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
#
"""Manage the host's apt source repository configuration."""

import io
import logging
import pathlib
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from craft_archives import os_release, utils

from . import apt_key_manager, apt_ppa, apt_uca, errors, package_repository

logger = logging.getLogger(__name__)

_DEFAULT_SOURCES_DIRECTORY = Path("/etc/apt/sources.list.d")


def _construct_deb822_source(
    *,
    architectures: Optional[List[str]] = None,
    components: Optional[List[str]] = None,
    formats: Optional[List[str]] = None,
    suites: List[str],
    url: str,
    signed_by: pathlib.Path,
) -> str:
    """Construct deb-822 formatted sources string."""
    with io.StringIO() as deb822:
        if formats:
            type_text = " ".join(formats)
        else:
            type_text = "deb"

        print(f"Types: {type_text}", file=deb822)

        print(f"URIs: {url}", file=deb822)

        suites_text = " ".join(suites)
        print(f"Suites: {suites_text}", file=deb822)

        if components:
            components_text = " ".join(components)
            print(f"Components: {components_text}", file=deb822)

        if architectures:
            arch_text = " ".join(architectures)
        else:
            arch_text = utils.get_host_architecture()

        print(f"Architectures: {arch_text}", file=deb822)

        print(f"Signed-By: {str(signed_by)}", file=deb822)

        return deb822.getvalue()


class AptSourcesManager:
    """Manage apt source configuration in /etc/apt/sources.list.d.

    :param sources_list_d: Path to sources.list.d directory.
    """

    # pylint: disable=too-few-public-methods
    def __init__(
        self,
        *,
        sources_list_d: Path = _DEFAULT_SOURCES_DIRECTORY,
        keyrings_dir: Path = apt_key_manager.KEYRINGS_PATH,
    ) -> None:
        self._sources_list_d = sources_list_d
        self._keyrings_dir = keyrings_dir

    def _install_sources(
        self,
        *,
        architectures: Optional[List[str]] = None,
        components: Optional[List[str]] = None,
        formats: Optional[List[str]] = None,
        name: str,
        suites: List[str],
        url: str,
        keyring_path: pathlib.Path,
    ) -> bool:
        """Install sources list configuration.

        Write config to:
        /etc/apt/sources.list.d/snapcraft-<name>.sources

        :returns: True if configuration was changed.
        """
        if keyring_path and not keyring_path.is_file():
            raise errors.AptGPGKeyringError(keyring_path)

        config = _construct_deb822_source(
            architectures=architectures,
            components=components,
            formats=formats,
            suites=suites,
            url=url,
            signed_by=keyring_path,
        )

        if name not in ["default", "default-security"]:
            name = "snapcraft-" + name

        config_path = self._sources_list_d / f"{name}.sources"
        if config_path.exists() and config_path.read_text() == config:
            # Already installed and matches, nothing to do.
            logger.debug(f"Ignoring unchanged sources: {config_path!s}")
            return False

        config_path.write_text(config)
        logger.debug(f"Installed sources: {config_path!s}")
        return True

    def _install_sources_apt(
        self, *, package_repo: package_repository.PackageRepositoryApt
    ) -> bool:
        """Install repository configuration.

        1) First check to see if package repo is implied path,
           or "bare repository" config.  This is indicated when no
           path, components, or suites are indicated.
        2) If path is specified, convert path to a suite entry,
           ending with "/".

        Relatedly, this assumes all of the error-checking has been
        done already on the package_repository object in a proper
        fashion, but do some sanity checks here anyways.

        :returns: True if source configuration was changed.
        """
        if (
            not package_repo.path
            and not package_repo.components
            and not package_repo.suites
        ):
            suites = ["/"]
        elif package_repo.path:
            # Suites denoting exact path must end with '/'.
            path = package_repo.path
            if not path.endswith("/"):
                path += "/"
            suites = [path]
        elif package_repo.suites:
            suites = package_repo.suites
            if not package_repo.components:
                raise RuntimeError("no components with suite")
        else:
            raise RuntimeError("no suites or path")

        if package_repo.name:
            name = package_repo.name
        else:
            name = re.sub(r"\W+", "_", package_repo.url)

        keyring_path = apt_key_manager.get_keyring_path(
            package_repo.key_id, base_path=self._keyrings_dir
        )

        return self._install_sources(
            architectures=package_repo.architectures,
            components=package_repo.components,
            formats=package_repo.formats,
            name=name,
            suites=suites,
            url=package_repo.url,
            keyring_path=keyring_path,
        )

    def _install_sources_ppa(
        self, *, package_repo: package_repository.PackageRepositoryAptPPA
    ) -> bool:
        """Install PPA formatted repository.

        Create a sources list config by:
        - Looking up the codename of the host OS and using it as the "suites"
          entry.
        - Formulate deb URL to point to PPA.
        - Enable only "deb" formats.

        :returns: True if source configuration was changed.
        """
        owner, name = apt_ppa.split_ppa_parts(ppa=package_repo.ppa)
        codename = os_release.OsRelease().version_codename()

        key_id = apt_ppa.get_launchpad_ppa_key_id(ppa=package_repo.ppa)
        keyring_path = apt_key_manager.get_keyring_path(
            key_id, base_path=self._keyrings_dir
        )

        return self._install_sources(
            components=["main"],
            formats=["deb"],
            name=f"ppa-{owner}_{name}",
            suites=[codename],
            url=f"http://ppa.launchpad.net/{owner}/{name}/ubuntu",
            keyring_path=keyring_path,
        )

    def _install_sources_uca(
        self, *, package_repo: package_repository.PackageRepositoryAptUCA
    ) -> bool:
        """Install UCA formatted repository.

        Create a sources list config by:
        - Looking up the codename of the host OS and using it as the "suites"
          entry.
        - Formulate deb URL to point to UCA.
        - Enable only "deb" formats.

        :returns: True if source configuration was changed.
        """
        cloud = package_repo.cloud
        pocket = package_repo.pocket

        codename = os_release.OsRelease().version_codename()
        apt_uca.check_release_compatibility(codename, cloud, pocket)

        key_id = package_repository.UCA_KEY_ID
        keyring_path = apt_key_manager.get_keyring_path(
            key_id, base_path=self._keyrings_dir
        )
        return self._install_sources(
            components=["main"],
            formats=["deb"],
            name=f"cloud-{cloud}",
            suites=[f"{codename}-{pocket}/{cloud}"],
            url=package_repository.UCA_ARCHIVE,
            keyring_path=keyring_path,
        )

    def install_package_repository_sources(
        self,
        *,
        package_repo: package_repository.PackageRepository,
    ) -> bool:
        """Install configured package repositories.

        :param package_repo: Repository to install the source configuration for.

        :returns: True if source configuration was changed.
        """
        logger.debug(f"Processing repo: {package_repo!r}")
        if isinstance(package_repo, package_repository.PackageRepositoryAptPPA):
            return self._install_sources_ppa(package_repo=package_repo)

        if isinstance(package_repo, package_repository.PackageRepositoryAptUCA):
            return self._install_sources_uca(package_repo=package_repo)

        if isinstance(package_repo, package_repository.PackageRepositoryApt):
            changed = self._install_sources_apt(package_repo=package_repo)
            architectures = package_repo.architectures
            if changed and architectures:
                _add_architecture(architectures)
            return changed

        raise RuntimeError(f"unhandled package repository: {package_repository!r}")


def _add_architecture(architectures: List[str]) -> None:
    """Add package repository architecture."""
    for arch in architectures:
        logger.info(f"Add repository architecture: {arch}")
        subprocess.run(["dpkg", "--add-architecture", arch], check=True)
