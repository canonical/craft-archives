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

"""Integration tests for repo.installer"""

import shutil
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List

import distro
import pytest
from craft_archives import repo

APT_SOURCES = dedent(
    """
    Types: deb deb-src
    URIs: http://ppa.launchpad.net/snappy-dev/snapcraft-daily/ubuntu
    Suites: focal
    Components: main
    Architectures: amd64
    Signed-By: {key_location}/craft-FC42E99D.gpg
    """
).lstrip()

VERSION_CODENAME = distro.codename()

PPA_SOURCES = dedent(
    """
    Types: deb
    URIs: http://ppa.launchpad.net/deadsnakes/ppa/ubuntu
    Suites: {codename}
    Components: main
    Architectures: amd64
    Signed-By: {key_location}/craft-6A755776.gpg
    """
).lstrip()

# Needed because some "clouds" are only available for specific Ubuntu releases
RELEASE_TO_CLOUD = {
    "jammy": {"cloud": "antelope", "codename": "jammy"},
    "focal": {"cloud": "wallaby", "codename": "focal"},
}

CLOUD_DATA = RELEASE_TO_CLOUD[VERSION_CODENAME]

CLOUD_SOURCES = dedent(
    """
    Types: deb
    URIs: http://ubuntu-cloud.archive.canonical.com/ubuntu
    Suites: {codename}-updates/{cloud}
    Components: main
    Architectures: amd64
    Signed-By: {key_location}/craft-EC4926EA.gpg
    """
).lstrip()

PUPPET_SOURCES = dedent(
    """
    Types: deb
    URIs: http://apt.puppet.com
    Suites: focal
    Components: puppet-tools
    Architectures: amd64
    Signed-By: {key_location}/craft-9E61EF26.gpg
    """
).lstrip()

PREFERENCES = dedent(
    """
    # This file is managed by craft-archives
    Package: *
    Pin: origin "ppa.launchpad.net"
    Pin-Priority: 100

    Package: *
    Pin: release o=LP-PPA-deadsnakes-ppa
    Pin-Priority: 1000

    Package: *
    Pin: origin "ubuntu-cloud.archive.canonical.com"
    Pin-Priority: 123

    """
).lstrip()


def create_etc_apt_dirs(etc_apt: Path):
    etc_apt.mkdir(parents=True)

    keyrings_dir = etc_apt / "keyrings"
    keyrings_dir.mkdir()

    sources_dir = etc_apt / "sources.list.d"
    sources_dir.mkdir()

    preferences_dir = etc_apt / "preferences.d"
    preferences_dir.mkdir()


@pytest.fixture
def fake_etc_apt(tmp_path, mocker) -> Path:
    """Mock the default paths used to store keys, sources and preferences."""
    etc_apt = tmp_path / "etc/apt"
    create_etc_apt_dirs(etc_apt)

    keyrings_dir = etc_apt / "keyrings"
    mocker.patch("craft_archives.repo.apt_key_manager.KEYRINGS_PATH", new=keyrings_dir)

    sources_dir = etc_apt / "sources.list.d"
    mocker.patch(
        "craft_archives.repo.apt_sources_manager._DEFAULT_SOURCES_DIRECTORY",
        new=sources_dir,
    )

    preferences_dir = etc_apt / "preferences.d"
    preferences_dir = preferences_dir / "craft-archives"
    mocker.patch(
        "craft_archives.repo.apt_preferences_manager._DEFAULT_PREFERENCES_FILE",
        new=preferences_dir,
    )

    return etc_apt


@pytest.fixture
def all_repo_types() -> List[Dict[str, Any]]:
    return [
        # a "standard" repo, with a key coming from the assets dir
        {
            "type": "apt",
            "formats": ["deb", "deb-src"],
            "components": ["main"],
            "suites": ["focal"],
            "key-id": "78E1918602959B9C59103100F1831DDAFC42E99D",
            "url": "http://ppa.launchpad.net/snappy-dev/snapcraft-daily/ubuntu",
            "priority": "defer",
        },
        # a "ppa" repo, with key coming from the ubuntu keyserver
        {
            "type": "apt",
            "ppa": "deadsnakes/ppa",
            "priority": "always",
        },
        # a "cloud" repo
        {
            "type": "apt",
            "cloud": CLOUD_DATA["cloud"],
            "pocket": "updates",
            "priority": 123,
        },
        # A key with multiple keys inside.
        {
            "type": "apt",
            "components": ["puppet-tools"],
            "suites": ["focal"],
            "url": "http://apt.puppet.com",
            "key-id": "D6811ED3ADEEB8441AF5AA8F4528B6CD9E61EF26",
        },
    ]


@pytest.fixture
def test_keys_dir(tmp_path, test_data_dir) -> Path:
    target_dir = tmp_path / "keys"
    target_dir.mkdir()

    shutil.copy2(test_data_dir / "FC42E99D.asc", target_dir)
    shutil.copy2(test_data_dir / "multi-keys/9E61EF26.asc", target_dir)

    return target_dir


def test_install(fake_etc_apt, all_repo_types, test_keys_dir):
    """Integrated test that checks the configuration of keys, sources and pins."""

    assert repo.install(project_repositories=all_repo_types, key_assets=test_keys_dir)

    check_keyrings(fake_etc_apt)
    check_sources(fake_etc_apt, signed_by_location=fake_etc_apt / "keyrings")
    check_preferences(fake_etc_apt)


def test_install_in_root(tmp_path, all_repo_types, test_keys_dir):
    """Integrated test that checks the configuration of keys, sources and pins."""
    etc_apt = tmp_path / "etc/apt"
    create_etc_apt_dirs(etc_apt)

    assert repo.install_in_root(
        project_repositories=all_repo_types, key_assets=test_keys_dir, root=tmp_path
    )

    check_keyrings(etc_apt)
    check_sources(etc_apt, signed_by_location=Path("/etc/apt/keyrings"))
    check_preferences(etc_apt)


def check_keyrings(etc_apt_dir: Path) -> None:
    keyrings_dir = etc_apt_dir / "keyrings"

    # Must have exactly these keyring files, one for each repo
    expected_key_ids = (
        "6A755776",
        "FC42E99D",
        "EC4926EA",
        "9E61EF26",
    )

    assert len(list(keyrings_dir.iterdir())) == len(expected_key_ids)
    for key_id in expected_key_ids:
        keyring_file = keyrings_dir / f"craft-{key_id}.gpg"
        assert keyring_file.is_file()


def check_sources(etc_apt_dir: Path, signed_by_location: Path) -> None:
    sources_dir = etc_apt_dir / "sources.list.d"

    keyrings_on_fs = etc_apt_dir / "keyrings"

    cloud_name = CLOUD_DATA["cloud"]
    codename = CLOUD_DATA["codename"]

    # Must have exactly these sources files, one for each repo
    source_to_contents = {
        "http_ppa_launchpad_net_snappy_dev_snapcraft_daily_ubuntu": APT_SOURCES.format(
            key_location=signed_by_location
        ),
        "ppa-deadsnakes_ppa": PPA_SOURCES.format(
            codename=VERSION_CODENAME, key_location=signed_by_location
        ),
        f"cloud-{cloud_name}": CLOUD_SOURCES.format(
            cloud=cloud_name,
            codename=codename,
            key_location=signed_by_location,
        ),
        "http_apt_puppet_com": PUPPET_SOURCES.format(key_location=signed_by_location),
    }

    assert len(list(keyrings_on_fs.iterdir())) == len(source_to_contents)

    for source_repo, expected_contents in source_to_contents.items():
        source_file = sources_dir / f"craft-{source_repo}.sources"
        assert source_file.is_file()
        assert source_file.read_text() == expected_contents


def check_preferences(etc_apt_dir: Path) -> None:
    # Exactly one "preferences" file
    preferences_dir = etc_apt_dir / "preferences.d"
    assert len(list(preferences_dir.iterdir())) == 1

    preferences_file = preferences_dir / "craft-archives"
    assert preferences_file.is_file()
    assert preferences_file.read_text() == PREFERENCES
