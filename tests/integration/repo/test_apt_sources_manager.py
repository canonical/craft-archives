# This file is part of craft-archives.
#
# Copyright 2024 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Integration tests for AptSourcesManager."""

import logging
import platform
import subprocess
import textwrap
from pathlib import Path

import pytest
from craft_archives.repo import gpg
from craft_archives.repo.apt_sources_manager import AptSourcesManager, _add_architecture
from craft_archives.repo.package_repository import PackageRepositoryApt
from debian import deb822

EXPECTED_SIGNED_BY = "/usr/share/keyrings/FC42E99D.gpg"

DEFAULT_SOURCE = """
Types: deb
URIs: {source_url}
Suites: noble noble-updates noble-backports
Components: main universe restricted multiverse
Signed-By: {source_key}
"""


@pytest.mark.parametrize(
    ("source_url", "repo_url", "repo_arch", "expected_url"),
    [
        # Exact same url
        pytest.param(
            "http://archive.ubuntu.com/ubuntu/",
            "http://archive.ubuntu.com/ubuntu/",
            "i386",
            "archive.ubuntu.com/ubuntu/",
            id="archive-same-url",
        ),
        pytest.param(
            "http://ports.ubuntu.com/ubuntu-ports/",
            "http://ports.ubuntu.com/ubuntu-ports/",
            "armhf",
            "ports.ubuntu.com/ubuntu-ports/",
            id="ports-same-url",
        ),
        # Different url (no ending /)
        pytest.param(
            "http://archive.ubuntu.com/ubuntu/",
            "http://archive.ubuntu.com/ubuntu",
            "i386",
            "archive.ubuntu.com/ubuntu/",
            id="archive-different-ending",
        ),
        pytest.param(
            "http://ports.ubuntu.com/ubuntu-ports/",
            "http://ports.ubuntu.com/ubuntu-ports",
            "armhf",
            "ports.ubuntu.com/ubuntu-ports/",
            id="ports-different-ending",
        ),
        # Different scheme (http vs https)
        pytest.param(
            "http://archive.ubuntu.com/ubuntu/",
            "https://archive.ubuntu.com/ubuntu",
            "i386",
            "archive.ubuntu.com/ubuntu/",
            id="archive-different-scheme",
        ),
        pytest.param(
            "http://ports.ubuntu.com/ubuntu-ports/",
            "https://ports.ubuntu.com/ubuntu-ports",
            "armhf",
            "ports.ubuntu.com/ubuntu-ports/",
            id="ports-different-scheme",
        ),
    ],
)
def test_install_sources_conflicting_keys(
    tmp_path, test_data_dir, caplog, source_url, repo_url, repo_arch, expected_url
):
    caplog.set_level(logging.DEBUG)
    fake_system = tmp_path

    # Set up a base system that already has the repository that we want to
    # configure, signed by a key that exists on the system.
    keys_dir = fake_system / "usr/share/keyrings/"
    keys_dir.mkdir(parents=True)
    gpg.call_gpg(
        "-o",
        str(keys_dir / "FC42E99D.gpg"),
        "--dearmor",
        str(test_data_dir / "FC42E99D.asc"),
    )

    sources_dir = fake_system / "etc/apt/sources.list.d/"
    sources_dir.mkdir(parents=True)
    ubuntu_sources = sources_dir / "ubuntu.sources"

    ubuntu_sources.write_text(
        DEFAULT_SOURCE.format(
            source_url=source_url,
            source_key=EXPECTED_SIGNED_BY,
        )
    )

    repository = PackageRepositoryApt.unmarshal(
        {
            "type": "apt",
            "url": repo_url,
            "suites": ["noble"],
            "components": ["main", "universe"],
            "architectures": [repo_arch],
            "key_id": "78E1918602959B9C59103100F1831DDAFC42E99D",
        }
    )
    sources_manager = AptSourcesManager(
        sources_list_d=sources_dir, signed_by_root=fake_system
    )
    sources_manager._install_sources_apt(package_repo=repository)

    craft_source = next(sources_dir.glob("craft-*"))
    assert craft_source.is_file()

    craft_dict = deb822.Deb822(sequence=craft_source.read_text())
    assert craft_dict["Signed-By"] == EXPECTED_SIGNED_BY

    expected_log = textwrap.dedent(
        f"""
        Looking for existing sources files for url '{repository.url}' and suites ['noble']
        Reading sources in '{ubuntu_sources}' looking for '{expected_url}'
        Source has these suites: ['noble', 'noble-backports', 'noble-updates']
        Suites match - Signed-By is '/usr/share/keyrings/FC42E99D.gpg'
        """
    ).strip()

    all_log = "\n".join(caplog.messages)
    assert expected_log in all_log


@pytest.mark.slow
@pytest.mark.skipif(platform.machine() != "aarch64", reason="Test is for arm64")
@pytest.mark.skipif(
    not Path("/etc/apt/sources.list.d/ubuntu.sources").is_file(),
    reason="host doesn't use a deb822 'ubuntu.sources' file",
)
def test_add_architecture_arm64(tmp_path):
    """Verify `apt update` succeeds after adding an arch on an arm64 system.

    Regression test for #230.
    """
    # set up an isolated root dir, so we don't contaminate the host
    sources_dir = tmp_path / "etc/apt/sources.list.d"
    sources_dir.mkdir(parents=True)
    (tmp_path / "var/lib/apt/lists/partial").mkdir(parents=True)
    (tmp_path / "var/cache/apt/archives/partial").mkdir(parents=True)

    ubuntu_sources = sources_dir / "ubuntu.sources"
    ubuntu_sources.write_text(
        Path("/etc/apt/sources.list.d/ubuntu.sources").read_text()
    )

    _add_architecture(["arm64"], root=tmp_path, sources_dir=sources_dir)
    # run apt-get update against the isolated root directory
    cmd = [
        "apt-get",
        "update",
        "-o",
        f"Dir={tmp_path}",
        "-o",
        f"Dir::Etc={tmp_path}/etc/apt",
        "-o",
        "Dir::Etc::sourcelist=/dev/null",
        "-o",
        f"Dir::Etc::sourceparts={sources_dir}",
        "-o",
        "Dir::State::status=/var/lib/dpkg/status",
        "-o",
        "APT::Sandbox::User=root",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)

    assert res.returncode == 0, f"apt-get update failed:\n{res.stderr}"
