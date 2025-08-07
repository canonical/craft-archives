# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2022-2023 Canonical Ltd.
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

"""Package repository error definitions."""

import pathlib
from typing import Any, Literal

from craft_archives.errors import ArchivesError


class PackageRepositoryError(ArchivesError):
    """Package repository error base."""


class PackageRepositoryValidationError(PackageRepositoryError):
    """Package repository is invalid."""

    def __init__(
        self,
        url: str,
        brief: str,
        details: str | None = None,
        resolution: str | None = None,
    ) -> None:
        super().__init__(
            f"Invalid package repository for {url!r}: {brief}",
            details=details,
            resolution=resolution,
        )


class AptPreferencesError(PackageRepositoryError):
    """Apt preferences are invalid."""

    def __init__(
        self,
        component: Literal["pin", "priority"],
        value: Any | None = None,  # noqa: ANN401 (no use of Any)
        details: str | None = None,
        resolution: str | None = None,
    ) -> None:
        super().__init__(
            brief=f"Invalid repository preference {component}",
            details=details or f"Invalid value: {value!r}",
            resolution=resolution,
        )


class AptPPAInstallError(PackageRepositoryError):
    """Installation of a PPA repository failed."""

    def __init__(self, ppa: str, reason: str) -> None:
        super().__init__(
            f"Failed to install PPA {ppa!r}: {reason}",
            resolution="Verify PPA is correct and try again",
        )


class AptUCAInstallError(PackageRepositoryError):
    """Installation of an UCA repository failed."""

    def __init__(self, cloud: str, pocket: str, reason: str) -> None:
        super().__init__(
            f"Failed to install UCA '{cloud}/{pocket}': {reason}",
            resolution="Verify UCA is correct and try again",
        )


class AptGPGKeyringError(PackageRepositoryError):
    """GPG keyring for repository does not exist or not valid."""

    def __init__(self, keyring_path: pathlib.Path) -> None:
        super().__init__(
            "Could not find keyring file for repository.",
            f"Keyring file does not exist or is invalid: {keyring_path}",
            "Ensure the keyring is installed in the correct path.",
        )


GPG_TIMEOUT_MESSAGE = "gpg: keyserver receive failed: Connection timed out"


class AptGPGKeyInstallError(PackageRepositoryError):
    """Installation of GPG key failed."""

    def __init__(
        self,
        output: str,
        *,
        key: str | None = None,
        key_id: str | None = None,
        key_server: str | None = None,
    ) -> None:
        """Convert gpg's error into a more user-friendly message."""
        message = output.strip()

        # Improve error messages that we can.
        if (
            "gpg: keyserver receive failed: No data" in message
            and key_id
            and key_server
        ):
            message = f"GPG key {key_id!r} not found on key server {key_server!r}"
        elif (
            "gpg: keyserver receive failed: Server indicated a failure" in message
            and key_server
        ):
            message = f"unable to establish connection to key server {key_server!r}"
        elif GPG_TIMEOUT_MESSAGE in message and key_server:
            message = (
                f"unable to establish connection to key server {key_server!r} "
                f"(connection timed out)"
            )

        details = ""
        if key:
            details += f"GPG key:\n{key}\n"
        if key_id:
            details += f"GPG key ID: {key_id}\n"
        if key_server:
            details += f"GPG key server: {key_server}"

        super().__init__(
            f"Failed to install GPG key: {message}",
            details=details,
            resolution="Verify any configured GPG keys",
        )


class SourcesKeyConflictError(PackageRepositoryError):
    """A requested key-id conflicts with existing sources' keys."""

    def __init__(
        self,
        *,
        requested_key_id: str,
        requested_url: str,
        conflict_keyring: str,
        conflicting_source: pathlib.Path,
    ) -> None:
        message = (
            f"The key {requested_key_id!r} for the repository with url "
            f"{requested_url!r} conflicts with a source in '{conflicting_source}', "
            f"which is signed by {conflict_keyring!r}."
        )

        super().__init__(
            message, resolution="Check the key-id of requested repositories."
        )
