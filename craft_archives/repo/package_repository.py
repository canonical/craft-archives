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
from typing import (
    Annotated,
    Any,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    TypeVar,
    Union,
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


PriorityValue = Union[int, Literal["always", "prefer", "defer"]]
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
    """The type of the repository.

    Only APT repositories are supported.

    **Examples**

    .. code-block:: yaml

        type: apt

    """

    priority: Optional[PriorityValue] = Field(
        default=None,
        description="The priority of the repository",
        examples=["always", "999"],
    )
    """The priority of the repository.

    If set, this key overrides the default behavior when picking the source for a
    package.

    **Values**

    .. list-table::
        :header-rows: 1

        * - Value
          - Description
        * - ``always``
          - Always use the repository. Maps to 1000.
        * - ``prefer``
          - Prefer using the repository. Maps to 990.
        * - ``defer``
          - Use other repositories instead. Maps to 100.

    """

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

    ppa: str = Field(
        description="The short name for the PPA.",
        examples=["mozillateam/firefox-next"],
    )

    key_id: KeyIdStr | None = Field(
        default=None,
        alias="key-id",
        description="The GPG identifier of the repository.",
        examples=["590CA3D8E4826565BE3200526A634116E00F4C82"],
    )
    """The GPG identifier of the repository.

    A GPG key is also known as a long-form thumbprint or fingerprint.

    Before reaching out to the keyserver defined with ``key-server``, the application
    looks for the corresponding key in the project directory under
    ``snap/keys/<short-thumbprint>.asc`` where ``<short-thumbprint>`` is the last 8
    characters of the key ID.

    To determine the ``key-id`` from a key file, run:

    .. code-block:: bash

        gpg --import-options show-only --import <file>

    Unlike Debian package repositories, the key is optional for PPA repositories.
    """

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

    cloud: str = Field(
        description="The UCA release name.",
        examples=["antelope"],
    )

    pocket: PocketUCAEnum = PocketUCAEnum.UPDATES
    """The pocket to get packages from.

    **Examples**

    .. code-block:: yaml

        pocket: updates

    .. code-block:: yaml

        pocket: proposed

    """

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

    url: AnyUrl | FileUrl = Field(
        description="The URL of the repository",
        examples=["https://ppa.launchpad.net/snappy-dev/snapcraft-daily/ubuntu"],
    )

    key_id: KeyIdStr = Field(
        alias="key-id",
        description="The GPG identifier of the repository.",
        examples=["590CA3D8E4826565BE3200526A634116E00F4C82"],
    )
    """The GPG identifier of the repository.

    A GPG key is also known as a long-form thumbprint or fingerprint.

    Before reaching out to the keyserver defined with ``key-server``, the application
    looks for the corresponding key in the project directory under
    ``snap/keys/<short-thumbprint>.asc`` where ``<short-thumbprint>`` is the last 8
    characters of the key ID.

    To determine the ``key-id`` from a key file, run:

    .. code-block:: bash

        gpg --import-options show-only --import <file>

    Unlike Debian package repositories, the key is optional for PPA repositories.
    """

    architectures: Optional[UniqueList[str]] = Field(
        default=None,
        description="The architectures to enable for the repository.",
        examples=["[i386, amd64]"],
    )
    """The architectures to enable for the repository.

    If unspecified, the repository's architecture is assumed to match the host
    architecture.
    """

    formats: Optional[List[Literal["deb", "deb-src"]]] = Field(
        default=None,
        description="The Debian package types to enable",
        examples=["[deb, deb-src]"],
    )
    """The Debian package types to enable.

    **Values**

    .. list-table::
        :header-rows: 1

        * - Value
          - Description
        * - ``deb``
          - Default. Enable the ``.deb`` format.
        * - ``deb-src``
          - Enable the ``.deb-src`` format.

    """

    path: Optional[str] = Field(
        default=None,
        description="The absolute path to the repository from the base URL.",
        examples=["/my-repo"],
    )
    """The absolute path to the repository from the base URL.

    This key can't be used with the ``components`` key.

    This key is only needed for repositories that don't use suites, or series and
    pockets.
    """

    components: Optional[UniqueList[str]] = Field(
        default=None,
        description="The components to enable for the repository.",
        examples=["[main, multiverse, universe, restricted]"],
    )
    """The components to enable for the repository.

    If ``components`` is specified, then either ``suites`` must be specified or
    ``series`` and ``pocket`` must be specified.

    This key can't be used with the ``path`` key.
    """

    key_server: Optional[str] = Field(
        default=None,
        alias="key-server",
        description="The URL of the key server to fetch the key from.",
        examples=["hkp://keyserver.ubuntu.com:80"],
    )
    """The URL of the key server to fetch the key from.

    The key defined in ``key-id`` is fetched.
    """

    suites: Optional[List[SuiteStr]] = Field(
        default=None,
        description="The suites to enable for the repository.",
        examples=["[noble, noble-updates]"],
    )
    """The suites to enable for the repository.

    If the ``url`` does not look like it has a suite defined, it is likely that the
    repository uses an absolute URL and the ``path`` key should be used instead.

    This key can't be used with the ``path``, ``series``, or ``pocket`` keys.
    """

    pocket: Optional[PocketEnum] = Field(
        default=None,
        description="The pocket to get packages from.",
        examples=["updates", "proposed"],
    )
    """The pocket to get packages from.

    **Values**

    .. list-table::
        :header-rows: 1

        * - Value
          - Description
        * - ``updates``
          - Default. Get packages from the ``updates`` pocket.
        * -  ``proposed``
          - Get packages from the ``proposed`` pocket.

    """

    series: Optional[SeriesStr] = Field(
        default=None,
        description="The series to enable for the repository.",
        examples=["jammy", "noble"],
    )
    """The series to enable for the repository.

    This key can't be used with the ``suites`` key.
    """

    # class Config(PackageRepository.Config):  # - no docstring needed
    #     error_msg_templates = {
    #         "value_error.any_str.min_length": "Invalid URL; URLs must be non-empty strings"
    #     }

    @property
    def name(self) -> str:
        """Get the repository name."""
        return re.sub(r"\W+", "_", str(self.url))

    @field_validator("url")
    @classmethod
    def _convert_url_to_string(cls, url: Union[AnyUrl, FileUrl]) -> str:
        return str(url).rstrip("/")

    @field_serializer("url")
    def _serialize_url_as_string(self, url: AnyUrl | FileUrl) -> str:
        return str(url)

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
                    f"components {components!r} cannot be combined with path {path!r}."
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


def _create_validation_error(*, url: Optional[str] = None, message: str) -> ValueError:
    """Create a ValueError with a formatted message and an optional url."""
    error_message = ""
    if url:
        error_message += f"Invalid package repository for '{url}': "
    error_message += message
    return ValueError(error_message)
