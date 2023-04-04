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
from craft_archives.repo import errors
from craft_archives.repo.projects import (
    Apt,
    AptDeb,
    AptPPA,
    AptUCA,
    validate_repository,
)


@pytest.fixture
def ppa_dict():
    return {"type": "apt", "ppa": "test/somerepo"}


@pytest.fixture
def uca_dict():
    return {"type": "apt", "cloud": "antelope", "pocket": "updates"}


class TestAptPPAValidation:
    """AptPPA field validation."""

    @pytest.mark.parametrize(
        "priority", ["always", "prefer", "defer", 1000, 990, 500, 100, -1, None]
    )
    def test_apt_ppa_valid(self, priority, ppa_dict):
        if priority is not None:
            ppa_dict["priority"] = priority
        apt_ppa = AptPPA.unmarshal(ppa_dict)
        assert apt_ppa.type == "apt"
        assert apt_ppa.ppa == "test/somerepo"
        assert apt_ppa.priority == priority

    def test_apt_ppa_repository_invalid(self):
        repo = {
            "ppa": "test/somerepo",
        }
        error = r"type\s+field required"
        with pytest.raises(pydantic.ValidationError, match=error):
            AptPPA.unmarshal(repo)

    def test_project_package_ppa_repository_bad_type(self):
        repo = {
            "type": "invalid",
            "ppa": "test/somerepo",
        }
        error = "unexpected value; permitted: 'apt'"
        with pytest.raises(pydantic.ValidationError, match=error):
            AptPPA.unmarshal(repo)


class TestAptUCAValidation:
    """AptUCA field validation."""

    @pytest.mark.parametrize(
        "priority", ["always", "prefer", "defer", 1000, 990, 500, 100, -1, None]
    )
    def test_apt_uca_valid(self, priority, uca_dict):
        if priority is not None:
            uca_dict["priority"] = priority
        apt_uca = AptUCA.unmarshal(uca_dict)
        assert apt_uca.type == "apt"
        assert apt_uca.cloud == "antelope"
        assert apt_uca.priority == priority

    def test_apt_uca_repository_invalid(self):
        repo = {
            "cloud": "antelope",
        }
        error = r"type\s+field required"
        with pytest.raises(pydantic.ValidationError, match=error):
            AptUCA.unmarshal(repo)

    def test_project_package_uca_repository_bad_type(self):
        repo = {
            "type": "invalid",
            "cloud": "antelope",
        }
        error = "unexpected value; permitted: 'apt'"
        with pytest.raises(pydantic.ValidationError, match=error):
            AptUCA.unmarshal(repo)


class TestAptDebValidation:
    """AptDeb field validation."""

    @pytest.mark.parametrize(
        "priority", ["always", "prefer", "defer", 1000, 990, 500, 100, -1, None]
    )
    @pytest.mark.parametrize(
        "repo",
        [
            {
                "type": "apt",
                "url": "https://some/url",
                "key-id": "BCDEF12345" * 4,
            },
            {
                "type": "apt",
                "url": "https://some/url",
                "key-id": "BCDEF12345" * 4,
                "formats": ["deb"],
                "components": ["some", "components"],
                "key-server": "my-key-server",
                "path": "my/path",
                "suites": ["some", "suites"],
            },
        ],
    )
    def test_apt_deb_valid(self, repo, priority):
        if priority is not None:
            repo["priority"] = priority
        apt_deb = AptDeb.unmarshal(repo)
        assert apt_deb.type == "apt"
        assert apt_deb.url == "https://some/url"
        assert apt_deb.key_id == "BCDEF12345" * 4
        assert apt_deb.formats == (["deb"] if "formats" in repo else None)
        assert apt_deb.components == (
            ["some", "components"] if "components" in repo else None
        )
        assert apt_deb.key_server == ("my-key-server" if "key-server" in repo else None)
        assert apt_deb.path == ("my/path" if "path" in repo else None)
        assert apt_deb.suites == (["some", "suites"] if "suites" in repo else None)

    @pytest.mark.parametrize(
        "key_id,error",
        [
            ("ABCDE12345" * 4, None),
            ("KEYID12345" * 4, "string does not match regex"),
            ("abcde12345" * 4, "string does not match regex"),
        ],
    )
    def test_apt_deb_key_id(self, key_id, error):
        repo = {
            "type": "apt",
            "url": "https://some/url",
            "key-id": key_id,
        }

        if not error:
            apt_deb = AptDeb.unmarshal(repo)
            assert apt_deb.key_id == key_id
        else:
            with pytest.raises(pydantic.ValidationError, match=error):
                AptDeb.unmarshal(repo)

    @pytest.mark.parametrize(
        "formats",
        [
            ["deb"],
            ["deb-src"],
            ["deb", "deb-src"],
            ["_invalid"],
        ],
    )
    def test_apt_deb_formats(self, formats):
        repo = {
            "type": "apt",
            "url": "https://some/url",
            "key-id": "ABCDE12345" * 4,
            "formats": formats,
        }

        if formats != ["_invalid"]:
            apt_deb = AptDeb.unmarshal(repo)
            assert apt_deb.formats == formats
        else:
            error = ".*unexpected value; permitted: 'deb', 'deb-src'"
            with pytest.raises(pydantic.ValidationError, match=error):
                AptDeb.unmarshal(repo)


# region Generic Apt model tests
@pytest.mark.parametrize(
    "subclass,value",
    [
        (AptPPA, {"type": "apt", "ppa": "ppa/ppa"}),
        (
            AptDeb,
            {
                "type": "apt",
                "url": "https://deb.repo",
                "key_id": "A" * 40,
                "formats": ["deb"],
            },
        ),
        (AptUCA, {"type": "apt", "cloud": "antelope"}),
    ],
)
def test_apt_unmarshal_returns_correct_subclass(subclass, value):
    model = Apt.unmarshal(value)

    assert isinstance(model, subclass)


@pytest.mark.parametrize(
    "error_class,kwargs",
    [
        (errors.PackageRepositoryValidationError, {"type": "apt", "priority": 0}),
    ],
)
def test_validation_failure(error_class, kwargs):
    with pytest.raises(error_class):
        Apt(**kwargs)


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
        validate_repository("invalid repository")  # type: ignore


def test_validate_repository_empty_dict():
    with pytest.raises(pydantic.ValidationError):
        validate_repository({})


# endregion
