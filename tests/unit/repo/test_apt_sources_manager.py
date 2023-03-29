# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2021-2023 Canonical Ltd.
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


import http
import urllib.error
from textwrap import dedent
from unittest.mock import call, patch

import pytest
from craft_archives.repo import apt_ppa, apt_sources_manager, errors
from craft_archives.repo.package_repository import (
    PackageRepositoryApt,
    PackageRepositoryAptPPA,
    PackageRepositoryAptUCA,
)


@pytest.fixture(autouse=True)
def mock_apt_ppa_get_signing_key(mocker):
    yield mocker.patch(
        "craft_archives.repo.apt_ppa.get_launchpad_ppa_key_id",
        spec=apt_ppa.get_launchpad_ppa_key_id,
        return_value="FAKE-PPA-SIGNING-KEY",
    )


@pytest.fixture(autouse=True)
def mock_environ_copy(mocker):
    yield mocker.patch("os.environ.copy")


@pytest.fixture(autouse=True)
def mock_host_arch(mocker):
    m = mocker.patch("craft_archives.utils.get_host_architecture")
    m.return_value = "FAKE-HOST-ARCH"

    yield m


@pytest.fixture(autouse=True)
def mock_run(mocker):
    yield mocker.patch("subprocess.run")


@pytest.fixture(autouse=True)
def mock_version_codename(mocker):
    yield mocker.patch(
        "craft_archives.os_release.OsRelease.version_codename",
        return_value="FAKE-CODENAME",
    )


@pytest.fixture
def apt_sources_mgr(tmp_path):
    sources_list_d = tmp_path / "sources.list.d"
    sources_list_d.mkdir(parents=True)
    keyrings_dir = tmp_path / "keyrings"
    keyrings_dir.mkdir(parents=True)

    yield apt_sources_manager.AptSourcesManager(
        sources_list_d=sources_list_d, keyrings_dir=keyrings_dir
    )


@pytest.mark.parametrize(
    "package_repo,name,content_template",
    [
        (
            PackageRepositoryApt(
                architectures=["amd64", "arm64"],
                components=["test-component"],
                formats=["deb", "deb-src"],
                key_id="A" * 40,
                suites=["test-suite1", "test-suite2"],
                url="http://test.url/ubuntu",
            ),
            "snapcraft-http_test_url_ubuntu.sources",
            dedent(
                """\
                Types: deb deb-src
                URIs: http://test.url/ubuntu
                Suites: test-suite1 test-suite2
                Components: test-component
                Architectures: amd64 arm64
                Signed-By: {keyring_path}
                """
            ),
        ),
        (
            PackageRepositoryApt(
                architectures=["amd64", "arm64"],
                components=["test-component"],
                key_id="A" * 40,
                name="NO-FORMAT",
                suites=["test-suite1", "test-suite2"],
                url="http://test.url/ubuntu",
            ),
            "snapcraft-NO-FORMAT.sources",
            dedent(
                """\
                Types: deb
                URIs: http://test.url/ubuntu
                Suites: test-suite1 test-suite2
                Components: test-component
                Architectures: amd64 arm64
                Signed-By: {keyring_path}
                """
            ),
        ),
        (
            PackageRepositoryApt(
                key_id="A" * 40,
                name="WITH-PATH",
                path="some-path",
                url="http://test.url/ubuntu",
            ),
            "snapcraft-WITH-PATH.sources",
            dedent(
                """\
                Types: deb
                URIs: http://test.url/ubuntu
                Suites: some-path/
                Architectures: FAKE-HOST-ARCH
                Signed-By: {keyring_path}
                """
            ),
        ),
        (
            PackageRepositoryApt(
                key_id="A" * 40,
                name="IMPLIED-PATH",
                url="http://test.url/ubuntu",
            ),
            "snapcraft-IMPLIED-PATH.sources",
            dedent(
                """\
                Types: deb
                URIs: http://test.url/ubuntu
                Suites: /
                Architectures: FAKE-HOST-ARCH
                Signed-By: {keyring_path}
                """
            ),
        ),
        (
            PackageRepositoryAptPPA(ppa="test/ppa"),
            "snapcraft-ppa-test_ppa.sources",
            dedent(
                """\
                Types: deb
                URIs: http://ppa.launchpad.net/test/ppa/ubuntu
                Suites: FAKE-CODENAME
                Components: main
                Architectures: FAKE-HOST-ARCH
                Signed-By: {keyring_path}
                """
            ),
        ),
        (
            PackageRepositoryAptUCA(cloud="fake-cloud"),
            "snapcraft-cloud-fake-cloud.sources",
            dedent(
                """\
                Types: deb
                URIs: http://ubuntu-cloud.archive.canonical.com/ubuntu
                Suites: FAKE-CODENAME-updates/fake-cloud
                Components: main
                Architectures: FAKE-HOST-ARCH
                Signed-By: {keyring_path}
                """
            ),
        ),
    ],
)
def test_install(package_repo, name, content_template, apt_sources_mgr, mocker):
    run_mock = mocker.patch("subprocess.run")
    mocker.patch("urllib.request.urlopen")
    sources_path = apt_sources_mgr._sources_list_d / name

    keyring_path = apt_sources_mgr._keyrings_dir / "craft-AAAAAAAA.gpg"
    keyring_path.touch(exist_ok=True)
    content = content_template.format(keyring_path=keyring_path).encode()
    mock_keyring_path = mocker.patch(
        "craft_archives.repo.apt_key_manager.get_keyring_path"
    )
    mock_keyring_path.return_value = keyring_path

    changed = apt_sources_mgr.install_package_repository_sources(
        package_repo=package_repo
    )

    assert changed is True
    assert sources_path.read_bytes() == content

    if isinstance(package_repo, PackageRepositoryApt) and package_repo.architectures:
        assert run_mock.mock_calls == [
            call(["dpkg", "--add-architecture", "amd64"], check=True),
            call(["dpkg", "--add-architecture", "arm64"], check=True),
        ]
    else:
        assert run_mock.mock_calls == []

    run_mock.reset_mock()

    # Verify a second-run does not incur any changes.
    changed = apt_sources_mgr.install_package_repository_sources(
        package_repo=package_repo
    )

    assert changed is False
    assert sources_path.read_bytes() == content
    assert run_mock.mock_calls == []


def test_install_ppa_invalid(apt_sources_mgr):
    repo = PackageRepositoryAptPPA(ppa="ppa-missing-slash")

    with pytest.raises(errors.AptPPAInstallError) as raised:
        apt_sources_mgr.install_package_repository_sources(package_repo=repo)

    assert str(raised.value) == (
        "Failed to install PPA 'ppa-missing-slash': invalid PPA format"
    )


@patch(
    "urllib.request.urlopen",
    side_effect=urllib.error.HTTPError("", http.HTTPStatus.NOT_FOUND, "", {}, None),  # type: ignore
)
def test_install_uca_invalid(urllib, apt_sources_mgr):
    repo = PackageRepositoryAptUCA(cloud="FAKE-CLOUD")
    with pytest.raises(errors.AptUCAInstallError) as raised:
        apt_sources_mgr.install_package_repository_sources(package_repo=repo)

    assert str(raised.value) == (
        "Failed to install UCA 'FAKE-CLOUD/updates': not a valid release for 'FAKE-CODENAME'"
    )


class UnvalidatedAptRepo(PackageRepositoryApt):
    """Repository with no validation to use for invalid repositories."""

    def validate(self) -> None:
        pass


@pytest.mark.parametrize(
    "repo,error_cls,error_match",
    [
        pytest.param(
            PackageRepositoryApt(
                architectures=["amd64"],
                url="https://example.com",
                key_id="A" * 40,
            ),
            errors.AptGPGKeyringError,
            "",
            id="keyring error",
        ),
        pytest.param(
            UnvalidatedAptRepo(
                architectures=["amd64"],
                url="https://example.com",
                suites=["honeymoon", "presidential"],
                key_id="A" * 40,
            ),
            RuntimeError,
            "no components with suite",
            id="no components with suite",
        ),
        pytest.param(
            UnvalidatedAptRepo(
                architectures=["amd64"],
                url="https://example.com",
                components=["handlebar"],
                key_id="A" * 40,
            ),
            RuntimeError,
            "no suites or path",
            id="no suites or path",
        ),
    ],
)
def test_install_apt_errors(repo, error_cls, error_match, apt_sources_mgr):
    with pytest.raises(error_cls, match=error_match):
        apt_sources_mgr._install_sources_apt(package_repo=repo)
