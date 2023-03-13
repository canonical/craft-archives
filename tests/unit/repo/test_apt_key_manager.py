# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2020-2023 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import pathlib
import subprocess
from textwrap import dedent
from unittest import mock
from unittest.mock import call

import pytest
from craft_archives.repo import apt_ppa, errors
from craft_archives.repo.apt_key_manager import AptKeyManager
from craft_archives.repo.package_repository import (
    PackageRepositoryApt,
    PackageRepositoryAptPPA,
)

with open(pathlib.Path(__file__).parent / "test_keys/FC42E99D.asc") as _f:
    SAMPLE_KEY = _f.read()


@pytest.fixture(autouse=True)
def mock_environ_copy(mocker):
    yield mocker.patch("os.environ.copy")


@pytest.fixture(autouse=True)
def mock_run(mocker):
    yield mocker.patch("subprocess.run", spec=subprocess.run)


@pytest.fixture
def mock_chmod(mocker):
    return mocker.patch("pathlib.Path.chmod", autospec=True)


@pytest.fixture(autouse=True)
def mock_apt_ppa_get_signing_key(mocker):
    yield mocker.patch(
        "craft_archives.repo.apt_ppa.get_launchpad_ppa_key_id",
        spec=apt_ppa.get_launchpad_ppa_key_id,
        return_value="FAKE-PPA-SIGNING-KEY",
    )


@pytest.fixture
def key_assets(tmp_path):
    assets = tmp_path / "key-assets"
    assets.mkdir(parents=True)
    yield assets


@pytest.fixture
def apt_gpg(key_assets, tmp_path):
    yield AptKeyManager(
        keyrings_path=tmp_path,
        key_assets=key_assets,
    )


def test_find_asset(
    apt_gpg,
    key_assets,
):
    key_id = "8" * 40
    expected_key_path = key_assets / ("8" * 8 + ".asc")
    expected_key_path.write_text("key")

    key_path = apt_gpg.find_asset_with_key_id(key_id=key_id)

    assert key_path == expected_key_path


def test_find_asset_none(
    apt_gpg,
):
    key_path = apt_gpg.find_asset_with_key_id(key_id="foo")

    assert key_path is None


def test_get_key_fingerprints(
    apt_gpg,
    mock_run,
):
    mock_run.return_value.stdout = dedent(
        """\
        pub   rsa4096 2021-02-13 [SC] [expires: 2029-02-11]
              FAKE-KEY-ID-FROM-GNUPG
        uid           [ unknown] Debian Stable Release Key (11/bullseye) <debian-release@lists.debian.org>
    """
    ).encode()

    ids = apt_gpg.get_key_fingerprints(key="8" * 40)

    assert ids == ["FAKE-KEY-ID-FROM-GNUPG"]
    assert mock_run.mock_calls == [
        call(
            ["gpg", "--batch", "--no-default-keyring", "--show-keys", mock.ANY],
            input=None,
            capture_output=True,
            check=True,
            env={"LANG": "C.UTF-8"},
        )
    ]


@pytest.mark.parametrize(
    "should_raise,expected_is_installed",
    [
        (True, False),
        (False, True),
    ],
)
def test_is_key_installed(
    should_raise, expected_is_installed, apt_gpg, mock_run, tmp_path
):
    if should_raise:
        mock_run.side_effect = subprocess.CalledProcessError(returncode=2, cmd=[])
    else:
        mock_run.returncode = 0

    keyring_path = tmp_path / "craft-FOO.gpg"

    # If the keyring file doesn't exist at all the function should exit early,
    # with no gpg calls
    assert not apt_gpg.is_key_installed(key_id="foo", keyring_path=keyring_path)
    assert mock_run.mock_calls == []

    keyring_path.touch()
    is_installed = apt_gpg.is_key_installed(key_id="foo", keyring_path=tmp_path)

    assert is_installed is expected_is_installed
    assert mock_run.mock_calls == [
        call(
            [
                "gpg",
                "--batch",
                "--no-default-keyring",
                "--keyring",
                f"gnupg-ring:{keyring_path}",
                "--list-keys",
                "foo",
            ],
            input=None,
            capture_output=True,
            check=True,
            env={"LANG": "C.UTF-8"},
        )
    ]


def test_is_key_installed_with_apt_key_failure(
    apt_gpg,
    mock_run,
):
    mock_run.side_effect = subprocess.CalledProcessError(
        cmd=["gpg"], returncode=1, output=b"some error"
    )

    is_installed = apt_gpg.is_key_installed(key_id="foo")

    assert is_installed is False


def test_install_key(
    apt_gpg,
    mock_run,
    mock_chmod,
):
    mock_run.return_value.stdout = dedent(
        """\
        pub   rsa4096 2014-11-20 [SC]
              78E1918602959B9C59103100F1831DDAFC42E99D
        uid                      Launchpad PPA for Snappy Developers

    """
    ).encode()

    apt_gpg.install_key(key=SAMPLE_KEY)

    assert mock_run.mock_calls == [
        call(
            ["gpg", "--batch", "--no-default-keyring", "--show-keys", mock.ANY],
            input=None,
            capture_output=True,
            check=True,
            env={"LANG": "C.UTF-8"},
        ),
        call(
            [
                "gpg",
                "--batch",
                "--no-default-keyring",
                "--keyring",
                mock.ANY,
                "--import",
                "-",
            ],
            input=SAMPLE_KEY.encode(),
            capture_output=True,
            check=True,
            env={"LANG": "C.UTF-8"},
        ),
    ]


def test_install_key_with_apt_key_failure(apt_gpg, mock_run):
    mock_run.side_effect = [
        subprocess.CompletedProcess(
            ["gpg", "--do-something"],
            returncode=0,
            stdout=b"pub    \nFAKEKEY"
        ),
        subprocess.CalledProcessError(
            cmd=["foo"], returncode=1, output=b"some error"
        )
    ]

    with pytest.raises(errors.AptGPGKeyInstallError) as raised:
        apt_gpg.install_key(key="FAKEKEY")

    assert str(raised.value) == "Failed to install GPG key: some error"


def test_install_key_from_keyserver(apt_gpg, mock_run, mock_chmod):
    apt_gpg.install_key_from_keyserver(key_id="FAKE_KEY", key_server="key.server")

    assert mock_run.mock_calls == [
        call(
            [
                "gpg",
                "--batch",
                "--no-default-keyring",
                "--keyring",
                mock.ANY,
                "--homedir",
                mock.ANY,
                "--keyserver",
                "key.server",
                "--recv-keys",
                "FAKE_KEY",
            ],
            check=True,
            env={"LANG": "C.UTF-8"},
            input=None,
            capture_output=True,
        )
    ]
    # Two chmod calls: one for the temporary dir that gpg uses during the fetching,
    # and one of the actual keyring file.
    assert mock_chmod.mock_calls == [call(mock.ANY, 0o700), call(mock.ANY, 0o644)]


def test_install_key_from_keyserver_with_apt_key_failure(apt_gpg, mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(
        cmd=["gpg"], returncode=1, output=b"some error"
    )

    with pytest.raises(errors.AptGPGKeyInstallError) as raised:
        apt_gpg.install_key_from_keyserver(
            key_id="fake-key-id", key_server="fake-server"
        )

    assert str(raised.value) == "Failed to install GPG key: some error"


@pytest.mark.parametrize(
    "is_installed",
    [True, False],
)
def test_install_package_repository_key_already_installed(
    is_installed, apt_gpg, mocker, mock_chmod
):
    mocker.patch(
        "craft_archives.repo.apt_key_manager.AptKeyManager.is_key_installed",
        return_value=is_installed,
    )
    package_repo = PackageRepositoryApt(
        components=["main", "multiverse"],
        key_id="8" * 40,
        key_server="xkeyserver.com",
        suites=["xenial"],
        url="http://archive.ubuntu.com/ubuntu",
    )

    updated = apt_gpg.install_package_repository_key(package_repo=package_repo)

    assert updated is not is_installed


def test_install_package_repository_key_from_asset(apt_gpg, key_assets, mocker):
    mocker.patch(
        "craft_archives.repo.apt_key_manager.AptKeyManager.is_key_installed",
        return_value=False,
    )
    mock_install_key = mocker.patch(
        "craft_archives.repo.apt_key_manager.AptKeyManager.install_key"
    )

    key_id = "123456789012345678901234567890123456AABB"
    expected_key_path = key_assets / "3456AABB.asc"
    expected_key_path.write_text("key-data")

    package_repo = PackageRepositoryApt(
        components=["main", "multiverse"],
        key_id=key_id,
        suites=["xenial"],
        url="http://archive.ubuntu.com/ubuntu",
    )

    updated = apt_gpg.install_package_repository_key(package_repo=package_repo)

    assert updated is True
    assert mock_install_key.mock_calls == [call(key="key-data")]


def test_install_package_repository_key_apt_from_keyserver(apt_gpg, mocker):
    mock_install_key_from_keyserver = mocker.patch(
        "craft_archives.repo.apt_key_manager.AptKeyManager.install_key_from_keyserver"
    )
    mocker.patch(
        "craft_archives.repo.apt_key_manager.AptKeyManager.is_key_installed",
        return_value=False,
    )

    key_id = "8" * 40

    package_repo = PackageRepositoryApt(
        components=["main", "multiverse"],
        key_id=key_id,
        key_server="key.server",
        suites=["xenial"],
        url="http://archive.ubuntu.com/ubuntu",
    )

    updated = apt_gpg.install_package_repository_key(package_repo=package_repo)

    assert updated is True
    assert mock_install_key_from_keyserver.mock_calls == [
        call(key_id=key_id, key_server="key.server")
    ]


def test_install_package_repository_key_ppa_from_keyserver(apt_gpg, mocker):
    mock_install_key_from_keyserver = mocker.patch(
        "craft_archives.repo.apt_key_manager.AptKeyManager.install_key_from_keyserver"
    )
    mocker.patch(
        "craft_archives.repo.apt_key_manager.AptKeyManager.is_key_installed",
        return_value=False,
    )

    package_repo = PackageRepositoryAptPPA(ppa="test/ppa")
    updated = apt_gpg.install_package_repository_key(package_repo=package_repo)

    assert updated is True
    assert mock_install_key_from_keyserver.mock_calls == [
        call(key_id="FAKE-PPA-SIGNING-KEY", key_server="keyserver.ubuntu.com")
    ]
