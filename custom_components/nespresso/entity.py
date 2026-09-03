# Copyright (c) 2026, Renaud Allard <renaud@allard.it>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""The machine every entity of a config entry hangs off."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN,
    MACHINE_FAMILY_NAMES,
    VERTUO_PLATFORM_NAMES,
    MachineFamily,
)

if TYPE_CHECKING:
    # Only the annotations need it, and importing the coordinator for real
    # would drag Home Assistant in behind it, which the tests do not have.
    from .coordinator import NespressoCoordinator


def platform_code(entry: ConfigEntry, coordinator: NespressoCoordinator) -> str | None:
    """Return the machine's platform code, if anything it told us carries one.

    Three places can hold it and none of them is always there: the BLE name is
    missing from some advertisements, and the serial and the market name only
    arrive with the first successful read.
    """
    if MachineFamily(entry.data["family"]) != MachineFamily.VERTUO_NEXT:
        return None
    data = coordinator.data
    for text in (
        entry.data.get("name") or "",
        (data.serial_number if data else None) or "",
        (data.iot_market_name if data else None) or "",
    ):
        upper = text.upper()
        for code in VERTUO_PLATFORM_NAMES:
            if code in upper:
                return code
    return None


def machine_model(entry: ConfigEntry, coordinator: NespressoCoordinator) -> str:
    """Name the model, falling back to the family when nothing says more.

    Only the Venus profile needs this. A Barista and a Vertuo Mini are already
    named by their family, and searching their serials for a three character
    code would only invent matches.
    """
    code = platform_code(entry, coordinator)
    if code is not None:
        return VERTUO_PLATFORM_NAMES[code]
    family = MachineFamily(entry.data["family"])
    return MACHINE_FAMILY_NAMES.get(family, "Unknown")


def machine_device_info(
    entry: ConfigEntry, coordinator: NespressoCoordinator
) -> DeviceInfo:
    """Describe the machine to the device registry.

    Twelve entities spelled this out identically, which was eleven chances for
    two of them to disagree about what the device is called.
    """
    data = coordinator.data
    return DeviceInfo(
        identifiers={(DOMAIN, entry.data["address"])},
        name=entry.data.get("name", "Nespresso"),
        manufacturer="Nespresso",
        model=machine_model(entry, coordinator),
        serial_number=data.serial_number if data else None,
        sw_version=data.firmware_version if data else None,
        hw_version=data.hardware_version if data else None,
    )
