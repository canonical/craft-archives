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
import urllib.parse
import urllib.request

from . import errors
from .package_repository import (
    UCA_ARCHIVE,
    UCA_DEFAULT_POCKET,
)


def check_release_compatibility(
    codename: str, cloud: str, pocket: str = UCA_DEFAULT_POCKET
) -> None:
    """Raise an exception if the release is incompatible with codename."""
    request = UCA_ARCHIVE + f"/dists/{codename}-{pocket}/{cloud}/"
    try:
        urllib.request.urlopen(request)
    except urllib.error.HTTPError as e:
        if e.code == http.HTTPStatus.NOT_FOUND:
            raise errors.AptUCAInstallError(
                cloud, pocket, f"not a valid release for {codename!r}"
            )
        raise errors.AptUCAInstallError(
            cloud,
            pocket,
            f"unexpected status code {e.code}: {e.reason!r} while fetching release",
        )
