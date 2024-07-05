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
"""Basic test configuration for craft-archives."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """test_data directory directly under tests directory."""
    path = Path(__file__).parent / "test_data"
    assert path.is_dir()
    return path


@pytest.fixture(scope="session")
def sample_key_path(test_data_dir) -> Path:
    path = test_data_dir / "FC42E99D.asc"
    assert path.is_file()
    return path


@pytest.fixture(scope="session")
def sample_key_string(sample_key_path) -> str:
    return sample_key_path.read_text()


@pytest.fixture(scope="session")
def sample_key_bytes(sample_key_path) -> bytes:
    return sample_key_path.read_bytes()
