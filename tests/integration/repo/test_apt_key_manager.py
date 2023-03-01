# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2019-2023 Canonical Ltd.
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

import subprocess
from pathlib import Path

import pytest
from craft_archives.repo.apt_key_manager import AptKeyManager


@pytest.fixture
def fakeroot(mocker) -> None:
    """Fixture that injects a "--fakeroot" parameter into every "apt-key" call.

    The fixture *fails* if subprocess.run() is called for something else, so
    that the code can be reviewed and this fixture possibly removed.
    """
    original_run = subprocess.run

    def inject_fakeroot(cmd, *args, **kwargs):
        if cmd[0] == "apt-key":
            cmd = ["apt-key", "--fakeroot"] + cmd[1:]
        else:
            pytest.fail(f"Unexpected subprocess.run() call: {cmd}")
        return original_run(cmd, *args, **kwargs)

    mocker.patch.object(subprocess, "run", side_effect=inject_fakeroot)


@pytest.fixture
def test_keys_dir() -> Path:
    return Path(__file__).parent / "test_keys"


@pytest.fixture
def key_assets(tmp_path):
    assets = tmp_path / "key-assets"
    assets.mkdir(parents=True)
    return assets


@pytest.fixture
def gpg_keyring(tmp_path):
    return tmp_path / "keyring.gpg"


@pytest.fixture
def apt_gpg(key_assets, gpg_keyring, fakeroot):
    return AptKeyManager(
        gpg_keyring=gpg_keyring,
        key_assets=key_assets,
    )


def test_install_key(apt_gpg, gpg_keyring, test_keys_dir):
    assert not gpg_keyring.is_file()
    assert not apt_gpg.is_key_installed(key_id="FC42E99D", keyring_path=gpg_keyring)

    keypath = test_keys_dir / "FC42E99D.asc"
    apt_gpg.install_key(key=keypath.read_text())

    assert gpg_keyring.is_file()
    assert apt_gpg.is_key_installed(key_id="FC42E99D", keyring_path=gpg_keyring)


def test_install_key_from_keyserver(apt_gpg, gpg_keyring):
    assert not gpg_keyring.is_file()
    assert not apt_gpg.is_key_installed(key_id="FC42E99D", keyring_path=gpg_keyring)

    key_id = "78E1918602959B9C59103100F1831DDAFC42E99D"
    apt_gpg.install_key_from_keyserver(key_id=key_id)

    assert gpg_keyring.is_file()
    assert apt_gpg.is_key_installed(key_id="FC42E99D", keyring_path=gpg_keyring)
