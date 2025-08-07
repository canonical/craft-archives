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
import subprocess
from pathlib import Path
from unittest import mock
from unittest.mock import call

import pytest
from craft_archives.repo import apt_ppa, errors, package_repository
from craft_archives.repo.apt_key_manager import KEYRINGS_PATH, AptKeyManager
from craft_archives.repo.package_repository import (
    PackageRepositoryApt,
    PackageRepositoryAptPPA,
    PackageRepositoryAptUCA,
)

# pyright: reportGeneralTypeIssues=false

SAMPLE_GPG_SHOW_KEY_OUTPUT = b"""\
pub:-:4096:1:F1831DDAFC42E99D:1416490823:::-:::scSC::::::23::0:
fpr:::::::::FAKE-KEY-ID-FROM-GNUPG:
uid:-::::1416490823::DCB9EEE37DC9FD84C3DB333BFBF6C41A075EEF62::Launchpad PPA for Snappy Developers::::::::::0:
"""

# Real output listing keys with sub/multiple keys.

# Docker repo: 1 primary key ("pub:") and 1 subkey ("sub:")
SAMPLE_GPG_DOCKER_OUTPUT = b"""\
pub:-:4096:1:8D81803C0EBFCD88:1487788586:::-:::escaESCA::::::23::0:
fpr:::::::::9DC858229FC7DD38854AE2D88D81803C0EBFCD88:
uid:-::::1487792064::B50C6A3598EE2C27B34302761B93B277BF674C93::Docker Release (CE deb) <docker@docker.com>::::::::::0:
sub:-:4096:1:7EA0A9C3F273FCD8:1487788586::::::s::::::23:
fpr:::::::::D3306A018370199E527AE7997EA0A9C3F273FCD8:
"""

# Puppet repo: Multiple primary and subkeys, most expired ("pub:e:" and "sub:e:").
SAMPLE_GPG_PUPPET_OUTPUT = b"""\
pub:e:4096:1:B8F999C007BB6C57:1360109177:1549910347::-:::sc::::::23::0:
fpr:::::::::8735F5AF62A99A628EC13377B8F999C007BB6C57:
uid:e::::1455302347::A8FC88656336852AD4301DF059CEE6134FD37C21::Puppet Labs Nightly Build Key (Puppet Labs Nightly Build Key) <delivery@puppetlabs.com>::::::::::0:
uid:e::::1455302347::4EF2A82F1FF355343885012A832C628E1A4F73A8::Puppet Labs Nightly Build Key (Puppet Labs Nightly Build Key) <info@puppetlabs.com>::::::::::0:
sub:e:4096:1:AE8282E5A5FC3E74:1360109177:1549910293:::::e::::::23:
fpr:::::::::F838D657CCAF0E4A6375B0E9AE8282E5A5FC3E74:
gpg: key 7F438280EF8D349F: 8 signatures not checked due to missing keys
pub:e:4096:1:7F438280EF8D349F:1471554366:1629234366::-:::sc::::::23::0:
fpr:::::::::6F6B15509CF8E59E6E469F327F438280EF8D349F:
uid:e::::1471554366::B648B946D1E13EEA5F4081D8FE5CF4D001200BC7::Puppet, Inc. Release Key (Puppet, Inc. Release Key) <release@puppet.com>::::::::::0:
sub:e:4096:1:A2D80E04656674AE:1471554366:1629234366:::::e::::::23:
fpr:::::::::07F5ABF8FE84BC3736D2AAD3A2D80E04656674AE:
pub:-:4096:1:4528B6CD9E61EF26:1554759562:1743975562::-:::scESC::::::23::0:
fpr:::::::::D6811ED3ADEEB8441AF5AA8F4528B6CD9E61EF26:
uid:-::::1554759562::B648B946D1E13EEA5F4081D8FE5CF4D001200BC7::Puppet, Inc. Release Key (Puppet, Inc. Release Key) <release@puppet.com>::::::::::0:
sub:-:4096:1:F230A24E9F057A83:1554759562:1743975562:::::e::::::23:
fpr:::::::::90A29D0A6576E2CA185AED3EF230A24E9F057A83:
"""


@pytest.fixture(autouse=True)
def mock_environ_copy(mocker):
    return mocker.patch("os.environ.copy")


@pytest.fixture(autouse=True)
def mock_run(mocker):
    return mocker.patch("subprocess.run", spec=subprocess.run)


@pytest.fixture
def mock_chmod(mocker):
    return mocker.patch("pathlib.Path.chmod", autospec=True)


@pytest.fixture(autouse=True)
def mock_apt_ppa_get_signing_key(mocker):
    return mocker.patch(
        "craft_archives.repo.apt_ppa.get_launchpad_ppa_key_id",
        spec=apt_ppa.get_launchpad_ppa_key_id,
        return_value="FAKE-PPA-SIGNING-KEY",
    )


@pytest.fixture(autouse=True)
def mock_apt_uca_key_id(mocker):
    return mocker.patch.object(package_repository, "UCA_KEY_ID", "FAKE-UCA-KEY-ID")


@pytest.fixture
def mock_logger(mocker):
    return mocker.patch("craft_archives.repo.gpg.logger", spec=logging.Logger)


@pytest.fixture
def key_assets(tmp_path):
    assets = tmp_path / "key-assets"
    assets.mkdir(parents=True)
    return assets


@pytest.fixture
def apt_gpg(key_assets, tmp_path):
    return AptKeyManager(
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


def test_get_key_fingerprints(apt_gpg, mock_run):
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
    ("sample_output", "expected_keys"),
    [
        (SAMPLE_GPG_DOCKER_OUTPUT, ["9DC858229FC7DD38854AE2D88D81803C0EBFCD88"]),
        (
            SAMPLE_GPG_PUPPET_OUTPUT,
            [
                "8735F5AF62A99A628EC13377B8F999C007BB6C57",
                "6F6B15509CF8E59E6E469F327F438280EF8D349F",
                "D6811ED3ADEEB8441AF5AA8F4528B6CD9E61EF26",
            ],
        ),
    ],
)
def test_get_key_fingerprints_multi_keys(
    apt_gpg, mock_run, sample_output, expected_keys
):
    mock_run.return_value.stdout = sample_output

    ids = apt_gpg.get_key_fingerprints(key="8" * 40)

    assert ids == expected_keys


@pytest.mark.parametrize(
    ("should_raise", "expected_is_installed"),
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
    assert not apt_gpg.is_key_installed(key_id="foo")
    assert mock_run.mock_calls == []

    keyring_path.touch()
    is_installed = apt_gpg.is_key_installed(key_id="foo")

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

    is_installed = apt_gpg.is_key_installed(key_id="foo")

    assert is_installed is False
    mock_logger.warning.assert_called_once_with("gpg error: some error")


@pytest.mark.parametrize("key_id", [None, "FAKE-KEY-ID-FROM-GNUPG"])
def test_install_key(
    apt_gpg, mock_run, mock_chmod, sample_key_string, sample_key_bytes, tmp_path, key_id
):
    mock_run.return_value.stdout = SAMPLE_GPG_SHOW_KEY_OUTPUT
    mock_run.return_value.stderr = None

    apt_gpg.install_key(key=sample_key_string)

    # The key should be imported to a file that contains the short-id of the
    # "FAKE-KEY-ID-FROM-GNUPG" fingerprint, (so the last 8 characters).
    expected_imported_keyring = f"gnupg-ring:{tmp_path / 'craft-OM-GNUPG.gpg'}"

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
            input=sample_key_bytes,
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
                expected_imported_keyring,
                "--homedir",
                mock.ANY,
                "--import",
                "-",
            ],
            input=sample_key_bytes,
            capture_output=True,
            check=True,
            env={"LANG": "C.UTF-8"},
        ),
    ]


def test_install_key_missing_dir(
    sample_key_string, mock_run, mock_chmod, tmp_path, key_assets
):
    keyrings_path = tmp_path / "keyrings"
    assert not keyrings_path.exists()

    apt_gpg = AptKeyManager(
        keyrings_path=keyrings_path,
        key_assets=key_assets,
    )
    mock_run.return_value.stdout = SAMPLE_GPG_SHOW_KEY_OUTPUT

    apt_gpg.install_key(key=sample_key_string)
    assert keyrings_path.exists()


def test_install_package_repository_key_missing_dir(
    mock_run, mock_chmod, tmp_path, key_assets, mock_apt_ppa_get_signing_key
):
    keyrings_path = tmp_path / "keyrings"
    assert not keyrings_path.exists()
    repo = PackageRepositoryAptPPA(ppa="snappy-dev/snapcraft-daily", type="apt")
    mock_run.return_value.stdout = SAMPLE_GPG_SHOW_KEY_OUTPUT
    apt_gpg = AptKeyManager(keyrings_path=keyrings_path, key_assets=key_assets)

    apt_gpg.install_package_repository_key(package_repo=repo)

    assert keyrings_path.is_dir()


def test_install_key_with_gpg_failure(apt_gpg, mock_run):
    mock_run.side_effect = [
        subprocess.CompletedProcess(
            ["gpg", "--do-something"], returncode=0, stdout=SAMPLE_GPG_SHOW_KEY_OUTPUT
        ),
        subprocess.CalledProcessError(cmd=["foo"], returncode=1, stderr=b"some error"),
    ]

    with pytest.raises(errors.AptGPGKeyInstallError) as raised:
        apt_gpg.install_key(key="FAKEKEY")

    assert str(raised.value) == "Failed to install GPG key: some error"


def test_install_key_with_no_fingerprints(apt_gpg, mocker):
    """Test installing key contents that have no fingerprints at all."""
    mock_fingerprints = mocker.patch.object(apt_gpg, "get_key_fingerprints")
    mock_fingerprints.return_value = []

    with pytest.raises(errors.AptGPGKeyInstallError) as raised:
        apt_gpg.install_key(key="key")

    assert str(raised.value) == "Failed to install GPG key: Invalid GPG key"


def test_install_key_with_invalid_key_id(apt_gpg, mocker):
    """Test installing key contents where the desired key-id is *not* among the
    existing fingerprints."""
    mock_fingerprints = mocker.patch.object(apt_gpg, "get_key_fingerprints")
    mock_fingerprints.return_value = ["FINGERPRINT-1", "FINGERPRINT-2"]

    expected_error = (
        "Failed to install GPG key: Desired key_id not found in fingerprints"
    )
    with pytest.raises(errors.AptGPGKeyInstallError, match=expected_error):
        apt_gpg.install_key(key="key", key_id="IM-NOT-THERE")


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


def test_install_key_from_keyserver_with_gpg_failure(apt_gpg, mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(
        cmd=["gpg"], returncode=1, stderr=b"some error"
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
    package_repo = PackageRepositoryApt.model_validate(
        {
            "type": "apt",
            "components": ["main", "multiverse"],
            "key-id": "8" * 40,
            "key-server": "xkeyserver.com",
            "suites": ["xenial"],
            "url": "http://archive.ubuntu.com/ubuntu",
        }
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

    package_repo = PackageRepositoryApt.model_validate(
        {
            "type": "apt",
            "components": ["main", "multiverse"],
            "key-id": key_id,
            "suites": ["xenial"],
            "url": "http://archive.ubuntu.com/ubuntu",
        }
    )

    updated = apt_gpg.install_package_repository_key(package_repo=package_repo)

    assert updated is True
    assert mock_install_key.mock_calls == [call(key="key-data", key_id=key_id)]


def test_install_package_repository_key_apt_from_keyserver(apt_gpg, mocker):
    mock_install_key_from_keyserver = mocker.patch(
        "craft_archives.repo.apt_key_manager.AptKeyManager.install_key_from_keyserver"
    )
    mocker.patch(
        "craft_archives.repo.apt_key_manager.AptKeyManager.is_key_installed",
        return_value=False,
    )

    key_id = "8" * 40

    package_repo = PackageRepositoryApt.model_validate(
        {
            "type": "apt",
            "components": ["main", "multiverse"],
            "key-id": key_id,
            "key-server": "key.server",
            "suites": ["xenial"],
            "url": "http://archive.ubuntu.com/ubuntu",
        }
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

    package_repo = PackageRepositoryAptPPA(type="apt", ppa="test/ppa")
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

    package_repo = PackageRepositoryAptUCA(type="apt", cloud="antelope")
    updated = apt_gpg.install_package_repository_key(package_repo=package_repo)

    assert updated is True
    assert mock_install_key_from_keyserver.mock_calls == [
        call(key_id="FAKE-UCA-KEY-ID", key_server="keyserver.ubuntu.com")
    ]


def test_keyrings_path_for_root():
    assert AptKeyManager.keyrings_path_for_root() == KEYRINGS_PATH
    assert AptKeyManager.keyrings_path_for_root(Path("/my/root")) == Path(
        "/my/root/etc/apt/keyrings"
    )
