# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2021-2022 Canonical Ltd.
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

"""Utilities for craft_archives."""
import logging
import pathlib
import platform
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OSPlatform:
    """Platform definition for a given host."""

    system: str
    release: str
    machine: str

    def __str__(self) -> str:
        """Return the string representation of an OSPlatform."""
        return f"{self.system}/{self.release} ({self.machine})"


# architecture translations from the platform syntax to the deb/snap syntax
# These two architecture mappings are almost inverses of each other, except one map is
# not reversible (same value for different keys)
_ARCH_TRANSLATIONS_PLATFORM_TO_DEB = {
    "aarch64": "arm64",
    "armv7l": "armhf",
    "i686": "i386",
    "ppc": "powerpc",
    "ppc64le": "ppc64el",
    "x86_64": "amd64",
    "AMD64": "amd64",  # Windows support
    "s390x": "s390x",
    "riscv64": "riscv64",
}


_32BIT_USERSPACE_ARCHITECTURE = {
    "aarch64": "armv7l",
    "armv8l": "armv7l",
    "ppc64le": "ppc",
    "x86_64": "i686",
}


def get_os_platform(filepath=pathlib.Path("/etc/os-release")):
    """Determine a system/release combo for an OS using /etc/os-release if available."""
    system = platform.system()
    release = platform.release()
    machine = platform.machine()

    if system == "Linux":
        try:
            with filepath.open("rt", encoding="utf-8") as release_file:
                lines = release_file.readlines()
        except FileNotFoundError:
            logger.debug("Unable to locate 'os-release' file, using default values")
        else:
            os_release = {}
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.rstrip().split("=", 1)
                if value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                os_release[key] = value
            system = os_release.get("ID", system)
            release = os_release.get("VERSION_ID", release)

    return OSPlatform(system=system, release=release, machine=machine)


def get_host_architecture():
    """Get host architecture in deb format suitable for base definition."""
    os_platform_machine = get_os_platform().machine

    if platform.architecture()[0] == "32bit":
        userspace = _32BIT_USERSPACE_ARCHITECTURE.get(os_platform_machine)
        if userspace:
            os_platform_machine = userspace

    return _ARCH_TRANSLATIONS_PLATFORM_TO_DEB.get(
        os_platform_machine, os_platform_machine
    )
