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

SAMPLE_KEY = """-----BEGIN PGP PUBLIC KEY BLOCK-----

xsFNBFRt70cBEADH/8JgKzFnwQQqtllZ3nqxYQ1cZguLCbyu9s1AwRDNu0P2oWOR
UN9YoUS15kuWtTuneVlLbdbda3N/S/HApvOWu7Q1oIrRRkpO4Jv4xN+1KaSpaTy1
vG+HepH1D0tCSV0dmbX0S07yd0Ml7o4gMx2svBXeX41RHzjwCNkMUQJGuMF/w0hC
/Wqz6Sbki6QcqQx+YAjwVyUU1KdDRlm9efelQOskDwdr1j9Vk6ky8q+p29dEX5q2
FApKnwJb7YPwgRDMT/kCMJzHpLxW9Zj0OLkY4epADRi+eNiMblJsWRULs5l7T5oj
yEaXFrGHzOi2HaxidUTUUro2Mb0qZUXRYoEnZV0ntmFxUPIS75sFapJdRbLF0mqy
aMFe9PtmKyFOJXC/MfMaqhMxChWRZm0f8d12zDcVe5LTnVgZaeYr+vPnhqRaDI7w
WZBtCdeMGd4BLa1b3fwY0id2Ti6egFbJzVu2v4GGojBTRkZmlw+Srdzm3w9FA/oj
mAQV/R7snK6bc2o9gtIvPGlZceUTSOtySwlOBCd50YpL2K4GdT1GlEm/DAPSPAWP
Zn9gtZOe8XLxyWd2Qca/NTU0sYeG5xdQGes7pdHz9Mqb0vN14ojE8VdqS8qZx74v
qhnN3+xJ7BDNOjAjjhOAcn1mulX4N9u/WlUw7O67Ht5V/8ODwVTh2L3lLQARAQAB
zSNMYXVuY2hwYWQgUFBBIGZvciBTbmFwcHkgRGV2ZWxvcGVyc8LBeAQTAQIAIgUC
VG3vRwIbAwYLCQgHAwIGFQgCCQoLBBYCAwECHgECF4AACgkQ8YMd2vxC6Z2y1RAA
w7jFWZomYHUkUmm0FNEeRko6kv5iDNGqQXpp0JaZz06kC3dW7vjE3kNgwmgMdcA+
/a+Jgf3ii8AHyplUQXuopHAXvZyz6YS6r17B2TuKt47MtMkWSk56UZ6av0VnE1Ms
yf6FeBEtQwojLW7ZHNZPq0BlwcvK3/H+qNHitDaIdCmCDDu9mwuerd0ZoNwbW0A1
RPPl+Jw3uJ+tZWBAkJV+5dGzT/FJlCL28NjywktGjduhGE2nM5Q/Kd0S+kovwf9q
wmPMF8BLwUwshZoHKjLmalu08DzoyO6Bfcl6SThlO1iHoSayFnP6hJZeWkTaF/L+
Uzbbfnjz+fWAutUoZSxHsK50VfykqgUiG9t7Kv4q5B/3s7X42O4270yEc4OSZM+Y
Ij3EOKWCgHkR3YH9/wk3w1jPiVKjO+jfZnX7FV77vVxbsR/+ibzEPEo51nWcp64q
bBf+bSSGotGv5ef6ETWw4k0cOF9Dws/zmLs9g9CYpuv5DG5d/pvSUKVmqcb2iEc2
bymJDuKD3kE9MNCqdtnCbwVUpyRauzKhjzY8vmYlFzhlJB5WU0tR6VMMQZNcmXst
1T/RVTcIlXZUYfgbUwvPX6SOLERX1do9vtbD+XvWAYQ/J7G4knHRtf5RpiW1xQkp
FSbrQ9ACQFlqN49Ogbl47J6TZ7BrjDpROote55ixmrU=
=PEEJ
-----END PGP PUBLIC KEY BLOCK-----
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
    mock_run.side_effect = subprocess.CalledProcessError(
        cmd=["foo"], returncode=1, output=b"some error"
    )

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
