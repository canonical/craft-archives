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
"""Manage the host's apt preferences configurations."""
import dataclasses
import io
import logging
import typing
from pathlib import Path

from craft_archives.repo.errors import AptPreferencesError

_DEFAULT_PREFERENCES_FILE = Path("/etc/apt/preferences.d/craft-archives")

_DEFAULT_HEADER = "# This file is managed by craft-archives"

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Preference:
    """A single preference paragraph.

    Matches preferences as defined by apt:
    https://manpages.debian.org/bullseye/apt/apt_preferences.5.en.html
    """

    pin: str
    priority: int

    @classmethod
    def from_string(cls, input_str: str) -> "Preference":
        """Create a Preference object from a preferences compliant string.

        :param input_str: The string containing a preferences paragraph
        :returns: a single Preference object
        :raises: ValueError if unknown
        """
        lines = input_str.splitlines(keepends=False)
        pin, priority = None, None
        for line in lines:
            if not line or line.startswith("#"):
                continue
            key, value = line.split(":", maxsplit=1)
            key, value = key.strip().lower(), value.strip()
            if key == "pin":
                pin = value
            elif key == "pin-priority":
                priority = int(value)
            else:
                logger.warning(f"Unknown preference line: {line!r}")
        if not pin:
            raise AptPreferencesError(
                component="pin",
                value=pin,
                resolution="Remove or update preferences file.",
            )
        if not priority:
            raise AptPreferencesError(
                component="priority",
                value=priority,
                resolution="Remove or update preferences file.",
            )
        return cls(pin=pin, priority=priority)

    def __post_init__(self) -> None:
        if self.priority == 0:
            raise AptPreferencesError(
                component="pin",
                details="Pin-Priority cannot be zero.",
                resolution="Check pin values for repositories.",
            )

    def to_file(self, file: typing.TextIO) -> None:
        """Write this preference to the opened file-like object provided.

        :param file: A file-like object with text input.
        """
        print("Package: *", file=file)
        print(f"Pin: {self.pin}", file=file)
        print(f"Pin-Priority: {self.priority}", file=file)
        print("", file=file)  # Empty line to start a new paragraph.


class AptPreferencesManager:
    """Manage an apt preferences file.

    :param path: Path to the preferences file
    """

    def __init__(
        self, *, path: Path = _DEFAULT_PREFERENCES_FILE, header: str = _DEFAULT_HEADER
    ) -> None:
        self._header = header
        self._path = path
        self._preferences: typing.List[Preference] = []

        self._read()

    def _read(self) -> None:
        """Read the preferences file and populate Preferences objects."""
        if not self._path.exists():
            logger.debug("No preferences read.")
            return
        paragraphs = self._path.read_text().split("\n\n")
        for paragraph in paragraphs:
            # Strip and check for contents to ensure no empty paragraphs are included.
            if not paragraph.strip():
                continue
            self._preferences.append(Preference.from_string(paragraph))
        logger.debug(f"{len(self._preferences)} pin preferences read.")

    def write(self) -> bool:
        """Write the preferences file from the given preferences.

        :returns: True if the preferences file was changed.
        """
        with io.StringIO() as config:
            print(self._header, file=config)
            for preference in self._preferences:
                preference.to_file(config)

            config_str = config.getvalue()

        if self._path.exists() and self._path.read_text() == config_str:
            logger.debug(f"Ignoring unchanged preferences: {self._path!s}")
            return False

        self._path.write_text(config_str)
        return True

    def add(self, *, pin: str, priority: int) -> bool:
        """Add a preference.

        :returns: True if the preference was added, False if already existed.
        """
        preference = Preference(pin, priority)
        if preference in self._preferences:
            return False
        self._preferences.append(preference)
        return True
