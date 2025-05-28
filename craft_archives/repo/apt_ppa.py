# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2020-2023 Canonical Ltd.
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

"""Personal Package Archive helpers."""

# pyright: reportMissingTypeStubs=false
# Eliminate launchpadlib typing issues:
# pyright: reportUnknownMemberType=false

import logging
from typing import cast

import lazr.restfulclient.errors  # type: ignore
from launchpadlib.launchpad import Launchpad  # type: ignore

from . import errors

logger = logging.getLogger(__name__)


def split_ppa_parts(*, ppa: str) -> tuple[str, str]:
    """Obtain user and repository components from a PPA line."""
    ppa_split = ppa.split("/")
    if len(ppa_split) != 2:  # noqa: PLR2004
        raise errors.AptPPAInstallError(ppa, "invalid PPA format")
    return ppa_split[0], ppa_split[1]


def get_launchpad_ppa_key_id(*, ppa: str) -> str:
    """Query Launchpad for PPA's key ID."""
    owner, name = split_ppa_parts(ppa=ppa)
    launchpad = Launchpad.login_anonymously("snapcraft", "production")
    launchpad_url = f"~{owner}/+archive/{name}"

    logger.debug(f"Loading launchpad url: {launchpad_url}")
    try:
        key_id: str = cast(str, launchpad.load(launchpad_url).signing_key_fingerprint)
    except lazr.restfulclient.errors.NotFound as error:
        raise errors.AptPPAInstallError(ppa, "not found on launchpad") from error

    logger.debug(f"Retrieved launchpad PPA key ID: {key_id}")

    return key_id
