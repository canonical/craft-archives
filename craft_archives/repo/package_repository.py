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

"""Package repository definitions."""

import abc
import enum
import re
from typing import Any, Dict, List, Mapping, Optional, Union
from urllib.parse import urlparse

from overrides import overrides  # pyright: ignore[reportUnknownVariableType]
from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,  # pyright: ignore[reportUnknownVariableType]
    FileUrl,
    StringConstraints,
    ValidationInfo,
    field_validator,  # pyright: ignore[reportUnknownVariableType]
    model_validator,  # pyright: ignore[reportUnknownVariableType]
)

# NOTE: using this instead of typing.Literal because of this bad typing_extensions
# interaction: https://github.com/pydantic/pydantic/issues/5821#issuecomment-1559196859
# We can revisit this when typing_extensions >4.6.0 is released, and/or we no
# longer have to support Python <3.10
from typing_extensions import Annotated, Literal

from . import errors

UCA_ARCHIVE = "http://ubuntu-cloud.archive.canonical.com/ubuntu"
UCA_NETLOC = urlparse(UCA_ARCHIVE).netloc
UCA_VALID_POCKETS = ["updates", "proposed"]
UCA_DEFAULT_POCKET = UCA_VALID_POCKETS[0]
UCA_KEY_ID = "391A9AA2147192839E9DB0315EDB1B62EC4926EA"


class PriorityString(enum.IntEnum):
    """Convenience values that represent common deb priorities."""

    ALWAYS = 1000
    PREFER = 990
    DEFER = 100


PriorityValue = Union[int, Literal["always", "prefer", "defer"]]


def _alias_generator(value: str) -> str:
    return value.replace("_", "-")


class PackageRepository(BaseModel, abc.ABC):
    """The base class for package repositories."""

    model_config = ConfigDict(
        validate_assignment=True,
        frozen=True,
        populate_by_name=True,
        alias_generator=_alias_generator,
        extra="forbid",
    )

    type: Literal["apt"]
    priority: Optional[PriorityValue] = None

    @model_validator(mode="before")
    @classmethod
    def priority_cannot_be_zero(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Priority cannot be zero per apt Preferences specification."""
        priority = values.get("priority")
        if priority == 0:
            raise _create_validation_error(
                url=str(values.get("url") or values.get("ppa") or values.get("cloud")),
                message="invalid priority: Priority cannot be zero.",
            )
        return values

    @field_validator("priority")
    @classmethod
    def _convert_priority_to_int(
        cls, priority: Optional[PriorityValue], info: ValidationInfo
    ) -> Optional[int]:
        if isinstance(priority, str):
            str_priority = priority.upper()
            if str_priority in PriorityString.__members__:
                return PriorityString[str_priority]
            # This cannot happen; if it's a string but not one of the accepted
            # ones Pydantic will fail early and won't call this validator.
            raise _create_validation_error(
                url=str(
                    info.data.get("url")
                    or info.data.get("ppa")
                    or info.data.get("cloud")
                ),
                message=(
                    f"invalid priority {priority!r}. "
                    "Priority must be 'always', 'prefer', 'defer' or a nonzero integer."
                ),
            )
        return priority

    def marshal(self) -> Dict[str, Union[str, int]]:
        """Return the package repository data as a dictionary."""
        return self.model_dump(by_alias=True, exclude_none=True)

    @classmethod
    def unmarshal(cls, data: Mapping[str, Any]) -> "PackageRepository":
        """Create a package repository object from the given data."""
        if not isinstance(data, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise errors.PackageRepositoryValidationError(
                url=str(data),
                brief="invalid object.",
                details="Package repository must be a valid dictionary object.",
                resolution=(
                    "Verify repository configuration and ensure that the "
                    "correct syntax is used."
                ),
            )

        if "ppa" in data:
            return PackageRepositoryAptPPA.unmarshal(data)
        if "cloud" in data:
            return PackageRepositoryAptUCA.unmarshal(data)

        return PackageRepositoryApt.unmarshal(data)

    @classmethod
    def unmarshal_package_repositories(
        cls, data: Optional[List[Dict[str, Any]]]
    ) -> List["PackageRepository"]:
        """Create multiple package repositories from the given data."""
        repositories: List[PackageRepository] = []

        if data is not None:
            if not isinstance(
                data, list
            ):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise errors.PackageRepositoryValidationError(
                    url=str(data),
                    brief="invalid list object.",
                    details="Package repositories must be a list of objects.",
                    resolution=(
                        "Verify 'package-repositories' configuration and ensure "
                        "that the correct syntax is used."
                    ),
                )

            for repository in data:
                package_repo = cls.unmarshal(repository)
                repositories.append(package_repo)

        return repositories


class PackageRepositoryAptPPA(PackageRepository):
    """A PPA package repository."""

    ppa: str

    @field_validator("ppa")
    @classmethod
    def _non_empty_ppa(cls, ppa: str) -> str:
        if not ppa:
            raise _create_validation_error(
                message="Invalid PPA: PPAs must be non-empty strings."
            )
        return ppa

    @classmethod
    @overrides
    def unmarshal(cls, data: Mapping[str, Any]) -> "PackageRepositoryAptPPA":
        """Create a package repository object from the given data."""
        return cls(**data)

    @property
    def pin(self) -> str:
        """The pin string for this repository if needed."""
        ppa_origin = self.ppa.replace("/", "-")
        return f"release o=LP-PPA-{ppa_origin}"


class PackageRepositoryAptUCA(PackageRepository):
    """A cloud package repository."""

    cloud: str
    pocket: Literal["updates", "proposed"] = "updates"

    @field_validator("cloud")
    @classmethod
    def _non_empty_cloud(cls, cloud: str) -> str:
        if not cloud:
            raise _create_validation_error(message="clouds must be non-empty strings.")
        return cloud

    @classmethod
    @overrides
    def unmarshal(cls, data: Mapping[str, Any]) -> "PackageRepositoryAptUCA":
        """Create a package repository object from the given data."""
        return cls(**data)

    @property
    def pin(self) -> str:
        """The pin string for this repository if needed."""
        return f'origin "{UCA_NETLOC}"'


class PackageRepositoryApt(PackageRepository):
    """An APT package repository."""

    url: Union[AnyUrl, FileUrl]
    key_id: Annotated[
        str, StringConstraints(min_length=40, max_length=40, pattern=r"^[0-9A-F]{40}$")
    ] = Field(alias="key-id")
    architectures: Optional[List[str]] = None
    formats: Optional[List[Literal["deb", "deb-src"]]] = None
    path: Optional[str] = None
    components: Optional[List[str]] = None
    key_server: Optional[Annotated[str, Field(alias="key-server")]] = None
    suites: Optional[List[str]] = None

    @property
    def name(self) -> str:
        """Get the repository name."""
        return re.sub(r"\W+", "_", str(self.url))

    @field_validator("url")
    @classmethod
    def _convert_url_to_string(cls, url: Union[AnyUrl, FileUrl]) -> str:
        return str(url).rstrip("/")

    @field_validator("path")
    @classmethod
    def _path_non_empty(
        cls, path: Optional[str], info: ValidationInfo
    ) -> Optional[str]:
        if path is not None and not path:
            raise _create_validation_error(
                url=info.data.get("url"),
                message="Invalid path; Paths must be non-empty strings.",
            )
        return path

    @field_validator("components")
    @classmethod
    def _not_mixing_components_and_path(
        cls, components: Optional[List[str]], info: ValidationInfo
    ) -> Optional[List[str]]:
        path = info.data.get("path")
        if components and path:
            raise _create_validation_error(
                url=info.data.get("url"),
                message=(
                    f"components {components!r} cannot be combined with "
                    f"path {path!r}."
                ),
            )
        return components

    @field_validator("suites")
    @classmethod
    def _not_mixing_suites_and_path(
        cls, suites: Optional[List[str]], info: ValidationInfo
    ) -> Optional[List[str]]:
        path = info.data.get("path")
        if suites and path:
            message = f"suites {suites!r} cannot be combined with path {path!r}."
            raise _create_validation_error(url=info.data.get("url"), message=message)
        return suites

    @field_validator("suites")
    @classmethod
    def _suites_without_backslash(
        cls, suites: List[str], info: ValidationInfo
    ) -> List[str]:
        for suite in suites:
            if suite.endswith("/"):
                raise _create_validation_error(
                    url=info.data.get("url"),
                    message=f"invalid suite {suite!r}. Suites must not end "
                    "with a '/'.",
                )
        return suites

    @model_validator(mode="before")
    @classmethod
    def _missing_components_or_suites(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        suites = values.get("suites")
        components = values.get("components")
        url = values.get("url")
        if suites and not components:
            raise _create_validation_error(
                url=url, message="components must be specified when using suites."
            )
        if components and not suites:
            raise _create_validation_error(
                url=url, message="suites must be specified when using components."
            )

        return values

    @classmethod
    @overrides
    def unmarshal(cls, data: Mapping[str, Any]) -> "PackageRepositoryApt":
        """Create a package repository object from the given data."""
        return cls(**data)

    @property
    def pin(self) -> str:
        """The pin string for this repository if needed."""
        domain = urlparse(str(self.url)).netloc
        return f'origin "{domain}"'


def _create_validation_error(*, url: Optional[str] = None, message: str) -> ValueError:
    """Create a ValueError with a formatted message and an optional url."""
    error_message = ""
    if url:
        error_message += f"Invalid package repository for '{url}': "
    error_message += message
    return ValueError(error_message)
