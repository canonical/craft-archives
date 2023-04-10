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

from craft_archives.repo import installer
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
    assert pkg_repos[4].pocket == "proposed"
