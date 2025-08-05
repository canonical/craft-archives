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
"""Integration tests for PackageRepository models."""

import pathlib

import pytest
from craft_archives.repo.package_repository import (
    PackageRepository,
    PackageRepositoryApt,
)
from pydantic import TypeAdapter

_TEST_SOURCES_DIRECTORY = pathlib.Path(__file__).parent / "default_sources_files"


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(p, id=str(p.relative_to(_TEST_SOURCES_DIRECTORY)))
        for p in _TEST_SOURCES_DIRECTORY.rglob("*.list")
    ],
)
def test_read_sources_lists(path: pathlib.Path):
    expected = TypeAdapter(list[PackageRepositoryApt]).validate_json(
        path.with_suffix(".list.json").read_text()
    )

    actual = PackageRepository.from_sources_list(path)
    assert actual == expected
    sources_lines = path.read_text().splitlines()
    for source in actual:
        for line in source.to_sources_list():
            assert line in sources_lines


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(p, id=str(p.relative_to(_TEST_SOURCES_DIRECTORY)))
        for p in _TEST_SOURCES_DIRECTORY.rglob("*.sources")
    ],
)
def test_read_deb822_sources(path: pathlib.Path):
    expected = TypeAdapter(list[PackageRepositoryApt]).validate_json(
        path.with_suffix(".sources.json").read_text()
    )
    sources_text = path.read_text()

    actual = PackageRepository.from_deb822(path)
    assert actual == expected
    for source in actual:
        assert source.to_deb822() in sources_text
