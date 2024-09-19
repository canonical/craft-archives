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
import collections
import enum
import re
from collections.abc import Mapping
from typing import (
    Annotated,
    Any,
    Literal,
    TypeVar,
)
from urllib.parse import urlparse

from overrides import overrides  # pyright: ignore[reportUnknownVariableType]
from pydantic import (
    AfterValidator,
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,  # pyright: ignore[reportUnknownVariableType]
    FileUrl,
    StringConstraints,
    ValidationInfo,
    field_serializer,
    field_validator,  # pyright: ignore[reportUnknownVariableType]
    model_validator,  # pyright: ignore[reportUnknownVariableType]
)
from typing_extensions import Self

from . import errors

T = TypeVar("T")


def _validate_list_is_unique(value: list[T]) -> list[T]:
    value_set = set(value)
    if len(value_set) == len(value):
        return value
    dupes = [item for item, count in collections.Counter(value).items() if count > 1]
    raise ValueError(f"duplicate values in list: {dupes}")


UniqueList = Annotated[
    list[T],
    AfterValidator(_validate_list_is_unique),
    Field(json_schema_extra={"uniqueItems": True}),
]


class PocketEnum(str, enum.Enum):
    """Enum values that represent possible pocket values."""

    RELEASE = "release"
    UPDATES = "updates"
    PROPOSED = "proposed"
    SECURITY = "security"

    def __str__(self) -> str:
        return self.value


class PocketUCAEnum(str, enum.Enum):
    """Enum values that represent possible pocket values for UCA."""

    UPDATES = PocketEnum.UPDATES.value
    PROPOSED = PocketEnum.PROPOSED.value

    def __str__(self) -> str:
        return self.value


UCA_ARCHIVE = "http://ubuntu-cloud.archive.canonical.com/ubuntu"
UCA_NETLOC = urlparse(UCA_ARCHIVE).netloc
UCA_KEY_ID = "391A9AA2147192839E9DB0315EDB1B62EC4926EA"


class PriorityString(enum.IntEnum):
    """Convenience values that represent common deb priorities."""

    ALWAYS = 1000
    PREFER = 990
    DEFER = 100


PriorityValue = int | Literal["always", "prefer", "defer"]
SeriesStr = Annotated[
    str, StringConstraints(min_length=1, pattern=re.compile(r"^[a-z]+$"))
]
KeyIdStr = Annotated[
    str,
    StringConstraints(
        min_length=40, max_length=40, pattern=re.compile(r"^[0-9A-F]{40}$")
    ),
]


def _validate_suite_str(suite: str) -> str:
    if suite.endswith("/"):
        raise ValueError(f"invalid suite {suite!r}. Suites must not end with a '/'.")
    return suite


SuiteStr = Annotated[
    str,
    AfterValidator(_validate_suite_str),
]


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
    priority: PriorityValue | None = None

    @model_validator(mode="before")
    @classmethod
    def priority_cannot_be_zero(cls, values: dict[str, Any]) -> dict[str, Any]:
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
        cls, priority: PriorityValue | None, info: ValidationInfo
    ) -> int | None:
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

    def marshal(self) -> dict[str, str | int]:
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
        cls, data: list[dict[str, Any]] | None
    ) -> list["PackageRepository"]:
        """Create multiple package repositories from the given data."""
        repositories: list[PackageRepository] = []

        if data is not None:
            if not isinstance(data, list):  # pyright: ignore[reportUnnecessaryIsInstance]
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
    key_id: KeyIdStr | None = Field(default=None, alias="key-id")

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
    pocket: PocketUCAEnum = PocketUCAEnum.UPDATES

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
        return cls.model_validate(data)

    @property
    def pin(self) -> str:
        """The pin string for this repository if needed."""
        return f'origin "{UCA_NETLOC}"'


class PackageRepositoryApt(PackageRepository):
    """An APT package repository."""

    url: AnyUrl | FileUrl
    key_id: KeyIdStr = Field(alias="key-id")
    architectures: UniqueList[str] | None = None
    formats: list[Literal["deb", "deb-src"]] | None = None
    path: str | None = None
    components: UniqueList[str] | None = None
    key_server: str | None = Field(default=None, alias="key-server")
    suites: list[SuiteStr] | None = None
    pocket: PocketEnum | None = None
    series: SeriesStr | None = None

    @property
    def name(self) -> str:
        """Get the repository name."""
        return re.sub(r"\W+", "_", str(self.url))

    @field_validator("url")
    @classmethod
    def _convert_url_to_string(cls, url: AnyUrl | FileUrl) -> str:
        return str(url).rstrip("/")

    @field_serializer("url")
    def _serialize_url_as_string(self, url: AnyUrl | FileUrl) -> str:
        return str(url)

    @field_validator("path")
    @classmethod
    def _path_non_empty(cls, path: str | None, info: ValidationInfo) -> str | None:
        if path is not None and not path:
            raise _create_validation_error(
                url=info.data.get("url"),
                message="Invalid path; Paths must be non-empty strings.",
            )
        return path

    @field_validator("components")
    @classmethod
    def _not_mixing_components_and_path(
        cls, components: list[str] | None, info: ValidationInfo
    ) -> list[str] | None:
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
        cls, suites: list[str] | None, info: ValidationInfo
    ) -> list[str] | None:
        path = info.data.get("path")
        if suites and path:
            message = f"suites {suites!r} cannot be combined with path {path!r}."
            raise _create_validation_error(url=info.data.get("url"), message=message)
        return suites

    @model_validator(mode="after")
    def _not_mixing_suites_and_series_pocket(self) -> Self:
        if self.suites and (self.series or self.pocket):
            raise _create_validation_error(
                url=str(self.url),
                message="suites cannot be combined with series and pocket.",
            )
        return self

    @model_validator(mode="after")
    def _missing_pocket_with_series(self) -> Self:
        """Validate pocket is set when series is. The other way around is NOT mandatory."""
        if self.series and not self.pocket:
            raise _create_validation_error(
                url=str(self.url), message="pocket must be specified when using series."
            )
        return self

    @model_validator(mode="after")
    def _missing_components_or_suites_pocket(self) -> Self:
        if self.suites and not self.components:
            raise _create_validation_error(
                url=str(self.url),
                message="components must be specified when using suites.",
            )
        if self.components and not (self.suites or self.pocket):
            raise _create_validation_error(
                url=str(self.url),
                message='either "suites" or "series and pocket" must be specified when using components.',
            )

        return self

    @classmethod
    @overrides
    def unmarshal(cls, data: Mapping[str, Any]) -> "PackageRepositoryApt":
        """Create a package repository object from the given data."""
        return cls.model_validate(data)

    @property
    def pin(self) -> str:
        """The pin string for this repository if needed."""
        domain = urlparse(str(self.url)).netloc
        return f'origin "{domain}"'


def _create_validation_error(*, url: str | None = None, message: str) -> ValueError:
    """Create a ValueError with a formatted message and an optional url."""
    error_message = ""
    if url:
        error_message += f"Invalid package repository for '{url}': "
    error_message += message
    return ValueError(error_message)
