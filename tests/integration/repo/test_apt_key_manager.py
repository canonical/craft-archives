# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2023 Canonical Ltd.
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

"""Integration tests for AptKeyManager"""

import logging
import tempfile

import gnupg
import pytest
from craft_archives.repo import errors
from craft_archives.repo.apt_key_manager import AptKeyManager


@pytest.fixture
def key_assets(tmp_path):
    assets = tmp_path / "key-assets"
    assets.mkdir(parents=True)
    return assets


@pytest.fixture
def gpg_keyring(tmp_path):
    return tmp_path / "keyring.gpg"


@pytest.fixture
def apt_gpg(key_assets, tmp_path):
    return AptKeyManager(
        keyrings_path=tmp_path,
        key_assets=key_assets,
    )


def test_install_key(apt_gpg, tmp_path, test_data_dir):
    expected_file = tmp_path / "craft-FC42E99D.gpg"
    assert not expected_file.exists()
    assert not apt_gpg.is_key_installed(key_id="FC42E99D")

    keypath = test_data_dir / "FC42E99D.asc"
    apt_gpg.install_key(key=keypath.read_text())

    assert expected_file.is_file()
    assert apt_gpg.is_key_installed(key_id="FC42E99D")

    # Check that gpg's backup file has been removed
    backup_file = expected_file.with_suffix(expected_file.suffix + "~")
    assert not backup_file.is_file()


@pytest.mark.slow
def test_install_key_from_keyserver(apt_gpg, tmp_path):
    expected_file = tmp_path / "craft-FC42E99D.gpg"
    assert not expected_file.exists()
    assert not apt_gpg.is_key_installed(key_id="FC42E99D")

    key_id = "78E1918602959B9C59103100F1831DDAFC42E99D"
    apt_gpg.install_key_from_keyserver(key_id=key_id)

    assert expected_file.is_file()
    assert apt_gpg.is_key_installed(key_id="FC42E99D")


def test_install_key_missing_directory(key_assets, tmp_path, test_data_dir):
    keyrings_path = tmp_path / "keyrings"
    assert not keyrings_path.exists()

    apt_gpg = AptKeyManager(
        keyrings_path=keyrings_path,
        key_assets=key_assets,
    )

    keypath = test_data_dir / "FC42E99D.asc"
    apt_gpg.install_key(key=keypath.read_text())

    assert keyrings_path.exists()
    assert keyrings_path.stat().st_mode == 0o40755


@pytest.mark.parametrize(
    "key_id, expected_keyfile",
    (
        # Desired key-id is provided: imported file has its shortid
        ("D6811ED3ADEEB8441AF5AA8F4528B6CD9E61EF26", "craft-9E61EF26.gpg"),
        # Desired key-id is *not* provided: imported file has the shortid of the
        # first fingerprint in the original file.
        (None, "craft-07BB6C57.gpg"),
    ),
)
def test_install_key_gpg_errors_valid(
    apt_gpg, tmp_path, test_data_dir, key_id, expected_keyfile, caplog
):
    """Test that install_key() succeeds even if gpg emits errors to stderr."""
    caplog.set_level(logging.DEBUG)

    problem_key = test_data_dir / "multi-keys/9E61EF26.asc"

    apt_gpg.install_key(key=problem_key.read_text(), key_id=key_id)

    # Check that the key was successfully imported, even with the errors
    expected_file = tmp_path / expected_keyfile
    assert expected_file.is_file()
    if key_id is not None:
        assert key_id in AptKeyManager.get_key_fingerprints(
            key=expected_file.read_bytes()
        )

    # Check that log messages containing gpg's output were generated
    marker = caplog.messages.index("gpg stderr:")
    gpg_log = caplog.messages[marker + 1]
    expected_gpg_log = (
        "gpg: key 7F438280EF8D349F: 8 signatures not checked due to missing keys"
    )
    assert expected_gpg_log in gpg_log


def test_install_key_gpg_errors_invalid_key_id(
    apt_gpg, tmp_path, test_data_dir, caplog, mocker
):
    """Test that install_key() fails if the key contents are imported successfully but
    the key_id is *not* found in the imported file."""
    caplog.set_level(logging.DEBUG)

    missing_key_id = "NOT-IN-KEY"
    problem_key = test_data_dir / "multi-keys/9E61EF26.asc"
    key_contents = problem_key.read_text()

    original_get_fingerprints = AptKeyManager.get_key_fingerprints

    # This is tricky: We want the install_key() to fail *after* the key is imported, but
    # AptKeyManager.get_key_fingerprints() is called twice: once before, and once after,
    # the actual installation. So this mock adds the missing key for the first call and
    # not the second.
    # A better test would need a key file that actually has this behavior, but we don't
    # have one right now.
    def fake_get_fingerprints(*, key: str) -> list[str]:
        result = original_get_fingerprints(key=key)
        if key is key_contents:
            result.append(missing_key_id)
        return result

    mocker.patch.object(
        AptKeyManager, "get_key_fingerprints", side_effect=fake_get_fingerprints
    )

    expected_message = "Failed to install GPG key: key-id NOT-IN-KEY not imported."
    with pytest.raises(errors.AptGPGKeyInstallError, match=expected_message):
        apt_gpg.install_key(key=key_contents, key_id=missing_key_id)

    # Check that log messages containing gpg's output were generated
    marker = caplog.messages.index("gpg stderr:")
    gpg_log = caplog.messages[marker + 1]
    expected_gpg_log = (
        "gpg: key 7F438280EF8D349F: 8 signatures not checked due to missing keys"
    )
    assert expected_gpg_log in gpg_log


def get_fingerprints_via_python_gnupg(key: str) -> list[str]:
    with tempfile.NamedTemporaryFile(suffix="keyring") as temp_file:
        return gnupg.GPG(keyring=temp_file.name).import_keys(key_data=key).fingerprints


@pytest.mark.parametrize(
    "keyfile", ["multi-keys/9E61EF26.asc", "multi-keys/0264B26D.asc", "FC42E99D.asc"]
)
def test_fingerprint_compat(test_data_dir, keyfile):
    """Test that ``AptKeyManager.get_key_fingerprints()`` returns the same values
    as python-gnupg (including expired keys)"""

    key_file = test_data_dir / keyfile
    key = key_file.read_text()

    python_gnupg_fingerprints = get_fingerprints_via_python_gnupg(key)
    our_fingerprints = AptKeyManager.get_key_fingerprints(key=key)
    assert len(our_fingerprints) > 0

    assert our_fingerprints == python_gnupg_fingerprints
