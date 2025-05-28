# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2019-2023 Canonical Ltd.
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

"""Package repository installer."""

import pathlib
from typing import Any

from . import errors
from .apt_key_manager import AptKeyManager
from .apt_preferences_manager import AptPreferencesManager
from .apt_sources_manager import AptSourcesManager
from .package_repository import (
    PackageRepository,
    PackageRepositoryApt,
    PackageRepositoryAptPPA,
    PackageRepositoryAptUCA,
)


def install(
    project_repositories: list[dict[str, Any]], *, key_assets: pathlib.Path
) -> bool:
    """Add package repositories to the host system.

    :param project_repositories: A list of package repositories to install.
    :param key_assets: The directory containing repository keys.

    :return: Whether a package list refresh is required.
    """
    return _install_repos(
        project_repositories=project_repositories, key_assets=key_assets
    )


def install_in_root(
    project_repositories: list[dict[str, Any]],
    root: pathlib.Path,
    *,
    key_assets: pathlib.Path,
) -> bool:
    """Add package repositories to the system located at ``root``.

    :param project_repositories: A list of package repositories to install.
    :param key_assets: The directory containing repository keys.
    :param root: The directory containing the Apt-based system installation.

    :return: Whether a package list refresh is required.
    """
    return _install_repos(
        project_repositories=project_repositories, root=root, key_assets=key_assets
    )


def _install_repos(
    *,
    project_repositories: list[dict[str, Any]],
    root: pathlib.Path | None = None,
    key_assets: pathlib.Path,
) -> bool:
    keyrings_path = AptKeyManager.keyrings_path_for_root(root)
    key_manager = AptKeyManager(keyrings_path=keyrings_path, key_assets=key_assets)

    sources_list_d = AptSourcesManager.sources_path_for_root(root)
    sources_manager = AptSourcesManager(
        sources_list_d=sources_list_d,
        keyrings_dir=keyrings_path,
        signed_by_root=root,
    )

    preferences_path = AptPreferencesManager.preferences_path_for_root(root)
    preferences_manager = AptPreferencesManager(path=preferences_path)

    package_repositories = _unmarshal_repositories(project_repositories)

    refresh_required = False
    for package_repo in package_repositories:
        refresh_required |= key_manager.install_package_repository_key(
            package_repo=package_repo
        )
        refresh_required |= sources_manager.install_package_repository_sources(
            package_repo=package_repo
        )
        if (
            isinstance(
                package_repo,
                PackageRepositoryApt | PackageRepositoryAptPPA | PackageRepositoryAptUCA,
            )
            and package_repo.priority is not None
        ):
            refresh_required |= preferences_manager.add(
                pin=package_repo.pin, priority=int(package_repo.priority)
            )

    refresh_required |= preferences_manager.write()

    _verify_all_key_assets_installed(key_assets=key_assets, key_manager=key_manager)

    return refresh_required


def _verify_all_key_assets_installed(
    *,
    key_assets: pathlib.Path,
    key_manager: AptKeyManager,
) -> None:
    """Verify all configured key assets are utilized, error if not."""
    for key_asset in key_assets.glob("*"):
        key_id = key_asset.stem
        if not key_manager.is_key_installed(key_id=key_id):
            raise errors.PackageRepositoryError(
                "Found unused key asset {key_asset!r}.",
                details="All configured key assets must be utilized.",
                resolution="Verify key usage and remove all unused keys.",
            )


def _unmarshal_repositories(
    project_repositories: list[dict[str, Any]],
) -> list[PackageRepository]:
    """Create package repositories objects from project data."""
    repositories: list[PackageRepository] = []
    for data in project_repositories:
        pkg_repo: PackageRepository

        if "ppa" in data:
            pkg_repo = PackageRepositoryAptPPA.unmarshal(data)
        elif "cloud" in data:
            pkg_repo = PackageRepositoryAptUCA.unmarshal(data)
        else:
            pkg_repo = PackageRepositoryApt.unmarshal(data)

        repositories.append(pkg_repo)

    return repositories
