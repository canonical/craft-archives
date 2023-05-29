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
import shutil
from pathlib import Path
from textwrap import dedent

import pytest
from craft_archives.repo.apt_preferences_manager import (
    _DEFAULT_PREFERENCES_FILE,
    AptPreferencesManager,
    Preference,
)
from craft_archives.repo.errors import AptPreferencesError

VALID_PRIORITY_STRINGS = ("always", "prefer", "defer")
VALID_PRIORITY_INTS = (1000, 990, 100, 500, 1, -1)
VALID_PRIORITIES = (*VALID_PRIORITY_STRINGS, *VALID_PRIORITY_INTS)
INVALID_PRIORITIES = (0,)

SAMPLE_PINS = (
    "release o=LP-PPA-deadsnakes-ppa-ppa",
    'origin "developer.download.nvidia.com"',
)


@pytest.fixture
def manager(tmp_path):
    yield AptPreferencesManager(path=tmp_path / "preferences")


# region Preference
@pytest.mark.parametrize("priority", VALID_PRIORITIES)
@pytest.mark.parametrize("pin", SAMPLE_PINS)
def test_create_valid_preferences(pin, priority):
    Preference(pin=pin, priority=priority)


@pytest.mark.parametrize("priority", INVALID_PRIORITIES)
def test_invalid_priorities(priority):
    with pytest.raises(AptPreferencesError):
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
    assert str(preference) == expected


# endregion
# region AptPreferencesManager
def test_read_nonexistent_file(tmp_path):
    preferences_path = tmp_path / "test-preferences"

    manager = AptPreferencesManager(path=preferences_path)

    assert manager._preferences == []


@pytest.mark.parametrize(
    "pref_file,expected",
    [
        (
            "no_header.preferences",
            [
                Preference(pin="release o=LP-PPA-safety-ppa", priority=99999),
                Preference(pin='origin "apt_ppa.redhat.arch.mac"', priority=-1),
            ],
        ),
        (
            "with_header.preferences",
            [
                Preference(pin="release o=LP-PPA-safety-ppa", priority=99999),
                Preference(pin='origin "apt_ppa.redhat.arch.mac"', priority=-1),
            ],
        ),
        ("empty.preferences", []),
        ("only_comment.preferences", []),
        ("many_blank_lines.preferences", []),
    ],
)
def test_read_existing_preferences(test_data_dir, pref_file, expected):
    pref_path = test_data_dir / pref_file
    manager = AptPreferencesManager(path=pref_path)

    manager.read()

    assert manager._preferences == expected


@pytest.mark.parametrize(
    "pref_file,expected_file",
    [
        (
            "no_header.preferences",
            "expected.preferences",
        ),
        (
            "with_header.preferences",
            "expected.preferences",
        ),
        (
            "expected.preferences",
            "expected.preferences",
        ),
    ],
)
def test_read_and_write_correct(test_data_dir, pref_file, expected_file, tmp_path):
    pref_path = test_data_dir / pref_file
    expected_path = test_data_dir / expected_file
    actual_path = tmp_path / "pref"
    shutil.copyfile(pref_path, actual_path)
    manager = AptPreferencesManager(path=actual_path)

    manager.read()
    manager.write()

    assert actual_path.read_text() == expected_path.read_text()


def test_write_empty_preferences_removes_file(tmp_path):
    file = tmp_path / "pref.preferences"
    file.touch()

    manager = AptPreferencesManager(path=file)

    # Still return true if the file was changed, even if that change was removal.
    assert manager.write()
    assert not file.exists()


@pytest.mark.parametrize(
    "preferences,expected_file",
    [
        pytest.param(
            [  # Preferences
                {"priority": 99999, "pin": "release o=LP-PPA-safety-ppa"},
                {"priority": -1, "pin": 'origin "apt_ppa.redhat.arch.mac"'},
            ],
            "expected.preferences",
            id="basic_file",
        )
    ],
)
def test_preferences_added(test_data_dir, tmp_path, preferences, expected_file):
    expected_path = test_data_dir / expected_file
    actual_path = tmp_path / "preferences"
    manager = AptPreferencesManager(path=actual_path)

    for pref in preferences:
        manager.add(**pref)
    manager.write()

    assert actual_path.read_text() == expected_path.read_text()


def test_preferences_path_for_root():
    assert (
        AptPreferencesManager.preferences_path_for_root() == _DEFAULT_PREFERENCES_FILE
    )
    assert AptPreferencesManager.preferences_path_for_root(Path("/my/root")) == Path(
        "/my/root/etc/apt/preferences.d/craft-archives"
    )


# endregion
