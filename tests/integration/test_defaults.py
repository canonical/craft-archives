# This file is part of craft-archives.
#
# Copyright 2025 Canonical Ltd.
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
"""Tests for code for adjusting the default repositories."""

import pathlib
import shutil

import pytest
from craft_archives import defaults


@pytest.mark.parametrize(
    ("distro_name", "expected"),
    [
        ("warty", True),
        ("dapper", True),
        ("precise", True),
        ("precise-updates", True),
        ("precise-backports", True),
        ("precise-proposed", True),
        ("noble", False),  # This will need to change in like... 2034?
        ("nonexistent-release", False),
    ],
)
def test_is_on_old_releases_real_ubuntu(distro_name: str, expected):
    assert defaults._is_on_old_releases(distro_name) == expected


@pytest.mark.parametrize(
    ("distro_name", "archive_url", "retries", "expected"),
    [
        ("jessie", "http://archive.debian.org/debian-archive/debian/", 3, True),
        ("blorp", "http://canonical.com/", 0, False),
    ],
)
def test_is_on_old_releases_custom(
    distro_name: str, archive_url: str, retries: int, expected
):
    assert (
        defaults._is_on_old_releases(
            distro_name, archive_url=archive_url, retries=retries
        )
        == expected
    )


@pytest.mark.parametrize(
    "directory",
    [
        pytest.param(path, id=path.name)
        for path in (pathlib.Path(__file__).parent / "default_sources_data").iterdir()
        if path.is_dir()
    ],
)
def test_use_old_releases(tmp_path: pathlib.Path, directory: pathlib.Path):
    apt_dir = tmp_path / "etc/apt"
    apt_dir.parent.mkdir(parents=True)
    shutil.copytree(directory, apt_dir)

    expected_out = (directory / ".is_eol").exists()

    assert defaults.use_old_releases(root=tmp_path) == expected_out

    for expected in directory.rglob("*.new"):
        actual = apt_dir / expected.relative_to(directory).with_suffix("")
        assert actual.read_text() == expected.read_text()
