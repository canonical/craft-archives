# This file is part of craft-archives.
#
# Copyright 2025 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Replace the default repositories (if necessary)."""

from __future__ import annotations

import functools
import http
import logging
import pathlib
import textwrap
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal, cast
from urllib.parse import urlparse
from urllib.request import HTTPError, urlopen

import pydantic
from debian._deb822_repro import parse_deb822_file

if TYPE_CHECKING:
    from http.client import HTTPResponse

logger = logging.getLogger(__name__)


class AptSource(pydantic.BaseModel):
    """A generic model for an apt source."""

    types: list[Literal["deb", "deb-src"]] = pydantic.Field(alias="Types")
    uris: list[pydantic.AnyUrl | pydantic.FileUrl] = pydantic.Field(alias="URIs")
    suites: list[str] = pydantic.Field(alias="Suites")
    components: list[str] = pydantic.Field(alias="Components")
    signed_by: pathlib.Path | None = pydantic.Field(default=None, alias="Signed-By")
    architectures: list[str] | None = pydantic.Field(
        default=None, alias="Architectures"
    )

    @pydantic.field_validator(
        "types", "uris", "suites", "components", "architectures", mode="before"
    )
    @classmethod
    def _vectorise(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return value.split()
        return value

    @classmethod
    def from_deb822(cls, path: pathlib.Path) -> Sequence[AptSource]:
        """Get a sequence of AptSource objects from a deb822 formatted file."""
        with path.open("r") as f:
            paragraphs = parse_deb822_file(f)

        return [cls.model_validate(paragraph) for paragraph in paragraphs]

    @classmethod
    def _from_sources_list_line(cls, data: str) -> AptSource:
        """Parse a line from sources.list file.

        This method parses a line from a sources.list file to an apt repository. It
        uses the one-line format defined at:
        https://www.debian.org/doc/manuals/debian-reference/ch02#_debian_archive_basics
        """
        repo_format, uri, suite, components = data.split(maxsplit=3)
        return cls.model_validate(
            {
                "Types": [repo_format],
                "URIs": [uri],
                "Suites": [suite],
                "Components": components.split(),
            }
        )

    @classmethod
    def from_sources_list(cls, path: pathlib.Path) -> Sequence[AptSource]:
        """Read a sequence of Package Repositoriues from a sources.list file.

        This parses a sources.list file into a sequence of PackageRepository models
        using the one-line format defined at:
        https://www.debian.org/doc/manuals/debian-reference/ch02#_debian_archive_basics
        """
        repositories: list[AptSource] = []
        with path.open("r") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                repositories.append(cls._from_sources_list_line(stripped))
        return repositories

    def to_sources_list(self) -> list[str]:
        """Convert this repository to one or more lines for a sources.list file."""
        components = " ".join(self.components) if self.components else "main"
        return [
            f"{pkg_type} {uri} {suite} {components}"
            for suite in self.suites
            for uri in self.uris
            for pkg_type in self.types
        ]

    def to_deb822(self) -> str:
        """Convert this repository to a deb822 paragraph."""
        signed_by_line = f"Signed-By: {self.signed_by}" if self.signed_by else ""
        return (
            textwrap.dedent(
                f"""\
                Types: {" ".join(self.types) if self.types else "deb"}
                URIs: {" ".join(str(uri) for uri in self.uris)}
                Suites: {" ".join(self.suites)}
                Components: {" ".join(self.components) if self.components else "./"}
                {signed_by_line}
            """
            ).rstrip()
            + "\n"
        )

    def replace_uris(self, *, new_uri: str, old_domain: str) -> None:
        """Replace any URIs on this model that are on the old domain with the new URI.

        :param new_uri: The full new URI. E.g. ``http://old-releases.ubuntu.com/ubuntu``
        :param old_domain: The old domain to search for. E.g. ``ubuntu.com``
        """
        source_indeces: list[int] = []
        for i, uri in enumerate(self.uris):
            if cast(str, urlparse(str(uri)).hostname).endswith(old_domain):
                source_indeces.append(i)
        for i in source_indeces:
            self.uris[i] = pydantic.AnyUrl(new_uri)


@functools.cache
def _is_on_old_releases(
    distro_name: str,
    *,
    archive_url: str = "http://old-releases.ubuntu.com/ubuntu",
    retries: int = 3,
) -> bool:
    """Check if a distribution is on the relevant old-releases site.

    :param distro_name: The distribution codename (e.g. "dapper")
    :param archive_url: The base URI for the archives. Defaults to Ubuntu's old-releases
        site.
    :param retries: How many times to retry in the case of an error.
    :returns: A boolean of whether the page is available on the
    """
    complete_url = f"{archive_url.rstrip('/')}/dists/{distro_name}/Release"
    if not complete_url.startswith("http"):
        raise RuntimeError("Don't know how to handle non-HTTP archives")
    try:
        response = cast("HTTPResponse", urlopen(complete_url))  # noqa: S310
    except HTTPError as exc:
        if not exc.status:  # Non-HTTP error.
            raise
        if (
            http.HTTPStatus.BAD_REQUEST
            <= exc.status
            < http.HTTPStatus.INTERNAL_SERVER_ERROR
        ):
            return False
        if retries > 0:
            time.sleep(5 / retries)
            return _is_on_old_releases(
                distro_name, archive_url=archive_url, retries=retries - 1
            )
        raise
    return response.status < http.HTTPStatus.BAD_REQUEST


def use_old_releases(
    root: pathlib.Path = pathlib.Path("/"),
    *,
    deb822_name: str = "ubuntu.sources",
    old_releases_url: str = "http://old-releases.ubuntu.com/ubuntu",
    change_domain: str = "ubuntu.com",
) -> bool:
    """Migrate the given root to use an old-releases archive if relevant.

    This changes the given root to use an archive on an old-releases site if the release
    exists on that site. If not, it's a no-op.

    :param root: The root of the filesystem to examine.
    :param deb822_name: The name of the deb822 file to search for default sources.
        (Default: ``ubuntu.sources``)
    :param old_releases_url: The URL of the old-releases site.
        (Default: ``http://old-releases.ubuntu.com/ubuntu``)
    :param change_domain: Only change sources on this domain.
        (Default: ``ubuntu.com``)
    :returns: True if any default releases were changed, False otherwise.
    """
    needs_update = False
    sources_list_file = root / "etc/apt/sources.list"
    deb822_sources_file = root / "etc/apt/sources.list.d" / deb822_name
    try:
        sources_list: Sequence[AptSource] = AptSource.from_sources_list(
            sources_list_file
        )
    except FileNotFoundError:
        sources_list = []

    try:
        deb822_sources: Sequence[AptSource] = AptSource.from_deb822(deb822_sources_file)
    except FileNotFoundError:
        deb822_sources = []

    for source in (*sources_list, *deb822_sources):
        for suite in source.suites:
            if _is_on_old_releases(suite, archive_url=old_releases_url):
                source.replace_uris(new_uri=old_releases_url, old_domain=change_domain)
                needs_update = True
                break

    if not needs_update:
        return False

    if deb822_sources:
        sources_paragraphs: list[str] = [
            source.to_deb822() for source in deb822_sources
        ]
        deb822_sources_file.write_text("\n".join(sources_paragraphs))
    if sources_list:
        sources_lines: list[str] = []
        for source in sources_list:
            sources_lines.extend(source.to_sources_list())
        sources_list_file.write_text("\n".join(sources_lines) + "\n")
    return True
