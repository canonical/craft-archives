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
import logging
import pathlib
import subprocess
from unittest import mock
from unittest.mock import call

import pytest
from craft_archives.repo import apt_ppa, errors, package_repository
from craft_archives.repo.apt_key_manager import AptKeyManager
from craft_archives.repo.package_repository import (
    PackageRepositoryApt,
    PackageRepositoryAptPPA,
    PackageRepositoryAptUCA,
)

with open(pathlib.Path(__file__).parent / "test_data/FC42E99D.asc") as _f:
    SAMPLE_KEY = _f.read()
SAMPLE_KEY_BYTES = SAMPLE_KEY.encode()

SAMPLE_GPG_SHOW_KEY_OUTPUT = b"""\
pub:-:4096:1:F1831DDAFC42E99D:1416490823:::-:::scSC::::::23::0:
fpr:::::::::FAKE-KEY-ID-FROM-GNUPG:
uid:-::::1416490823::DCB9EEE37DC9FD84C3DB333BFBF6C41A075EEF62::Launchpad PPA for Snappy Developers::::::::::0:
"""


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


@pytest.fixture(autouse=True)
def mock_apt_uca_key_id(mocker):
    yield mocker.patch.object(package_repository, "UCA_KEY_ID", "FAKE-UCA-KEY-ID")


@pytest.fixture()
def mock_logger(mocker):
    yield mocker.patch(
        "craft_archives.repo.apt_key_manager.logger", spec=logging.Logger
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
    mock_run.return_value.stdout = SAMPLE_GPG_SHOW_KEY_OUTPUT

    ids = apt_gpg.get_key_fingerprints(key="8" * 40)

    assert ids == ["FAKE-KEY-ID-FROM-GNUPG"]
    assert mock_run.mock_calls == [
        call(
            [
                "gpg",
                "--batch",
                "--no-default-keyring",
                "--with-colons",
                "--homedir",
                mock.ANY,
                "--import-options",
                "show-only",
                "--import",
            ],
            input=b"8" * 40,
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
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=2, cmd=[], output=b""
        )
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
                "--with-colons",
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


@pytest.mark.parametrize("return_code", [1, 2, 130])
def test_is_key_installed_with_gpg_failure(
    apt_gpg, mock_run, mock_logger, tmp_path, return_code
):
    keyring_file = tmp_path / "craft-FOO.gpg"
    keyring_file.touch()
    mock_run.side_effect = subprocess.CalledProcessError(
        cmd=["gpg"], returncode=return_code, output=b"some error"
    )

    is_installed = apt_gpg.is_key_installed(key_id="foo", keyring_path=tmp_path)

    assert is_installed is False
    mock_logger.warning.assert_called_once_with("gpg error: some error")


def test_install_key(
    apt_gpg,
    mock_run,
    mock_chmod,
):
    mock_run.return_value.stdout = SAMPLE_GPG_SHOW_KEY_OUTPUT

    apt_gpg.install_key(key=SAMPLE_KEY)

    assert mock_run.mock_calls == [
        call(
            [
                "gpg",
                "--batch",
                "--no-default-keyring",
                "--with-colons",
                "--homedir",
                mock.ANY,
                "--import-options",
                "show-only",
                "--import",
            ],
            input=SAMPLE_KEY_BYTES,
            capture_output=True,
            check=True,
            env={"LANG": "C.UTF-8"},
        ),
        call(
            [
                "gpg",
                "--batch",
                "--no-default-keyring",
                "--with-colons",
                "--keyring",
                mock.ANY,
                "--import",
                "-",
            ],
            input=SAMPLE_KEY_BYTES,
            capture_output=True,
            check=True,
            env={"LANG": "C.UTF-8"},
        ),
    ]


def test_install_key_missing_dir(mock_run, mock_chmod, tmp_path, key_assets):
    keyrings_path = tmp_path / "keyrings"
    assert not keyrings_path.exists()

    apt_gpg = AptKeyManager(
        keyrings_path=keyrings_path,
        key_assets=key_assets,
    )
    mock_run.return_value.stdout = SAMPLE_GPG_SHOW_KEY_OUTPUT

    apt_gpg.install_key(key=SAMPLE_KEY)
    assert keyrings_path.exists()


def test_install_key_with_gpg_failure(apt_gpg, mock_run):
    mock_run.side_effect = [
        subprocess.CompletedProcess(
            ["gpg", "--do-something"], returncode=0, stdout=SAMPLE_GPG_SHOW_KEY_OUTPUT
        ),
        subprocess.CalledProcessError(cmd=["foo"], returncode=1, output=b"some error"),
    ]

    with pytest.raises(errors.AptGPGKeyInstallError) as raised:
        apt_gpg.install_key(key="FAKEKEY")

    assert str(raised.value) == "Failed to install GPG key: some error"


@pytest.mark.parametrize(
    "fingerprints,error",
    [
        pytest.param([], "Invalid GPG key", id="no keys"),
        pytest.param(
            ["finger1", "finger2"],
            "Key must be a single key, not multiple.",
            id="multiple keys",
        ),
    ],
)
def test_install_key_with_key_issue(apt_gpg, mocker, fingerprints, error):
    mock_fingerprints = mocker.patch.object(apt_gpg, "get_key_fingerprints")
    mock_fingerprints.return_value = fingerprints

    with pytest.raises(errors.AptGPGKeyInstallError) as raised:
        apt_gpg.install_key(key="key")

    assert str(raised.value) == f"Failed to install GPG key: {error}"


def test_install_key_from_keyserver(apt_gpg, mock_run, mock_chmod):
    apt_gpg.install_key_from_keyserver(key_id="FAKE_KEY", key_server="key.server")

    assert mock_run.mock_calls == [
        call(
            [
                "gpg",
                "--batch",
                "--no-default-keyring",
                "--with-colons",
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


def test_install_package_repository_key_uca_from_keyserver(apt_gpg, mocker):
    mock_install_key_from_keyserver = mocker.patch(
        "craft_archives.repo.apt_key_manager.AptKeyManager.install_key_from_keyserver"
    )
    mocker.patch(
        "craft_archives.repo.apt_key_manager.AptKeyManager.is_key_installed",
        return_value=False,
    )

    package_repo = PackageRepositoryAptUCA(cloud="antelope")
    updated = apt_gpg.install_package_repository_key(package_repo=package_repo)

    assert updated is True
    assert mock_install_key_from_keyserver.mock_calls == [
        call(key_id="FAKE-UCA-KEY-ID", key_server="keyserver.ubuntu.com")
    ]
