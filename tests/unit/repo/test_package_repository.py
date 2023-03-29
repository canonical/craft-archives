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


import pytest
from craft_archives.repo import errors
from craft_archives.repo.package_repository import (
    UCA_VALID_POCKETS,
    PackageRepository,
    PackageRepositoryApt,
    PackageRepositoryAptPPA,
    PackageRepositoryAptUCA,
)

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
    "name": "test-name",
    "suites": ["xenial", "xenial-updates"],
    "type": "apt",
    "url": "http://archive.ubuntu.com/ubuntu",
    "priority": 123,
}


@pytest.fixture
def apt_repository():
    yield PackageRepositoryApt(
        architectures=["amd64", "i386"],
        components=["main", "multiverse"],
        formats=["deb", "deb-src"],
        key_id="A" * 40,
        key_server="keyserver.ubuntu.com",
        name="test-name",
        suites=["xenial", "xenial-updates"],
        url="http://archive.ubuntu.com/ubuntu",
        priority=123,
    )


# endregion
# region PackageRepositoryApt
def test_apt_name():
    repo = PackageRepositoryApt(
        key_id="A" * 40,
        url="http://archive.ubuntu.com/ubuntu",
    )
    assert repo.name == "http_archive_ubuntu_com_ubuntu"


@pytest.mark.parametrize(
    "arch", ["amd64", "armhf", "arm64", "i386", "ppc64el", "riscv", "s390x"]
)
def test_apt_valid_architectures(arch):
    package_repo = PackageRepositoryApt(
        key_id="A" * 40, url="http://test", architectures=[arch]
    )

    assert package_repo.architectures == [arch]


def test_apt_invalid_url():
    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryApt(
            key_id="A" * 40,
            url="",
        )

    err = raised.value
    assert str(err) == "Invalid package repository for '': invalid URL."
    assert err.details == "URLs must be non-empty strings."
    assert err.resolution == (
        "Verify the repository configuration and ensure that 'url' "
        "is correctly specified."
    )


def test_apt_invalid_path():
    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryApt(
            key_id="A" * 40,
            path="",
            url="http://archive.ubuntu.com/ubuntu",
        )

    err = raised.value
    assert str(err) == (
        "Invalid package repository for 'http://archive.ubuntu.com/ubuntu': "
        "invalid path ''."
    )
    assert err.details == "Paths must be non-empty strings."
    assert err.resolution == (
        "Verify the repository configuration and ensure that 'path' "
        "is a non-empty string such as '/'."
    )


def test_apt_invalid_path_with_suites():
    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryApt(
            key_id="A" * 40,
            path="/",
            suites=["xenial", "xenial-updates"],
            url="http://archive.ubuntu.com/ubuntu",
        )

    err = raised.value
    assert str(err) == (
        "Invalid package repository for 'http://archive.ubuntu.com/ubuntu': "
        "suites ['xenial', 'xenial-updates'] cannot be combined with path '/'."
    )
    assert err.details == "Path and suites are incomptiable options."
    assert err.resolution == (
        "Verify the repository configuration and remove 'path' or 'suites'."
    )


def test_apt_invalid_path_with_components():
    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryApt(
            key_id="A" * 40,
            path="/",
            components=["main"],
            url="http://archive.ubuntu.com/ubuntu",
        )

    err = raised.value
    assert str(err) == (
        "Invalid package repository for 'http://archive.ubuntu.com/ubuntu': "
        "components ['main'] cannot be combined with path '/'."
    )
    assert err.details == "Path and components are incomptiable options."
    assert err.resolution == (
        "Verify the repository configuration and remove 'path' or 'components'."
    )


def test_apt_invalid_missing_components():
    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryApt(
            key_id="A" * 40,
            suites=["xenial", "xenial-updates"],
            url="http://archive.ubuntu.com/ubuntu",
        )

    err = raised.value
    assert str(err) == (
        "Invalid package repository for 'http://archive.ubuntu.com/ubuntu': "
        "no components specified."
    )
    assert err.details == "Components are required when using suites."
    assert err.resolution == (
        "Verify the repository configuration and ensure that 'components' "
        "is correctly specified."
    )


def test_apt_invalid_missing_suites():
    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryApt(
            key_id="A" * 40,
            components=["main"],
            url="http://archive.ubuntu.com/ubuntu",
        )

    err = raised.value
    assert str(err) == (
        "Invalid package repository for 'http://archive.ubuntu.com/ubuntu': "
        "no suites specified."
    )
    assert err.details == "Suites are required when using components."
    assert err.resolution == (
        "Verify the repository configuration and ensure that 'suites' "
        "is correctly specified."
    )


def test_apt_invalid_suites_as_path():
    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryApt(
            key_id="A" * 40,
            suites=["my-suite/"],
            url="http://archive.ubuntu.com/ubuntu",
        )

    err = raised.value
    assert str(err) == (
        "Invalid package repository for 'http://archive.ubuntu.com/ubuntu': "
        "invalid suite 'my-suite/'."
    )
    assert err.details == "Suites must not end with a '/'."
    assert err.resolution == (
        "Verify the repository configuration and remove the trailing '/' "
        "from suites or use the 'path' property to define a path."
    )


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

    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryApt.unmarshal(test_dict)

    err = raised.value
    assert str(err) == (
        "Invalid package repository for 'http://archive.ubuntu.com/ubuntu': "
        "unsupported properties 'foo', 'foo2'."
    )
    assert err.details is None
    assert err.resolution == "Verify repository configuration and ensure it is correct."


def test_apt_unmarshal_invalid_data():
    test_dict = "not-a-dict"

    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryApt.unmarshal(test_dict)  # type: ignore

    err = raised.value
    assert str(err) == "Invalid package repository for 'not-a-dict': invalid object."
    assert err.details == "Package repository must be a valid dictionary object."
    assert err.resolution == (
        "Verify repository configuration and ensure that the correct syntax is used."
    )


def test_apt_unmarshal_invalid_type():
    test_dict = {
        "architectures": ["amd64", "i386"],
        "components": ["main", "multiverse"],
        "formats": ["deb", "deb-src"],
        "key-id": "A" * 40,
        "key-server": "keyserver.ubuntu.com",
        "name": "test-name",
        "suites": ["xenial", "xenial-updates"],
        "type": "aptx",
        "url": "http://archive.ubuntu.com/ubuntu",
        "priority": "always",
    }

    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryApt.unmarshal(test_dict)

    err = raised.value
    assert str(err) == (
        "Invalid package repository for 'http://archive.ubuntu.com/ubuntu': "
        "unsupported type 'aptx'."
    )
    assert err.details == "The only currently supported type is 'apt'."
    assert err.resolution == (
        "Verify repository configuration and ensure that 'type' is correctly specified."
    )


@pytest.mark.parametrize(
    "repository",
    [
        BASIC_APT_MARSHALLED,
        {
            "type": "apt",
            "key-id": "A" * 40,
            "url": "https://example.com",
            "name": "test",
        },
        {
            "type": "apt",
            "key-id": "A" * 40,
            "url": "https://example.com",
            "name": "test",
            "architectures": ["spookyarch"],
        },
        {
            "type": "apt",
            "key-id": "A" * 40,
            "url": "https://example.com",
            "name": "test",
            "components": ["main"],
            "suites": ["jammy"],
        },
        pytest.param(
            {
                "type": "apt",
                "key-id": "A" * 40,
                "url": "https://example.com",
                "name": "test",
                "path": "/dev/null",
            },
            marks=pytest.mark.xfail(
                reason=(
                    "PackageRepositoryApt does not unmarshal a path. "
                    "https://github.com/canonical/craft-archives/issues/37"
                )
            ),
        ),
        {
            "type": "apt",
            "key-id": "A" * 40,
            "url": "https://example.com",
            "name": "test",
            "components": ["main"],
            "suites": ["jammy"],
            "priority": "always",
        },
        {
            "type": "apt",
            "key-id": "A" * 40,
            "url": "https://example.com",
            "name": "test",
            "components": ["main"],
            "suites": ["jammy"],
            "priority": 1234,
        },
    ],
)
def test_apt_marshal_unmarshal_inverses(repository):
    assert PackageRepositoryApt.unmarshal(repository).marshal() == repository


@pytest.mark.parametrize(
    "priority_str,priority_int",
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
    "url,pin",
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
def test_ppa_marshal():
    repo = PackageRepositoryAptPPA(ppa="test/ppa", priority=123)

    assert repo.marshal() == {"type": "apt", "ppa": "test/ppa", "priority": 123}


@pytest.mark.parametrize(
    "ppa",
    [
        "",
        None,
    ],
)
def test_ppa_invalid_ppa(ppa):
    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryAptPPA(ppa=ppa)

    err = raised.value
    assert str(err) == f"Invalid package repository for {ppa!r}: invalid PPA."
    assert err.details == "PPAs must be non-empty strings."
    assert err.resolution == (
        "Verify repository configuration and ensure that 'ppa' is correctly specified."
    )


def test_ppa_unmarshal_invalid_data():
    test_dict = "not-a-dict"

    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryAptPPA.unmarshal(test_dict)  # type: ignore

    err = raised.value
    assert str(err) == "Invalid package repository for 'not-a-dict': invalid object."
    assert err.details == "Package repository must be a valid dictionary object."
    assert err.resolution == (
        "Verify repository configuration and ensure that the correct syntax is used."
    )


@pytest.mark.parametrize(
    "ppa,error,details,resolution",
    [
        pytest.param(
            {"type": "aptx", "ppa": "test/ppa"},
            "Invalid package repository for 'test/ppa': unsupported type 'aptx'.",
            "The only currently supported type is 'apt'.",
            "Verify repository configuration and ensure that 'type' is correctly specified.",
            id="invalid_type",
        ),
        pytest.param(
            {"type": "apt", "ppa": "test/ppa", "test": "foo"},
            "Invalid package repository for 'test/ppa': unsupported properties 'test'.",
            None,
            "Verify repository configuration and ensure that it is correct.",
            id="extra_keys",
        ),
    ],
)
def test_ppa_unmarshal_error(check, ppa, error, details, resolution):
    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryAptPPA.unmarshal(ppa)

    check.equal(str(raised.value), error)
    check.equal(raised.value.details, details)
    check.equal(raised.value.resolution, resolution)


@pytest.mark.parametrize(
    "priority_str,priority_int",
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
    "ppa,pin",
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
        PackageRepository.unmarshal_package_repositories("not-a-list")

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
def test_uca_marshal():
    repo = PackageRepositoryAptUCA(cloud="antelope", priority=123)

    assert repo.marshal() == {
        "type": "apt",
        "cloud": "antelope",
        "pocket": "updates",
        "priority": 123,
    }


@pytest.mark.parametrize(
    "cloud",
    [
        "",
        None,
    ],
)
def test_uca_invalid_cloud(cloud):
    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryAptUCA(cloud=cloud)

    err = raised.value
    assert str(err) == (f"Invalid package repository for {cloud!r}: invalid cloud.")
    assert err.details == "clouds must be non-empty strings."
    assert err.resolution == (
        "Verify repository configuration and ensure that 'cloud' is correctly specified."
    )


def test_uca_unmarshal_invalid_data():
    test_dict = "not-a-dict"

    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryAptUCA.unmarshal(test_dict)  # type: ignore

    err = raised.value
    assert str(err) == "Invalid package repository for 'not-a-dict': invalid object."
    assert err.details == "Package repository must be a valid dictionary object."
    assert err.resolution == (
        "Verify repository configuration and ensure that the correct syntax is used."
    )


@pytest.mark.parametrize(
    "cloud,error,details,resolution",
    [
        pytest.param(
            {"type": "aptx", "cloud": "antelope"},
            "Invalid package repository for 'antelope': unsupported type 'aptx'.",
            "The only currently supported type is 'apt'.",
            "Verify repository configuration and ensure that 'type' is correctly specified.",
            id="invalid_type",
        ),
        pytest.param(
            {"type": "apt", "cloud": "antelope", "test": "foo"},
            "Invalid package repository for 'antelope': unsupported properties 'test'.",
            None,
            "Verify repository configuration and ensure that it is correct.",
            id="extra_keys",
        ),
        pytest.param(
            {"type": "apt", "cloud": "antelope", "pocket": "security_updates"},
            "Invalid package repository for 'antelope': Invalid pocket 'security_updates'.",
            f"pocket must be a valid string and comprised in {UCA_VALID_POCKETS!r}",
            (
                "Verify repository configuration and ensure that 'pocket' "
                "is correctly specified."
            ),
            id="invalid_type",
        ),
    ],
)
def test_uca_unmarshal_error(check, cloud, error, details, resolution):
    with pytest.raises(errors.PackageRepositoryValidationError) as raised:
        PackageRepositoryAptUCA.unmarshal(cloud)

    check.equal(str(raised.value), error)
    check.equal(raised.value.details, details)
    check.equal(raised.value.resolution, resolution)


@pytest.mark.parametrize(
    "priority_str,priority_int",
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
    "cloud,pin",
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
