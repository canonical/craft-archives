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

import pydantic
import pytest
from craft_archives.repo.projects import validate_repository


# region validate_repository tests
@pytest.mark.parametrize(
    "repo",
    [
        {"type": "apt", "ppa": "ppa/ppa"},
        {
            "type": "apt",
            "url": "https://deb.repo",
            "key-id": "A" * 40,
            "formats": ["deb"],
        },
        {"type": "apt", "cloud": "antelope"},
    ],
)
def test_validate_repository(repo):
    validate_repository(repo)


def test_validate_repository_invalid():
    with pytest.raises(TypeError, match="must be a dictionary"):
        validate_repository("invalid repository")  # type: ignore[reportGeneralTypeIssues]


def test_validate_repository_empty_dict():
    with pytest.raises(pydantic.ValidationError):
        validate_repository({})


# endregion
