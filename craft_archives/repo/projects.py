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

from typing import Any, Dict

from craft_archives.repo.package_repository import PackageRepository


def validate_repository(data: Dict[str, Any]) -> None:
    """Validate a package repository.

    :param data: The repository data to validate.
    """
    if not isinstance(data, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError("value must be a dictionary")
    PackageRepository.unmarshal(data)
