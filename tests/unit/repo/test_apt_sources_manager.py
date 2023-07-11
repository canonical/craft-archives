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
from pathlib import Path
from textwrap import dedent
from unittest import mock
from unittest.mock import call, patch

import distro
import pytest
from craft_archives.repo import apt_ppa, apt_sources_manager, errors
from craft_archives.repo.apt_sources_manager import (
    _DEFAULT_SOURCES_DIRECTORY,
    AptSourcesManager,
)
from craft_archives.repo.package_repository import (
    PackageRepositoryApt,
    PackageRepositoryAptPPA,
    PackageRepositoryAptUCA,
)

# pyright: reportGeneralTypeIssues=false


@pytest.fixture(autouse=True)
def mock_apt_ppa_get_signing_key(mocker):
    return mocker.patch(
        "craft_archives.repo.apt_ppa.get_launchpad_ppa_key_id",
        spec=apt_ppa.get_launchpad_ppa_key_id,
        return_value="FAKE-PPA-SIGNING-KEY",
    )


@pytest.fixture(autouse=True)
def mock_environ_copy(mocker):
    return mocker.patch("os.environ.copy")


@pytest.fixture(autouse=True)
def mock_host_arch(mocker):
    m = mocker.patch("craft_archives.utils.get_host_architecture")
    m.return_value = "FAKE-HOST-ARCH"

    return m


@pytest.fixture(autouse=True)
def mock_run(mocker):
    return mocker.patch("subprocess.run")


@pytest.fixture(autouse=True)
def mock_version_codename(monkeypatch):
    mock_codename = mock.Mock(return_value="FAKE-CODENAME")
    monkeypatch.setattr(distro, "codename", mock_codename)
    return mock_codename


@pytest.fixture
def apt_sources_mgr(tmp_path):
    sources_list_d = tmp_path / "sources.list.d"
    sources_list_d.mkdir(parents=True)
    keyrings_dir = tmp_path / "keyrings"
    keyrings_dir.mkdir(parents=True)

    return apt_sources_manager.AptSourcesManager(
        sources_list_d=sources_list_d,
        keyrings_dir=keyrings_dir,
    )


def create_apt_sources_mgr(tmp_path: Path, *, use_signed_by_root: bool):
    signed_by_root = None
    if use_signed_by_root:
        signed_by_root = tmp_path

    sources_list_d = tmp_path / "sources.list.d"
    sources_list_d.mkdir(parents=True)
    keyrings_dir = tmp_path / "keyrings"
    keyrings_dir.mkdir(parents=True)

    return apt_sources_manager.AptSourcesManager(
        sources_list_d=sources_list_d,
        keyrings_dir=keyrings_dir,
        signed_by_root=signed_by_root,
    )


@pytest.mark.parametrize("use_signed_by_root", [False, True])
@pytest.mark.parametrize(
    ("package_repo", "name", "content_template"),
    [
        (
            PackageRepositoryApt(
                type="apt",
                architectures=["amd64", "arm64"],
                components=["test-component"],
                formats=["deb", "deb-src"],
                key_id="A" * 40,
                suites=["test-suite1", "test-suite2"],
                url="http://test.url/ubuntu",
            ),
            "craft-http_test_url_ubuntu.sources",
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
                type="apt",
                architectures=["amd64", "arm64"],
                formats=["deb", "deb-src"],
                path="dir/subdir",
                key_id="A" * 40,
                url="http://test.url/ubuntu",
            ),
            "craft-http_test_url_ubuntu.sources",
            dedent(
                """\
                    Types: deb deb-src
                    URIs: http://test.url/ubuntu
                    Suites: dir/subdir/
                    Architectures: amd64 arm64
                    Signed-By: {keyring_path}
                    """
            ),
        ),
        (
            PackageRepositoryAptPPA(type="apt", ppa="test/ppa"),
            "craft-ppa-test_ppa.sources",
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
            PackageRepositoryAptUCA(type="apt", cloud="fake-cloud"),
            "craft-cloud-fake-cloud.sources",
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
def test_install(
    tmp_path,
    package_repo,
    name,
    content_template,
    use_signed_by_root,
    mocker,
):
    run_mock = mocker.patch("subprocess.run")
    mocker.patch("urllib.request.urlopen")

    apt_sources_mgr = create_apt_sources_mgr(
        tmp_path, use_signed_by_root=use_signed_by_root
    )
    sources_path = apt_sources_mgr._sources_list_d / name

    keyring_path = apt_sources_mgr._keyrings_dir / "craft-AAAAAAAA.gpg"
    keyring_path.touch(exist_ok=True)

    if use_signed_by_root:
        signed_by_path = "/keyrings/craft-AAAAAAAA.gpg"
    else:
        signed_by_path = str(keyring_path)

    content = content_template.format(keyring_path=signed_by_path).encode()
    mock_keyring_path = mocker.patch(
        "craft_archives.repo.apt_key_manager.get_keyring_path"
    )
    mock_keyring_path.return_value = keyring_path

    changed = apt_sources_mgr.install_package_repository_sources(
        package_repo=package_repo
    )

    assert changed is True
    assert sources_path.read_bytes() == content

    expected_root = str(tmp_path) if use_signed_by_root else "/"

    if isinstance(package_repo, PackageRepositoryApt) and package_repo.architectures:
        assert run_mock.mock_calls == [
            call(
                ["dpkg", "--add-architecture", "amd64", "--root", expected_root],
                check=True,
            ),
            call(
                ["dpkg", "--add-architecture", "arm64", "--root", expected_root],
                check=True,
            ),
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
    repo = PackageRepositoryAptPPA(type="apt", ppa="ppa-missing-slash")

    with pytest.raises(errors.AptPPAInstallError) as raised:
        apt_sources_mgr.install_package_repository_sources(package_repo=repo)

    assert str(raised.value) == (
        "Failed to install PPA 'ppa-missing-slash': invalid PPA format"
    )


@patch(
    "urllib.request.urlopen",
    side_effect=urllib.error.HTTPError("", http.HTTPStatus.NOT_FOUND, "", {}, None),
)
def test_install_uca_invalid(urllib, apt_sources_mgr):
    repo = PackageRepositoryAptUCA(type="apt", cloud="FAKE-CLOUD")
    with pytest.raises(errors.AptUCAInstallError) as raised:
        apt_sources_mgr.install_package_repository_sources(package_repo=repo)

    assert str(raised.value) == (
        "Failed to install UCA 'FAKE-CLOUD/updates': not a valid release for 'FAKE-CODENAME'"
    )


class UnvalidatedAptRepo(PackageRepositoryApt):
    """Repository with no validation to use for invalid repositories."""

    def validate(self) -> None:
        pass


def test_install_apt_errors(apt_sources_mgr):
    repo = PackageRepositoryApt(
        type="apt",
        architectures=["amd64"],
        url="https://example.com",
        key_id="A" * 40,
    )
    with pytest.raises(errors.AptGPGKeyringError):
        apt_sources_mgr._install_sources_apt(package_repo=repo)


def test_preferences_path_for_root():
    assert AptSourcesManager.sources_path_for_root() == _DEFAULT_SOURCES_DIRECTORY
    assert AptSourcesManager.sources_path_for_root(Path("/my/root")) == Path(
        "/my/root/etc/apt/sources.list.d"
    )
