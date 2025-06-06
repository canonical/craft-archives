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

"""Ubuntu Cloud Archive helpers."""

import http
import urllib.error
import urllib.request

from . import errors
from .package_repository import (
    UCA_ARCHIVE,
    PocketUCAEnum,
)


def check_release_compatibility(
    codename: str, cloud: str, pocket: PocketUCAEnum = PocketUCAEnum.UPDATES
) -> None:
    """Raise an exception if the release is incompatible with codename."""
    request = UCA_ARCHIVE + f"/dists/{codename}-{pocket.value}/{cloud}/"
    try:
        urllib.request.urlopen(request)  # noqa: S310, mitigated because UCA_ARCHIVE is hardcoded to a trusted protocol
    except urllib.error.HTTPError as e:
        if e.code == http.HTTPStatus.NOT_FOUND:
            raise errors.AptUCAInstallError(
                cloud, pocket.value, f"not a valid release for {codename!r}"
            )
        raise errors.AptUCAInstallError(
            cloud,
            pocket.value,
            f"unexpected status code {e.code}: {e.reason!r} while fetching release",
        )
