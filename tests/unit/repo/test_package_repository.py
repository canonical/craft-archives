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
import pydantic
import pytest
from craft_archives.repo import errors
from craft_archives.repo.package_repository import (
    PackageRepository,
    PackageRepositoryApt,
    PackageRepositoryAptPPA,
    PackageRepositoryAptUCA,
)

# pyright: reportGeneralTypeIssues=false
# pyright: reportCallIssue=information

# region Test data and fixtures
BASIC_PPA_MARSHALLED = {"type": "apt", "ppa": "test/foo", "priority": 123}
BASIC_UCA_MARSHALLED = {
    "type": "apt",
    "cloud": "antelope",
    "pocket": "updates",
    "priority": 123,
}
BASIC_APT_MARSHALLED = {
    "architectures": ["amd64", "i386"],
    "components": ["main", "multiverse"],
    "formats": ["deb", "deb-src"],
    "key-id": "A" * 40,
    "key-server": "keyserver.ubuntu.com",
    "suites": ["xenial", "xenial-updates"],
    "type": "apt",
    "url": "http://archive.ubuntu.com/ubuntu",
    "priority": 123,
}


@pytest.fixture()
def apt_repository():
    return PackageRepositoryApt(
        type="apt",
        architectures=["amd64", "i386"],
        components=["main", "multiverse"],
        formats=["deb", "deb-src"],
        key_id="A" * 40,
        key_server="keyserver.ubuntu.com",
        suites=["xenial", "xenial-updates"],
        url="http://archive.ubuntu.com/ubuntu",
        priority=123,
    )


# endregion
# region PackageRepositoryApt
def create_apt(**kwargs) -> PackageRepositoryApt:
    return PackageRepositoryApt(type="apt", **kwargs)


def test_apt_name():
    repo = create_apt(
        key_id="A" * 40,
        url="http://archive.ubuntu.com/ubuntu",
    )
    assert repo.name == "http_archive_ubuntu_com_ubuntu"


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
            "path": "my/path",
        },
        {
            "type": "apt",
            "url": "https://some/url",
            "key-id": "BCDEF12345" * 4,
            "formats": ["deb"],
            "components": ["some", "components"],
            "key-server": "my-key-server",
            "suites": ["some", "suites"],
        },
        {  # File URLs. See: https://github.com/canonical/craft-archives/issues/92
            "type": "apt",
            "url": "file:///tmp/apt-repo",
            "path": "my/path",
            "key-id": "BCDEF12345" * 4,
        },
    ],
)
def test_apt_valid(repo, priority):
    if priority is not None:
        repo["priority"] = priority
    apt_deb = PackageRepositoryApt.unmarshal(repo)
    assert apt_deb.type == "apt"
    assert apt_deb.url == repo["url"]
    assert apt_deb.key_id == "BCDEF12345" * 4
    assert apt_deb.formats == (["deb"] if "formats" in repo else None)
    assert apt_deb.components == (
        ["some", "components"] if "components" in repo else None
    )
    assert apt_deb.key_server == ("my-key-server" if "key-server" in repo else None)
    assert apt_deb.path == ("my/path" if "path" in repo else None)
    assert apt_deb.suites == (["some", "suites"] if "suites" in repo else None)


@pytest.mark.parametrize(
    "arch", ["amd64", "armhf", "arm64", "i386", "ppc64el", "riscv", "s390x"]
)
def test_apt_valid_architectures(arch):
    package_repo = create_apt(key_id="A" * 40, url="http://test", architectures=[arch])

    assert package_repo.architectures == [arch]


def test_apt_invalid_url():
    with pytest.raises(
        pydantic.ValidationError, match="Invalid URL; URLs must be non-empty strings"
    ):
        create_apt(
            key_id="A" * 40,
            url="",
        )


def test_apt_invalid_path():
    with pytest.raises(
        pydantic.ValidationError, match="Invalid path; Paths must be non-empty strings."
    ):
        create_apt(
            key_id="A" * 40,
            path="",
            url="http://archive.ubuntu.com/ubuntu",
        )


def test_apt_invalid_path_with_suites():
    with pytest.raises(pydantic.ValidationError) as raised:
        create_apt(
            key_id="A" * 40,
            path="/",
            suites=["xenial", "xenial-updates"],
            url="http://archive.ubuntu.com/ubuntu",
        )

    expected_message = (
        "Invalid package repository for 'http://archive.ubuntu.com/ubuntu': "
        "suites ['xenial', 'xenial-updates'] cannot be combined with path '/'"
    )

    err = raised.value
    assert expected_message in str(err)


def test_apt_invalid_path_with_components():
    with pytest.raises(pydantic.ValidationError) as raised:
        create_apt(
            key_id="A" * 40,
            path="/",
            components=["main"],
            url="http://archive.ubuntu.com/ubuntu",
        )

    expected_message = (
        "Invalid package repository for 'http://archive.ubuntu.com/ubuntu': "
        "components ['main'] cannot be combined with path '/'."
    )

    err = raised.value
    assert expected_message in str(err)


def test_apt_invalid_missing_components():
    with pytest.raises(pydantic.ValidationError) as raised:
        create_apt(
            key_id="A" * 40,
            suites=["xenial", "xenial-updates"],
            url="http://archive.ubuntu.com/ubuntu",
        )

    expected_message = (
        "Invalid package repository for 'http://archive.ubuntu.com/ubuntu': "
        "components must be specified when using suites."
    )

    err = raised.value
    assert expected_message in str(err)


def test_apt_invalid_missing_suites():
    with pytest.raises(pydantic.ValidationError) as raised:
        create_apt(
            key_id="A" * 40,
            components=["main"],
            url="http://archive.ubuntu.com/ubuntu",
        )

    expected_message = (
        "Invalid package repository for 'http://archive.ubuntu.com/ubuntu': "
        "suites must be specified when using components."
    )

    err = raised.value
    assert expected_message in str(err)


def test_apt_invalid_suites_as_path():
    with pytest.raises(pydantic.ValidationError) as raised:
        create_apt(
            key_id="A" * 40,
            suites=["my-suite/"],
            url="http://archive.ubuntu.com/ubuntu",
        )

    expected_message = (
        "Invalid package repository for 'http://archive.ubuntu.com/ubuntu': "
        "invalid suite 'my-suite/'. Suites must not end with a '/'."
    )

    err = raised.value
    assert expected_message in str(err)


def test_apt_key_id_valid():
    key_id = "ABCDE12345" * 4
    repo = {
        "type": "apt",
        "url": "https://some/url",
        "key-id": key_id,
    }
    apt_deb = PackageRepositoryApt.unmarshal(repo)
    assert apt_deb.key_id == key_id


@pytest.mark.parametrize(
    "key_id",
    ["KEYID12345" * 4, "abcde12345" * 4],
)
def test_apt_key_id_invalid(key_id):
    repo = {
        "type": "apt",
        "url": "https://some/url",
        "key-id": key_id,
    }

    with pytest.raises(pydantic.ValidationError, match="string does not match regex"):
        PackageRepositoryApt.unmarshal(repo)


@pytest.mark.parametrize(
    "formats",
    [
        ["deb"],
        ["deb-src"],
        ["deb", "deb-src"],
        ["_invalid"],
    ],
)
def test_apt_formats(formats):
    repo = {
        "type": "apt",
        "url": "https://some/url",
        "key-id": "ABCDE12345" * 4,
        "formats": formats,
    }

    if formats != ["_invalid"]:
        apt_deb = PackageRepositoryApt.unmarshal(repo)
        assert apt_deb.formats == formats
    else:
        error = ".*unexpected value; permitted: 'deb', 'deb-src'"
        with pytest.raises(pydantic.ValidationError, match=error):
            PackageRepositoryApt.unmarshal(repo)


def test_apt_marshal(apt_repository):
    assert apt_repository.marshal() == BASIC_APT_MARSHALLED


def test_apt_unmarshal_invalid_extra_keys():
    test_dict = {
        "architectures": ["amd64", "i386"],
        "components": ["main", "multiverse"],
        "formats": ["deb", "deb-src"],
        "key-id": "A" * 40,
        "key-server": "keyserver.ubuntu.com",
        "name": "test-name",
        "suites": ["xenial", "xenial-updates"],
        "type": "apt",
        "url": "http://archive.ubuntu.com/ubuntu",
        "priority": 123,
        "foo": "bar",
        "foo2": "bar",
    }

    with pytest.raises(pydantic.ValidationError):
        PackageRepositoryApt.unmarshal(test_dict)


def test_apt_unmarshal_invalid_type():
    test_dict = {
        "architectures": ["amd64", "i386"],
        "components": ["main", "multiverse"],
        "formats": ["deb", "deb-src"],
        "key-id": "A" * 40,
        "key-server": "keyserver.ubuntu.com",
        "suites": ["xenial", "xenial-updates"],
        "type": "aptx",
        "url": "http://archive.ubuntu.com/ubuntu",
        "priority": "always",
    }

    with pytest.raises(pydantic.ValidationError):
        PackageRepositoryApt.unmarshal(test_dict)


@pytest.mark.parametrize(
    "repository",
    [
        BASIC_APT_MARSHALLED,
        {
            "type": "apt",
            "key-id": "A" * 40,
            "url": "https://example.com",
        },
        {
            "type": "apt",
            "key-id": "A" * 40,
            "url": "https://example.com",
            "architectures": ["spookyarch"],
        },
        {
            "type": "apt",
            "key-id": "A" * 40,
            "url": "https://example.com",
            "components": ["main"],
            "suites": ["jammy"],
        },
        {
            "type": "apt",
            "key-id": "A" * 40,
            "url": "https://example.com",
            "path": "/dev/null",
        },
        {
            "type": "apt",
            "key-id": "A" * 40,
            "url": "https://example.com",
            "components": ["main"],
            "suites": ["jammy"],
            "priority": 1234,
        },
    ],
)
def test_apt_marshal_unmarshal_inverses(repository):
    assert PackageRepositoryApt.unmarshal(repository).marshal() == repository


def test_apt_invalid_priority():
    with pytest.raises(pydantic.ValidationError) as raised:
        create_apt(key_id="A" * 40, url="http://test", priority=0)

    expected_message = (
        "Invalid package repository for 'http://test': "
        "invalid priority: Priority cannot be zero."
    )

    err = raised.value
    assert expected_message in str(err)


@pytest.mark.parametrize(
    ("priority_str", "priority_int"),
    [
        ("always", 1000),
        ("prefer", 990),
        ("defer", 100),
    ],
)
def test_priority_correctly_converted(priority_str, priority_int):
    repo_marshalled = BASIC_APT_MARSHALLED.copy()
    repo_marshalled["priority"] = priority_str
    repo = PackageRepositoryApt.unmarshal(repo_marshalled)

    assert repo.priority == priority_int


@pytest.mark.parametrize(
    ("url", "pin"),
    [
        ("https://example.com/repo", 'origin "example.com"'),
        ("http://archive.debian.org/debian/stable/blah", 'origin "archive.debian.org"'),
        (
            "https://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu/",
            'origin "ppa.launchpadcontent.net"',
        ),
    ],
)
def test_pin_value(url, pin):
    repo_marshalled = BASIC_APT_MARSHALLED.copy()
    repo_marshalled["url"] = url
    repo = PackageRepositoryApt.unmarshal(repo_marshalled)

    assert repo.pin == pin


# endregion
# region PackageRepositoryAptPPA
def create_ppa(**kwargs) -> PackageRepositoryAptPPA:
    return PackageRepositoryAptPPA(type="apt", **kwargs)


def test_ppa_marshal():
    repo = create_ppa(ppa="test/ppa", priority=123)

    assert repo.marshal() == {"type": "apt", "ppa": "test/ppa", "priority": 123}


def test_ppa_invalid_ppa():
    with pytest.raises(pydantic.ValidationError) as raised:
        create_ppa(ppa="")

    expected_message = "Invalid PPA: PPAs must be non-empty strings."
    err = raised.value
    assert expected_message in str(err)


@pytest.mark.parametrize(
    ("priority_str", "priority_int"),
    [
        ("always", 1000),
        ("prefer", 990),
        ("defer", 100),
    ],
)
def test_ppa_priority_correctly_converted(priority_str, priority_int):
    repo_marshalled = BASIC_PPA_MARSHALLED.copy()
    repo_marshalled["priority"] = priority_str
    repo = PackageRepositoryAptPPA.unmarshal(repo_marshalled)

    assert repo.priority == priority_int


@pytest.mark.parametrize(
    ("ppa", "pin"),
    [
        ("ppa/ppa", "release o=LP-PPA-ppa-ppa"),
        ("deadsnakes/nightly", "release o=LP-PPA-deadsnakes-nightly"),
    ],
)
def test_ppa_pin_value(ppa, pin):
    repo = PackageRepositoryAptPPA.unmarshal(
        {
            "type": "apt",
            "ppa": ppa,
        }
    )

    assert repo.pin == pin


# endregion
# region PackageRepository
@pytest.mark.parametrize("data", [None, "some_string"])
def test_unmarshal_validation_error(data):
    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepository.unmarshal(data)

    assert (
        raised.value.details == "Package repository must be a valid dictionary object."
    )


@pytest.mark.parametrize(
    "repositories",
    [
        [],
        pytest.param([BASIC_PPA_MARSHALLED], id="ppa"),
        pytest.param([BASIC_APT_MARSHALLED], id="apt"),
        pytest.param([BASIC_APT_MARSHALLED, BASIC_PPA_MARSHALLED], id="ppa_and_apt"),
    ],
)
def test_marshal_unmarshal_inverses(repositories):
    objects = PackageRepository.unmarshal_package_repositories(repositories)
    marshalled = [repo.marshal() for repo in objects]

    assert marshalled == repositories


def test_unmarshal_package_repositories_list_none():
    assert PackageRepository.unmarshal_package_repositories(None) == []


def test_unmarshal_package_repositories_invalid_data():
    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepository.unmarshal_package_repositories("not-a-list")  # pyright: ignore[reportArgumentType]

    err = raised.value
    assert str(err) == (
        "Invalid package repository for 'not-a-list': invalid list object."
    )
    assert err.details == "Package repositories must be a list of objects."
    assert err.resolution == (
        "Verify 'package-repositories' configuration and ensure that "
        "the correct syntax is used."
    )


# endregion
# region PackageRepositoryAptCloud
def create_uca(**kwargs) -> PackageRepositoryAptUCA:
    return PackageRepositoryAptUCA(type="apt", **kwargs)


def test_uca_marshal():
    repo = create_uca(cloud="antelope", priority=123)

    assert repo.marshal() == {
        "type": "apt",
        "cloud": "antelope",
        "pocket": "updates",
        "priority": 123,
    }


def test_uca_invalid_cloud():
    with pytest.raises(pydantic.ValidationError) as raised:
        create_uca(cloud="")

    expected_message = "clouds must be non-empty strings."

    err = raised.value
    assert expected_message in str(err)


@pytest.mark.parametrize(
    ("priority_str", "priority_int"),
    [
        ("always", 1000),
        ("prefer", 990),
        ("defer", 100),
    ],
)
def test_uca_priority_correctly_converted(priority_str, priority_int):
    repo_marshalled = BASIC_UCA_MARSHALLED.copy()
    repo_marshalled["priority"] = priority_str
    repo = PackageRepositoryAptUCA.unmarshal(repo_marshalled)

    assert repo.priority == priority_int


@pytest.mark.parametrize(
    ("cloud", "pin"),
    [
        ("antelope", 'origin "ubuntu-cloud.archive.canonical.com"'),
        ("zed", 'origin "ubuntu-cloud.archive.canonical.com"'),
    ],
)
def test_uca_pin_value(cloud, pin):
    repo = PackageRepositoryAptUCA.unmarshal(
        {
            "type": "apt",
            "cloud": cloud,
        }
    )

    assert repo.pin == pin


# endregion
