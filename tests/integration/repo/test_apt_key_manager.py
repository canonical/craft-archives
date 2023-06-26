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
import tempfile
from typing import List

import gnupg
import pytest
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
    assert keyrings_path.stat().st_mode == 0o40755  # noqa: PLR2004 magic value


def get_fingerprints_via_python_gnupg(key: str) -> List[str]:
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
