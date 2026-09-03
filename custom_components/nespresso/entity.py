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

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MACHINE_FAMILY_NAMES, MachineFamily
from .coordinator import NespressoCoordinator


def machine_device_info(
    entry: ConfigEntry, coordinator: NespressoCoordinator
) -> DeviceInfo:
    """Describe the machine to the device registry.

    Twelve entities spelled this out identically, which was eleven chances for
    two of them to disagree about what the device is called.
    """
    family = MachineFamily(entry.data["family"])
    data = coordinator.data
    return DeviceInfo(
        identifiers={(DOMAIN, entry.data["address"])},
        name=entry.data.get("name", "Nespresso"),
        manufacturer="Nespresso",
        model=MACHINE_FAMILY_NAMES.get(family, "Unknown"),
        serial_number=data.serial_number if data else None,
        sw_version=data.firmware_version if data else None,
        hw_version=data.hardware_version if data else None,
    )
