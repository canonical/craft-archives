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
import logging
import re
import textwrap
import urllib.error
from pathlib import Path
from textwrap import dedent
from typing import Any
from unittest import mock
from unittest.mock import call, patch

import distro
import pytest
from craft_archives.repo import apt_ppa, apt_sources_manager, errors, gpg
from craft_archives.repo.apt_sources_manager import (
    _DEFAULT_SOURCES_DIRECTORY,
    AptSourcesManager,
    _add_architecture,
    _get_suites,
    _is_deb822_default,
    _update_sources_file,
)
from craft_archives.repo.package_repository import (
    PackageRepositoryApt,
    PackageRepositoryAptPPA,
    PackageRepositoryAptUCA,
    PocketEnum,
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
        signed_by_root=tmp_path,
    )


@pytest.fixture
def mock_is_deb822_default(request, mocker):
    return mocker.patch(
        "craft_archives.repo.apt_sources_manager._is_deb822_default",
        return_value=getattr(request, "param", False),
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
    "package_repo,name,content_template",
    [
        (
            PackageRepositoryApt.model_validate(
                {
                    "type": "apt",
                    "architectures": ["amd64", "arm64"],
                    "components": ["test-component"],
                    "formats": ["deb", "deb-src"],
                    "key-id": "A" * 40,
                    "suites": ["test-suite1", "test-suite2"],
                    "url": "http://test.url/ubuntu",
                }
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
            PackageRepositoryApt.model_validate(
                {
                    "type": "apt",
                    "architectures": ["amd64", "arm64"],
                    "components": ["test-component"],
                    "formats": ["deb", "deb-src"],
                    "key-id": "A" * 40,
                    "series": "test",
                    "pocket": PocketEnum.PROPOSED,
                    "url": "http://test.url/ubuntu",
                }
            ),
            "craft-http_test_url_ubuntu.sources",
            dedent(
                """\
                Types: deb deb-src
                URIs: http://test.url/ubuntu
                Suites: test test-updates test-proposed
                Components: test-component
                Architectures: amd64 arm64
                Signed-By: {keyring_path}
                """
            ),
        ),
        (
            PackageRepositoryApt.model_validate(
                {
                    "type": "apt",
                    "architectures": ["amd64", "arm64"],
                    "components": ["test-component"],
                    "formats": ["deb", "deb-src"],
                    "key-id": "A" * 40,
                    "series": "test",
                    "pocket": PocketEnum.SECURITY,
                    "url": "http://test.url/ubuntu",
                }
            ),
            "craft-http_test_url_ubuntu.sources",
            dedent(
                """\
                Types: deb deb-src
                URIs: http://test.url/ubuntu
                Suites: test-security
                Components: test-component
                Architectures: amd64 arm64
                Signed-By: {keyring_path}
                """
            ),
        ),
        (
            PackageRepositoryApt.model_validate(
                {
                    "type": "apt",
                    "architectures": ["amd64", "arm64"],
                    "formats": ["deb", "deb-src"],
                    "path": "dir/subdir",
                    "key-id": "A" * 40,
                    "url": "http://test.url/ubuntu",
                }
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
    get_architecture_mock = mocker.patch(
        "subprocess.check_output", return_value=b"fake"
    )
    add_architecture_mock = mocker.spy(
        apt_sources_manager,
        "_add_architecture",
    )

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

    if use_signed_by_root:
        expected_root = tmp_path
    else:
        expected_root = Path("/")

    if isinstance(package_repo, PackageRepositoryApt) and package_repo.architectures:
        assert add_architecture_mock.mock_calls == [
            call(
                architectures=package_repo.architectures,
                root=expected_root,
                sources_dir=apt_sources_mgr._sources_list_d,
            )
        ]
        assert get_architecture_mock.called

    # Regardless of host architecture, "dpkg --add-architecture" must _not_ be called,
    # because the fantasy archs in the test repos are not compatible.
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
    side_effect=urllib.error.HTTPError("", http.HTTPStatus.NOT_FOUND, "", {}, None),  # type: ignore
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

    @classmethod
    def validate(cls, value: Any) -> Any:
        return value


def test_install_apt_errors(apt_sources_mgr):
    repo = PackageRepositoryApt.model_validate(
        {
            "type": "apt",
            "architectures": ["amd64"],
            "url": "https://example.com",
            "key-id": "A" * 40,
        }
    )
    with pytest.raises(errors.AptGPGKeyringError):
        apt_sources_mgr._install_sources_apt(package_repo=repo)


def test_preferences_path_for_root():
    assert AptSourcesManager.sources_path_for_root() == _DEFAULT_SOURCES_DIRECTORY
    assert AptSourcesManager.sources_path_for_root(Path("/my/root")) == Path(
        "/my/root/etc/apt/sources.list.d"
    )


@pytest.mark.parametrize(
    ("host_arch", "repo_arch"),
    [
        (b"amd64\n", "i386"),
        (b"arm64\n", "armhf"),
    ],
)
@pytest.mark.usefixtures("mock_is_deb822_default")
def test_add_architecture_compatible_not_deb822(caplog, mocker, host_arch, repo_arch):
    """Add compatible architectures even if the default sources aren't deb822."""
    caplog.set_level(logging.DEBUG)
    update_sources_file_mock = mocker.patch(
        "craft_archives.repo.apt_sources_manager._update_sources_file"
    )
    check_output_mock = mocker.patch("subprocess.check_output", return_value=host_arch)
    run_mock = mocker.patch("subprocess.run")

    _add_architecture(
        [repo_arch], root=Path("/"), sources_dir=_DEFAULT_SOURCES_DIRECTORY
    )

    check_output_mock.assert_called_once_with(["dpkg", "--print-architecture"])
    assert run_mock.mock_calls == [
        call(
            ["dpkg", "--root", "/", "--add-architecture", repo_arch],
            check=True,
        ),
    ]
    update_sources_file_mock.assert_not_called()
    assert (
        "Not updating sources.list because it doesn't exist "
        "or isn't in the deb822 format."
    ) in caplog.text


@pytest.mark.parametrize(
    ("host_arch", "repo_arch"),
    [
        (b"amd64\n", "arm64"),
        (b"arm64\n", "i386"),
    ],
)
@pytest.mark.usefixtures("mock_is_deb822_default")
def test_add_architecture_incompatible_not_deb822(caplog, mocker, host_arch, repo_arch):
    """Don't add incompatible architectures if the default sources aren't deb822."""
    caplog.set_level(logging.DEBUG)
    update_sources_file_mock = mocker.patch(
        "craft_archives.repo.apt_sources_manager._update_sources_file"
    )
    check_output_mock = mocker.patch("subprocess.check_output", return_value=host_arch)
    run_mock = mocker.patch("subprocess.run")

    _add_architecture(
        [repo_arch], root=Path("/"), sources_dir=_DEFAULT_SOURCES_DIRECTORY
    )

    check_output_mock.assert_called_once_with(["dpkg", "--print-architecture"])
    assert not run_mock.called
    update_sources_file_mock.assert_not_called()
    assert (
        "Not updating sources.list because it doesn't exist "
        "or isn't in the deb822 format."
    ) in caplog.text


@pytest.mark.parametrize(
    ("host_arch", "compatible_archs", "repo_arch"),
    [
        pytest.param(b"amd64\n", ["amd64", "i386"], "arm64", id="compatible-arch-pair"),
        pytest.param(b"riscv64\n", "riscv64", "arm64", id="lone-arch"),
    ],
)
@pytest.mark.parametrize("mock_is_deb822_default", [True], indirect=True)
def test_add_architecture_deb822(
    mocker, host_arch, compatible_archs, repo_arch, mock_is_deb822_default
):
    """Update default sources and add archs if the default sources are deb822."""
    update_sources_file_mock = mocker.patch(
        "craft_archives.repo.apt_sources_manager._update_sources_file"
    )
    check_output_mock = mocker.patch("subprocess.check_output", return_value=host_arch)
    run_mock = mocker.patch("subprocess.run")

    _add_architecture(
        [repo_arch], root=Path("/"), sources_dir=_DEFAULT_SOURCES_DIRECTORY
    )

    check_output_mock.assert_called_once_with(["dpkg", "--print-architecture"])
    assert run_mock.mock_calls == [
        call(
            ["dpkg", "--root", "/", "--add-architecture", repo_arch],
            check=True,
        ),
    ]
    update_sources_file_mock.assert_called_once_with(
        sources_file=_DEFAULT_SOURCES_DIRECTORY / "ubuntu.sources",
        field="Architectures",
        values=compatible_archs,
    )


@pytest.mark.parametrize(
    ("archs_entry", "archs_to_update", "expected_archs_entry"),
    [
        pytest.param("", ["riscv64"], "Architectures: riscv64\n", id="add-one"),
        pytest.param(
            "", ["amd64", "i386"], "Architectures: amd64 i386\n", id="add-multiple"
        ),
        pytest.param(
            "Architectures: riscv64",
            ["riscv64"],
            "Architectures: riscv64\n",
            id="update-no-op",
        ),
        pytest.param(
            "Architectures: amd64",
            ["riscv64"],
            "Architectures: riscv64\n",
            id="update-one",
        ),
        pytest.param(
            "Architectures: amd64",
            ["amd64", "i386"],
            "Architectures: amd64 i386\n",
            id="update-multiple",
        ),
        pytest.param("Architectures: amd64 i386", "", "", id="delete-empty-str"),
        pytest.param("Architectures: amd64 i386", [], "", id="delete-empty-list"),
    ],
)
def test_update_sources(
    caplog, tmp_path, archs_entry, archs_to_update, expected_archs_entry
):
    """Update values in a deb822 sources files."""
    caplog.set_level(logging.DEBUG)
    sources_file = (
        tmp_path / _DEFAULT_SOURCES_DIRECTORY.relative_to("/") / "ubuntu.sources"
    )
    uri = "http://archive.ubuntu.com/ubuntu/"
    sources = textwrap.dedent(
        f"""
        Types: deb
        URIs: {uri}
        Suites: noble noble-updates noble-backports
        Components: main universe restricted multiverse
        Signed-By: /usr/share/keyrings/FC42E99D.gpg
        """
    )
    sources_file.parent.mkdir(parents=True)
    sources_file.write_text(sources + archs_entry)

    _update_sources_file(
        sources_file=sources_file,
        field="Architectures",
        values=archs_to_update,
    )

    assert sources_file.read_text() == sources.lstrip() + expected_archs_entry + "\n"
    assert f"Reading sources from {str(sources_file)!r}." in caplog.text
    assert f"Updating source {uri!r}." in caplog.text
    assert f"Writing updated sources to {str(sources_file)!r}." in caplog.text


def update_sources_does_not_exist(caplog, tmp_path):
    """No-op if the sources file does not exist."""
    caplog.set_level(logging.DEBUG)
    sources_file = (
        tmp_path / _DEFAULT_SOURCES_DIRECTORY.relative_to("/") / "ubuntu.sources"
    )
    sources_file.parent.mkdir(parents=True)

    _update_sources_file(
        sources_file=sources_file,
        field="Architectures",
        values="riscv64",
    )

    assert not sources_file.exists()
    assert f"Sources file {str(sources_file)!r} doesn't exist." in caplog.text


def test_update_sources_wrong_format(caplog, tmp_path):
    """Don't touch non-deb822 files."""
    caplog.set_level(logging.DEBUG)
    sources_file = (
        tmp_path / _DEFAULT_SOURCES_DIRECTORY.relative_to("/") / "ubuntu.sources"
    )
    sources_file.parent.mkdir(parents=True)
    sources_file.write_text("not a sources file\n")

    _update_sources_file(
        sources_file=sources_file,
        field="Architectures",
        values="riscv64",
    )

    assert sources_file.read_text() == "not a sources file\n"
    assert (
        f"Not updating {str(sources_file)!r} because it doesn't contain any deb822 sources."
        in caplog.text
    )


def test_is_deb822_default(tmp_path):
    _is_deb822_default.cache_clear()
    sources_file = tmp_path / "ubuntu.sources"
    sources_file.write_text(
        textwrap.dedent(
            """
            Types: deb
            URIs: http://archive.ubuntu.com/ubuntu/
            Suites: noble noble-updates noble-backports
            Components: main universe restricted multiverse
            Signed-By: /usr/share/keyrings/FC42E99D.gpg
            """
        )
    )

    assert _is_deb822_default(tmp_path)


def test_is_deb822_default_no_file(tmp_path):
    _is_deb822_default.cache_clear()

    assert not _is_deb822_default(tmp_path)


def test_is_deb822_default_wrong_format(tmp_path):
    _is_deb822_default.cache_clear()
    sources_file = tmp_path / "ubuntu.sources"
    sources_file.write_text("not a sources file\n")

    assert not _is_deb822_default(tmp_path)


@pytest.mark.parametrize(
    ("pocket, series, result"),
    [
        (PocketEnum.RELEASE, "jammy", ["jammy"]),
        (PocketEnum.UPDATES, "jammy", ["jammy", "jammy-updates"]),
        (PocketEnum.PROPOSED, "jammy", ["jammy", "jammy-updates", "jammy-proposed"]),
        (PocketEnum.SECURITY, "jammy", ["jammy-security"]),
        (None, "jammy", ["jammy"]),
        (PocketEnum.RELEASE, "", [""]),
    ],
)
def test_get_suites(pocket, series, result):
    assert _get_suites(pocket, series) == result


def test_existing_key_incompatible(apt_sources_mgr, tmp_path, mocker):
    repo = PackageRepositoryApt.unmarshal(
        {
            "type": "apt",
            "url": "http://archive.ubuntu.com/ubuntu",
            "suites": ["noble"],
            "components": ["main", "universe"],
            "key_id": "78E1918602959B9C59103100F1831DDAFC42E99D",
        }
    )

    # Add a fake "ubuntu.sources" file that has a source that is Signed-By
    # a fake keyring file that does *not* contain FC42E99D.
    ubuntu_sources = tmp_path / "etc/apt/sources.list.d/ubuntu.sources"
    ubuntu_sources.parent.mkdir(parents=True)
    ubuntu_sources.write_text(
        textwrap.dedent(
            """
            Types: deb
            URIs: http://archive.ubuntu.com/ubuntu/
            Suites: noble noble-updates noble-backports
            Components: main universe restricted multiverse
            Architectures: i386
            Signed-By: /usr/share/keyrings/0264B26D.gpg
            """
        )
    )

    mock_is_key_in_keyring = mocker.patch.object(
        gpg, "is_key_in_keyring", return_value=False
    )

    expected_message = re.escape(
        "The key '78E1918602959B9C59103100F1831DDAFC42E99D' for "
        "the repository with url 'http://archive.ubuntu.com/ubuntu' conflicts "
        f"with a source in '{ubuntu_sources}', "
        "which is signed by '/usr/share/keyrings/0264B26D.gpg'"
    )

    with pytest.raises(errors.SourcesKeyConflictError, match=expected_message):
        apt_sources_mgr.install_package_repository_sources(package_repo=repo)

    assert mock_is_key_in_keyring.called
