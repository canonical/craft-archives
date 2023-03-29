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

"""Project model definitions and helpers."""
import abc
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Union

import pydantic
from pydantic import constr, validator

from craft_archives.repo import errors

# Workaround for mypy
# see https://github.com/samuelcolvin/pydantic/issues/975#issuecomment-551147305
if TYPE_CHECKING:
    KeyIdStr = str
else:
    KeyIdStr = constr(regex=r"^[0-9A-F]{40}$")

PriorityValue = Union[Literal["always", "prefer", "defer"], int]


class ProjectModel(pydantic.BaseModel):
    """Base model for project repository classes."""

    class Config:  # pylint: disable=too-few-public-methods
        """Pydantic model configuration."""

        # pyright: reportUnknownMemberType=false
        # pyright: reportUnknownVariableType=false
        # pyright: reportUnknownLambdaType=false

        validate_assignment = True
        allow_mutation = False
        allow_population_by_field_name = True
        alias_generator = lambda s: s.replace("_", "-")  # noqa: E731
        extra = "forbid"


# TODO: Project repo definitions are almost the same as PackageRepository
#       ported from legacy. Check if we can consolidate them and remove
#       field validation (moving all validation rules to pydantic).


class Apt(abc.ABC, ProjectModel):
    """Apt package repository — could be deb-style or a PPA."""

    type: Literal["apt"]
    # URL and PPA must be defined before priority so the validator can use their values
    url: Optional[str]
    ppa: Optional[str]
    cloud: Optional[str]
    priority: Optional[PriorityValue]

    @classmethod
    def unmarshal(cls, data: Dict[str, Any]) -> "Apt":
        """Create an Apt subclass object from a dictionary."""
        if "ppa" in data:
            return AptPPA.unmarshal(data)
        if "cloud" in data:
            return AptUCA.unmarshal(data)
        return AptDeb.unmarshal(data)

    @validator("priority")
    def priority_cannot_be_zero(
        cls, priority: Optional[PriorityValue], values: Dict[str, Any]
    ) -> Optional[PriorityValue]:
        """Priority cannot be zero per apt Preferences specification."""
        if priority == 0:
            raise errors.PackageRepositoryValidationError(
                url=str(values.get("url") or values.get("ppa") or values.get("cloud")),
                brief=f"invalid priority {priority}.",
                details="Priority cannot be zero.",
                resolution="Verify priority value.",
            )
        return priority


class AptDeb(Apt):
    """Apt package repository definition."""

    url: str
    key_id: KeyIdStr
    architectures: Optional[List[str]]
    formats: Optional[List[Literal["deb", "deb-src"]]]
    components: Optional[List[str]]
    key_server: Optional[str]
    path: Optional[str]
    suites: Optional[List[str]]

    @classmethod
    def unmarshal(cls, data: Dict[str, Any]) -> "AptDeb":
        """Create an AptDeb object from dictionary data."""
        return cls(**data)


class AptPPA(Apt):
    """PPA package repository definition."""

    ppa: str

    @classmethod
    def unmarshal(cls, data: Dict[str, Any]) -> "AptPPA":
        """Create an AptPPA object from dictionary data."""
        return cls(**data)


class AptUCA(Apt):
    """Ubuntu Cloud Archive repository definition."""

    cloud: str
    pocket: Optional[str]

    @classmethod
    def unmarshal(cls, data: Dict[str, Any]) -> "AptUCA":
        """Create an AptUCA object from dictionary data."""
        return cls(**data)


def validate_repository(data: Dict[str, Any]) -> None:
    """Validate a package repository.

    :param data: The repository data to validate.
    """
    if not isinstance(data, dict):  # pyright: reportUnnecessaryIsInstance=false
        raise TypeError("value must be a dictionary")
    try:
        if "ppa" in data:
            AptPPA(**data)
        elif "cloud" in data:
            AptUCA(**data)
        return
    except pydantic.ValidationError:
        pass

    AptDeb(**data)
