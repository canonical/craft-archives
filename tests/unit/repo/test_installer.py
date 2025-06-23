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
import pytest
from craft_archives.repo import installer
from craft_archives.repo.apt_key_manager import AptKeyManager
from craft_archives.repo.apt_preferences_manager import AptPreferencesManager
from craft_archives.repo.apt_sources_manager import AptSourcesManager
from craft_archives.repo.package_repository import (
    PackageRepositoryApt,
    PackageRepositoryAptPPA,
    PackageRepositoryAptUCA,
)


def test_unmarshal_repositories():
    data = [
        {
            "type": "apt",
            "ppa": "test/somerepo",
        },
        {
            "type": "apt",
            "url": "https://some/url",
            "key-id": "ABCDE12345" * 4,
        },
        {
            "type": "apt",
            "ppa": "test/somerepo",
            "priority": -1,
        },
        {
            "type": "apt",
            "url": "https://some/url",
            "key-id": "ABCDE12345" * 4,
            "priority": -2,
        },
        {
            "type": "apt",
            "cloud": "antelope",
            "pocket": "proposed",
        },
    ]

    pkg_repos = installer._unmarshal_repositories(data)
    assert len(pkg_repos) == 5
    assert isinstance(pkg_repos[0], PackageRepositoryAptPPA)
    assert pkg_repos[0].ppa == "test/somerepo"
    assert pkg_repos[0].priority is None
    assert isinstance(pkg_repos[1], PackageRepositoryApt)
    assert pkg_repos[1].url == "https://some/url"
    assert pkg_repos[1].key_id == "ABCDE12345" * 4
    assert pkg_repos[1].priority is None
    assert isinstance(pkg_repos[2], PackageRepositoryAptPPA)
    assert isinstance(pkg_repos[3], PackageRepositoryApt)
    assert pkg_repos[2].priority == -1
    assert pkg_repos[3].priority == -2
    assert isinstance(pkg_repos[4], PackageRepositoryAptUCA)
    assert pkg_repos[4].cloud == "antelope"
    assert pkg_repos[4].pocket.value == "proposed"


@pytest.fixture
def manager_mocks(mocker, tmp_path):
    mock_install_package_repository_key = mocker.patch.object(
        AptKeyManager,
        "install_package_repository_key",
        return_value=True,
    )
    mock_install_package_repository_sources = mocker.patch.object(
        AptSourcesManager,
        "install_package_repository_sources",
        return_value=True,
    )
    mock_preferences_add = mocker.patch.object(
        AptPreferencesManager,
        "add",
    )
    mock_preferences_write = mocker.patch.object(
        AptPreferencesManager,
        "write",
        return_value=True,
    )

    repo_dict = {
        "type": "apt",
        "ppa": "test/somerepo",
        "priority": 999,
    }
    repo_ppa = PackageRepositoryAptPPA.unmarshal(repo_dict)
    yield [repo_dict]

    mock_install_package_repository_key.assert_called_once_with(package_repo=repo_ppa)
    mock_install_package_repository_sources.assert_called_once_with(
        package_repo=repo_ppa
    )
    mock_preferences_add.assert_called_once_with(
        pin="release o=LP-PPA-test-somerepo", priority=999
    )
    assert mock_preferences_write.called


def test_install(tmp_path, manager_mocks):
    """Smokish test that checks that installer.install() makes the expected calls."""
    project_repositories = manager_mocks
    assert installer.install(
        project_repositories=project_repositories, key_assets=tmp_path
    )


def test_install_in_root(tmp_path, manager_mocks):
    """Smokish test that checks that installer.install_in_root() makes the expected calls."""
    project_repositories = manager_mocks
    assert installer.install_in_root(
        project_repositories=project_repositories, key_assets=tmp_path, root=tmp_path
    )
