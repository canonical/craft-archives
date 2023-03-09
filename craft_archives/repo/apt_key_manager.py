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

import logging
import pathlib
import subprocess
import tempfile
from typing import Iterable, List, Optional, Union

from . import apt_ppa, errors, package_repository

logger = logging.getLogger(__name__)

# Directory for apt keyrings as recommended by Debian for third-party keyrings.
_KEYRINGS_PATH = pathlib.Path("/etc/apt/keyrings")

# GnuPG command line options that we always want to use.
_GPG_PREFIX = ["gpg", "--batch", "--no-default-keyring"]


def _gnupg_ring(keyring_file: pathlib.Path) -> str:
    """Return a string specifying that ``keyring_file`` is in the binary OpenGPG format.

    This is for use in ``gpg`` commands for APT-related keys.
    """
    return f"gnupg-ring:{keyring_file}"


def _call_gpg(
    *parameters: str,
    keyring: Optional[pathlib.Path] = None,
    base_parameters: Iterable[str] = _GPG_PREFIX,
    stdin: Optional[bytes] = None,
) -> bytes:
    if keyring:
        command = [*base_parameters, "--keyring", f"gnupg-ring:{keyring}", *parameters]
    else:
        command = [*base_parameters, *parameters]
    logger.debug(f"Executing command: {command}")
    env = {"LANG": "C.UTF-8"}
    process = subprocess.run(
        command,
        input=stdin,
        capture_output=True,
        check=True,
        env=env,
    )
    return process.stdout


def _get_key_path(
    key_id: str,
    *,
    is_ascii: bool = False,
    base_path: pathlib.Path = _KEYRINGS_PATH,
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


def _gen_gpg_fingerprints(path: Union[str, pathlib.Path]) -> Iterable[str]:
    """Get the fingerprint of a GPG key by file path.

    :returns: the fingerprint of the first GPG key in the file
    :raises: FileNotFoundError if the file does not exist
    """
    if not pathlib.Path(path).is_file():
        raise FileNotFoundError(f"GPG key file does not exist: {str(path)}")

    response = _call_gpg("--show-keys", str(path)).splitlines(keepends=False)
    for index, line in enumerate(
        response, start=1
    ):  # index will be the next line's index
        if line.startswith(b"pub   "):
            yield response[index].decode().strip()


class AptKeyManager:
    """Manage APT repository keys."""

    def __init__(
        self,
        *,
        keyrings_path: pathlib.Path = _KEYRINGS_PATH,
        key_assets: pathlib.Path,
    ) -> None:
        self._keyrings_path = keyrings_path
        self._key_assets = key_assets

    def find_asset_with_key_id(self, *, key_id: str) -> Optional[pathlib.Path]:
        """Find snap key asset matching key_id.

        The key asset much be named with the last 8 characters of the key
        identifier, in upper case.

        :param key_id: Key ID to search for.

        :returns: Path of key asset if match found, otherwise None.
        """
        key_path = _get_key_path(
            key_id, is_ascii=True, prefix="", base_path=self._key_assets
        )

        if key_path.exists():
            return key_path

        return None

    @classmethod
    def get_key_fingerprints(cls, *, key: str) -> List[str]:
        """List fingerprints found in specified key.

        Do this by importing the key into a temporary keyring,
        then querying the keyring for fingerprints.

        :param key: Key data (string) to parse.

        :returns: List of key fingerprints/IDs.
        """
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(key.encode())
            temp_file.flush()
            return list(_gen_gpg_fingerprints(temp_file.name))

    @classmethod
    def is_key_installed(
        cls, *, key_id: str, keyring_path: pathlib.Path = _KEYRINGS_PATH
    ) -> bool:
        """Check if specified key_id is installed.

        :param key_id: Key ID to check for.
        :param keyring_path: An optional override to check for the keyring.

        :returns: True if key is installed.
        """
        keyring_file = _get_key_path(key_id, base_path=keyring_path)
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
            # From testing, the gpg call will fail with return code 2 if the key
            # doesn't exist in the keyring, so it's an expected possible case.
            _expected_returncode = 2
            if error.returncode != _expected_returncode:
                logger.warning(f"Unexpected gpg failure: {error.output}")
            logger.warning(
                f"Keyring file {keyring_file!r} does not contain the expected key."
            )
            return False
        else:
            return True

    def install_key(self, *, key: str) -> None:
        """Install given key.

        :param key: Key to install.

        :raises: AptGPGKeyInstallError if unable to install key.
        """
        logger.debug(f"Importing key {key}")
        try:
            fingerprints = self.get_key_fingerprints(key=key)
            if not fingerprints:
                raise errors.AptGPGKeyInstallError(
                    "Invalid GPG key", key=key
                )
            if len(fingerprints) != 1:
                raise errors.AptGPGKeyInstallError(
                    "Key must be a single key, not multiple.", key=key
                )
            keyring_path = _get_key_path(fingerprints[0], base_path=self._keyrings_path)
            _call_gpg("--import", "-", keyring=keyring_path, stdin=key.encode())
        except subprocess.CalledProcessError as error:
            raise errors.AptGPGKeyInstallError(error.output.decode(), key=key)

        # Change the permissions on the file so that APT itself can read it later
        keyring_path.chmod(0o644)
        logger.debug(f"Installed apt repository key:\n{key}")

    def install_key_from_keyserver(
        self, *, key_id: str, key_server: str = "keyserver.ubuntu.com"
    ) -> None:
        """Install key from specified key server.

        :param key_id: Key ID to install.
        :param key_server: Key server to query.

        :raises: AptGPGKeyInstallError if unable to install key.
        """
        keyring_path = _get_key_path(key_id, base_path=self._keyrings_path)
        try:
            with tempfile.TemporaryDirectory() as tmpdir_str:
                # We use a tmpdir because gpg needs a "homedir" to place temporary
                # files into during the download process.
                tmpdir = pathlib.Path(tmpdir_str)
                tmpdir.chmod(0o700)
                _call_gpg(
                    "--homedir",
                    tmpdir_str,
                    "--keyserver",
                    key_server,
                    "--recv-keys",
                    key_id,
                    keyring=keyring_path,
                )
            keyring_path.chmod(0o644)
        except subprocess.CalledProcessError as error:
            raise errors.AptGPGKeyInstallError(
                error.output.decode(), key_id=key_id, key_server=key_server
            )

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
        key_server: Optional[str] = None
        if isinstance(package_repo, package_repository.PackageRepositoryAptPPA):
            key_id = apt_ppa.get_launchpad_ppa_key_id(ppa=package_repo.ppa)
        elif isinstance(package_repo, package_repository.PackageRepositoryApt):
            key_id = package_repo.key_id
            key_server = package_repo.key_server
        else:
            raise RuntimeError(f"unhandled package repo type: {package_repo!r}")

        # Already installed, nothing to do.
        if self.is_key_installed(key_id=key_id):
            return False

        key_path = self.find_asset_with_key_id(key_id=key_id)
        if key_path is not None:
            self.install_key(key=key_path.read_text())
        else:
            if key_server is None:
                key_server = "keyserver.ubuntu.com"
            self.install_key_from_keyserver(key_id=key_id, key_server=key_server)

        return True
