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

import http
import urllib.error
from unittest.mock import Mock, patch

import pytest
from craft_archives.repo import apt_uca, errors


@patch("urllib.request.urlopen", return_value=Mock(status=http.HTTPStatus.OK))
def test_check_release_compatibility(urllib):
    assert apt_uca.check_release_compatibility("jammy", "antelope") is None


@patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("", http.HTTPStatus.NOT_FOUND, "NOT FOUND", {}, None))  # type: ignore
def test_check_release_compatibility_invalid(urllib):
    with pytest.raises(
        errors.AptUCAInstallError,
        match="Failed to install UCA 'invalid-cloud/updates': not a valid release for 'jammy'",
    ):
        apt_uca.check_release_compatibility("jammy", "invalid-cloud")


@patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("", http.HTTPStatus.BAD_GATEWAY, "BAD GATEWAY", {}, None))  # type: ignore
def test_check_release_compatibility_bad_gateway(urllib):
    with pytest.raises(
        errors.AptUCAInstallError,
        match="Failed to install UCA 'antelope/updates': unexpected status code 502: 'BAD GATEWAY' while fetching release",
    ):
        apt_uca.check_release_compatibility("jammy", "antelope")
