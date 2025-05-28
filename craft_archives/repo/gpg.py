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
"""Utilities to interact with gpg."""

import logging
import pathlib
import subprocess
from collections.abc import Iterable

logger = logging.getLogger(__name__)

# GnuPG command line options that we always want to use.
_GPG_PREFIX = ["gpg", "--batch", "--no-default-keyring", "--with-colons"]


def is_key_in_keyring(key_id: str, keyring_file: pathlib.Path) -> bool:
    """Whether the ``keyring_file`` keyring contains the ``key_id`` key."""
    try:
        logger.debug("Listing keys in keyring...")
        call_gpg("--list-keys", key_id, keyring=keyring_file)
    except subprocess.CalledProcessError as error:
        logger.warning(f"gpg error: {error.output.decode()}")
        return False
    else:
        return True


def call_gpg(
    *parameters: str,
    keyring: pathlib.Path | None = None,
    base_parameters: Iterable[str] = _GPG_PREFIX,
    stdin: bytes | None = None,
    log: bool = False,
) -> bytes:
    """Call "gpg" with the appropriate common parameters.

    :return: The process' stdout.
    """
    if keyring:
        command = [*base_parameters, "--keyring", f"gnupg-ring:{keyring}", *parameters]
    else:
        command = [*base_parameters, *parameters]
    logger.debug(f"Executing command: {command}")
    env = {"LANG": "C.UTF-8"}
    try:
        process = subprocess.run(
            command,
            input=stdin,
            capture_output=True,
            check=True,
            env=env,
        )
        if log:
            _log_gpg(process)
        return process.stdout
    except subprocess.CalledProcessError as error:
        if log:
            _log_gpg(error)
        raise


def _log_gpg(
    entity: subprocess.CompletedProcess[bytes] | subprocess.CalledProcessError,
) -> None:
    if entity.stdout:
        logger.debug("gpg stdout:")
        logger.debug(entity.stdout.decode())
    if entity.stderr:
        logger.debug("gpg stderr:")
        logger.debug(entity.stderr.decode())
