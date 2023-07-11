# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2015-2023 Canonical Ltd.
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

"""APT key management helpers."""

# pyright: reportMissingTypeStubs=false
from __future__ import annotations

import logging
import pathlib
import subprocess
import tempfile
from contextlib import contextmanager
from typing import Iterable, Iterator, List, Optional, Union

from . import apt_ppa, errors, package_repository

logger = logging.getLogger(__name__)

DEFAULT_APT_KEYSERVER = "keyserver.ubuntu.com"

# Directory for apt keyrings as recommended by Debian for third-party keyrings.
KEYRINGS_PATH = pathlib.Path("/etc/apt/keyrings")

# GnuPG command line options that we always want to use.
_GPG_PREFIX = ["gpg", "--batch", "--no-default-keyring", "--with-colons"]


def _call_gpg(
    *parameters: str,
    keyring: Optional[pathlib.Path] = None,
    base_parameters: Iterable[str] = _GPG_PREFIX,
    stdin: Optional[bytes] = None,
    log: bool = False,
) -> bytes:
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
    except subprocess.CalledProcessError as error:
        if log:
            _log_gpg(error)
        raise
    else:
        return process.stdout


def get_keyring_path(
    key_id: str,
    *,
    is_ascii: bool = False,
    base_path: pathlib.Path = KEYRINGS_PATH,
    prefix: str = "craft-",
) -> pathlib.Path:
    """Get a Path object where we would expect to find a key.

    :param key_id: The key ID for the keyring file.
    :param base_path: The directory for the key.
    :param prefix: The prefix fer the keyfile
    :param is_ascii: Whether the file is ASCII-armored (.asc suffix)

    :returns: A Path object matching the expected filename
    """
    file_base = prefix + key_id[-8:].upper()
    return base_path.joinpath(file_base).with_suffix(".asc" if is_ascii else ".gpg")


def _configure_keyring_file(keyring_file: pathlib.Path) -> None:
    """Configure a newly created keyring file."""
    # Change the permissions on the file so that APT itself can read it later
    keyring_file.chmod(0o644)
    # Also remove the backup file, if gpg created it
    backup = keyring_file.with_suffix(keyring_file.suffix + "~")
    backup.unlink(missing_ok=True)


class AptKeyManager:
    """Manage APT repository keys."""

    def __init__(
        self,
        *,
        keyrings_path: Optional[pathlib.Path] = None,
        key_assets: pathlib.Path,
    ) -> None:
        self._keyrings_path = keyrings_path or KEYRINGS_PATH
        self._key_assets = key_assets

    def find_asset_with_key_id(self, *, key_id: str) -> Optional[pathlib.Path]:
        """Find snap key asset matching key_id.

        The key asset much be named with the last 8 characters of the key
        identifier, in upper case.

        :param key_id: Key ID to search for.

        :returns: Path of key asset if match found, otherwise None.
        """
        key_path = get_keyring_path(
            key_id, is_ascii=True, prefix="", base_path=self._key_assets
        )

        if key_path.exists():
            return key_path

        return None

    @classmethod
    def keyrings_path_for_root(
        cls, root: Optional[pathlib.Path] = None
    ) -> pathlib.Path:
        """Get the location for Apt keyrings with ``root`` as the system root.

        :param root: The optional system root to consider, or None to assume the standard
          system root "/".
        """
        if root is None:
            return KEYRINGS_PATH
        return root / "etc/apt/keyrings"

    @classmethod
    def get_key_fingerprints(cls, *, key: Union[str, bytes]) -> List[str]:
        """List fingerprints found in the specified key.

        Fingerprints for subkeys are not returned. Fingerprints for primary keys are
        returned in the order that they are found, even if the keys are expired.

        :param key: Key data (string) to parse.

        :returns: List of key fingerprints/IDs.
        """
        key_bytes = key.encode() if isinstance(key, str) else key

        with _temporary_home_dir() as tmpdir:
            response = _call_gpg(
                "--homedir",
                str(tmpdir),
                "--import-options",
                "show-only",
                "--import",
                stdin=key_bytes,
            ).splitlines()
        fingerprints: List[str] = []
        # Only export fingerprints for primary keys.
        is_primary = False
        for line in response:
            if line.startswith(b"pub:"):
                is_primary = True
            elif line.startswith(b"sub:"):
                is_primary = False
            if line.startswith(b"fpr:") and is_primary:
                fingerprints.append(line[4:].decode().strip(":"))
        return fingerprints

    def is_key_installed(self, *, key_id: str) -> bool:
        """Check if specified key_id is installed.

        :param key_id: Key ID to check for. The key will be looked for in the
          AptKeyManager's configured keyrings path.

        :returns: True if key is installed.
        """
        keyring_file = get_keyring_path(key_id, base_path=self._keyrings_path)
        # Check if the keyring file exists first, otherwise the gpg check itself
        # creates it.
        if not keyring_file.is_file():
            logger.debug(f"Keyring file not found: {keyring_file}")
            return False

        # Ensure the keyring file contains the correct key
        try:
            logger.debug("Listing keys in keyring...")
            _call_gpg("--list-keys", key_id, keyring=keyring_file)
        except subprocess.CalledProcessError as error:
            logger.warning(f"gpg error: {error.output.decode()}")
            return False
        else:
            return True

    def install_key(self, *, key: str, key_id: Optional[str] = None) -> None:
        """Install given key.

        :param key: Contents of key to install.
        :param key_id: The optional fingerprint of the desired primary key in ``key``.
            If provided, this fingerprint will be checked after the import is done to
            ensure that it is present, and the imported file will use this fingerprint
            for its filename (short id).

        :raises: AptGPGKeyInstallError if unable to install key.
        """
        logger.debug(f"Importing key {key}")
        fingerprints = self.get_key_fingerprints(key=key)
        if not fingerprints:
            raise errors.AptGPGKeyInstallError("Invalid GPG key", key=key)

        if key_id and key_id not in fingerprints:
            raise errors.AptGPGKeyInstallError(
                "Desired key_id not found in fingerprints", key=key
            )

        self._create_keyrings_path()
        target_id = key_id or fingerprints[0]
        keyring_path = get_keyring_path(target_id, base_path=self._keyrings_path)

        # Note: use a temporary homedir because otherwise local configuration can influence
        # how GPG behaves when importing keys.
        with _temporary_home_dir() as tmpdir:
            try:
                _call_gpg(
                    "--homedir",
                    str(tmpdir),
                    "--import",
                    "-",
                    keyring=keyring_path,
                    stdin=key.encode(),
                    log=True,
                )
            except subprocess.CalledProcessError as error:
                raise errors.AptGPGKeyInstallError(
                    error.stderr.decode(), key=key
                ) from error

        if key_id is not None:
            # Make sure the imported key has the expected key_id
            imported_keyring = keyring_path.read_bytes()
            if key_id not in self.get_key_fingerprints(key=imported_keyring):
                raise errors.AptGPGKeyInstallError(f"key-id {key_id} not imported.")

        _configure_keyring_file(keyring_path)
        logger.debug(f"Installed apt repository key:\n{key_id or key}")

    def install_key_from_keyserver(
        self, *, key_id: str, key_server: str = DEFAULT_APT_KEYSERVER
    ) -> None:
        """Install key from specified key server.

        :param key_id: Key ID to install.
        :param key_server: Key server to query.

        :raises: AptGPGKeyInstallError if unable to install key.
        """
        self._create_keyrings_path()
        keyring_path = get_keyring_path(key_id, base_path=self._keyrings_path)
        try:
            with _temporary_home_dir() as tmpdir:
                # We use a tmpdir because gpg needs a "homedir" to place temporary
                # files into during the download process.
                _call_gpg(
                    "--homedir",
                    str(tmpdir),
                    "--keyserver",
                    key_server,
                    "--recv-keys",
                    key_id,
                    keyring=keyring_path,
                )
            _configure_keyring_file(keyring_path)
        except subprocess.CalledProcessError as error:
            raise errors.AptGPGKeyInstallError(
                error.output.decode(), key_id=key_id, key_server=key_server
            ) from error

    def install_package_repository_key(
        self, *, package_repo: package_repository.PackageRepository
    ) -> bool:
        """Install required key for specified package repository.

        For both PPA and other Apt package repositories:
        1) If key is already installed, return False.
        2) Install key from local asset, if available.
        3) Install key from key server, if available. An unspecified
           keyserver will default to using keyserver.ubuntu.com.

        :param package_repo: Apt PackageRepository configuration.

        :returns: True if key configuration was changed. False if
            key already installed.

        :raises: AptGPGKeyInstallError if unable to install key.
        """
        key_server = DEFAULT_APT_KEYSERVER
        if isinstance(package_repo, package_repository.PackageRepositoryAptPPA):
            key_id = apt_ppa.get_launchpad_ppa_key_id(ppa=package_repo.ppa)
        elif isinstance(package_repo, package_repository.PackageRepositoryAptUCA):
            key_id = package_repository.UCA_KEY_ID
        elif isinstance(package_repo, package_repository.PackageRepositoryApt):
            key_id = package_repo.key_id
            if package_repo.key_server:
                key_server = package_repo.key_server
        else:
            raise TypeError(f"unhandled package repo type: {package_repo!r}")

        # Already installed, nothing to do.
        if self.is_key_installed(key_id=key_id):
            return False

        # If the keyring exists but does not contain the key, remove it and
        # install a fresh one.
        keyring_path = get_keyring_path(key_id, base_path=self._keyrings_path)
        if keyring_path.parent.is_dir():
            keyring_path.unlink(missing_ok=True)

        key_path = self.find_asset_with_key_id(key_id=key_id)
        if key_path is not None:
            self.install_key(key=key_path.read_text(), key_id=key_id)
        else:
            self.install_key_from_keyserver(key_id=key_id, key_server=key_server)

        return True

    def _create_keyrings_path(self) -> None:
        """Create the directory that will contain the keys, if necessary."""
        if not self._keyrings_path.exists():
            logger.debug(
                f"Keyrings location {self._keyrings_path} doesn't exist; Attempting to create it."
            )
            self._keyrings_path.mkdir(mode=0o755, parents=False)


@contextmanager
def _temporary_home_dir() -> Iterator[pathlib.Path]:
    """Yield a temporary directory with proper permissions for gpg."""
    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = pathlib.Path(tmpdir_str)
        tmpdir.chmod(0o700)
        yield tmpdir


def _log_gpg(
    entity: Union[subprocess.CompletedProcess[bytes], subprocess.CalledProcessError]
) -> None:
    if entity.stdout:
        logger.debug("gpg stdout:")
        logger.debug(entity.stdout.decode())
    if entity.stderr:
        logger.debug("gpg stderr:")
        logger.debug(entity.stderr.decode())
