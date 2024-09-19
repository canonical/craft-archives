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
import types

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


@pytest.fixture
def project_main_module() -> types.ModuleType:
    """Fixture that returns the project's principal package (imported).

    This fixture should be rewritten by "downstream" projects to return the correct
    module. Then, every test that uses this fixture will correctly test against the
    downstream project.
    """
    try:
        # This should be the project's main package; downstream projects must update this.
        import craft_archives as main_module
    except ImportError:
        pytest.fail(
            "Failed to import the project's main module: check if it needs updating",
        )
    return main_module
