# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2023 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""Tests for apt_preferencs_manager"""
import io
import pathlib
import shutil
from textwrap import dedent

import pytest
from craft_archives.repo.apt_preferences_manager import (
    AptPreferencesManager,
    Preference,
)

VALID_PRIORITY_STRINGS = ("always", "prefer", "defer")
VALID_PRIORITY_INTS = (1000, 990, 100, 500, 1, -1)
VALID_PRIORITIES = (*VALID_PRIORITY_STRINGS, *VALID_PRIORITY_INTS)
INVALID_PRIORITIES = (0,)

SAMPLE_PINS = (
    "release o=LP-PPA-deadsnakes-ppa-ppa",
    'origin "developer.download.nvidia.com"',
)

DATA_PATH = pathlib.Path(__file__).parent / "test_data"


# region Preference
@pytest.mark.parametrize("priority", VALID_PRIORITIES)
@pytest.mark.parametrize("pin", SAMPLE_PINS)
def test_create_valid_preferences(pin, priority):
    Preference(pin=pin, priority=priority)


@pytest.mark.parametrize("priority", INVALID_PRIORITIES)
def test_invalid_priorities(priority):
    with pytest.raises(ValueError):
        Preference(pin="", priority=priority)


@pytest.mark.parametrize(
    "input_str,expected",
    [
        (
            dedent(
                """
                Package: *
                Pin: release o=LP-PPA-ppa-ppa
                Pin-Priority: 123
                """
            ),
            Preference(pin="release o=LP-PPA-ppa-ppa", priority=123),
        ),
        (
            dedent(
                """
                Package: *
                Pin: origin "developer.download.nvidia.com"
                Pin-Priority: 456
                """
            ),
            Preference(pin='origin "developer.download.nvidia.com"', priority=456),
        ),
        (
            dedent(
                """
                Explanation: This line will be ignored, but logged.
                Package: *
                Pin: origin "valvesoftware.com"
                Pin-Priority: 789
                """
            ),
            Preference(pin='origin "valvesoftware.com"', priority=789),
        ),
    ],
)
def test_preference_string_parsing(input_str, expected):
    preference = Preference.from_string(input_str)

    assert preference == expected


@pytest.mark.parametrize(
    "preference,expected",
    [
        (
            Preference(pin="release o=LP-PPA-ppa-ppa", priority=123),
            dedent(
                """\
                Package: *
                Pin: release o=LP-PPA-ppa-ppa
                Pin-Priority: 123

                """
            ),
        ),
        (
            Preference(pin='origin "valvesoftware.com"', priority=789),
            dedent(
                """\
                Package: *
                Pin: origin "valvesoftware.com"
                Pin-Priority: 789

                """
            ),
        ),
    ],
)
def test_preference_to_file(preference, expected):
    file = io.StringIO()

    preference.to_file(file)

    assert file.getvalue() == expected


# endregion
# region AptPreferencesManager
def test_read_nonexistent_file(tmp_path):
    preferences_path = tmp_path / "test-preferences"

    manager = AptPreferencesManager(path=preferences_path)

    assert manager._preferences == []


@pytest.mark.parametrize(
    "pref_path,expected",
    [
        (
            DATA_PATH / "no_header.preferences",
            [
                Preference(pin="release o=LP-PPA-safety-ppa", priority=99999),
                Preference(pin='origin "apt_ppa.redhat.arch.mac"', priority=-1),
            ],
        ),
        (
            DATA_PATH / "with_header.preferences",
            [
                Preference(pin="release o=LP-PPA-safety-ppa", priority=99999),
                Preference(pin='origin "apt_ppa.redhat.arch.mac"', priority=-1),
            ],
        ),
    ],
)
def test_read_existing_preferences(pref_path, expected):
    manager = AptPreferencesManager(path=pref_path)

    assert manager._preferences == expected


@pytest.mark.parametrize(
    "pref_path,expected_path",
    [
        (
            DATA_PATH / "no_header.preferences",
            DATA_PATH / "expected.preferences",
        ),
        (
            DATA_PATH / "with_header.preferences",
            DATA_PATH / "expected.preferences",
        ),
        (
            DATA_PATH / "expected.preferences",
            DATA_PATH / "expected.preferences",
        ),
    ],
)
def test_read_and_write_correct(pref_path, expected_path, tmp_path):
    actual_path = tmp_path / "pref"
    shutil.copyfile(pref_path, actual_path)
    manager = AptPreferencesManager(path=actual_path)

    manager.write()

    assert actual_path.read_text() == expected_path.read_text()


@pytest.mark.parametrize(
    "preferences,expected_path",
    [
        pytest.param(
            [  # Preferences
                {"priority": 99999, "pin": "release o=LP-PPA-safety-ppa"},
                {"priority": -1, "pin": 'origin "apt_ppa.redhat.arch.mac"'},
            ],
            DATA_PATH / "expected.preferences",
            id="basic_file",
        )
    ],
)
def test_preferences_added(tmp_path, preferences, expected_path):
    actual_path = tmp_path / "preferences"
    manager = AptPreferencesManager(path=actual_path)

    for pref in preferences:
        manager.add(**pref)
    manager.write()

    assert actual_path.read_text() == expected_path.read_text()


# endregion
