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
    CONF_FORCE_BREW_BUTTON,
    DOMAIN,
    MACHINE_FAMILY_NAMES,
    MILK_PLATFORM_CODES,
    NO_BREW_PLATFORM_CODES,
    VERTUO_PLATFORM_NAMES,
    MachineFamily,
)

if TYPE_CHECKING:
    # Only the annotations need it, and importing the coordinator for real
    # would drag Home Assistant in behind it, which the tests do not have.
    from .coordinator import NespressoCoordinator


def is_expert(entry: ConfigEntry) -> bool:
    """Whether the entry is a Nespresso Expert, as the app's ExpertModule decides.

    From the name the machine advertised when it was added. The title would do
    until someone renames the entry.
    """
    return "expert" in (entry.data.get("name") or "").lower()


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

    Only the Venus profile needs this. A Barista and a Vertuo Up are already
    named by their family, and searching their serials for a three character
    code would only invent matches. The Expert shares the profile but is not a
    Vertuo, and its name already says what it is.
    """
    if coordinator.is_expert:
        return "Expert"
    code = platform_code(entry, coordinator)
    if code is not None:
        return VERTUO_PLATFORM_NAMES[code]
    family = MachineFamily(entry.data["family"])
    return MACHINE_FAMILY_NAMES.get(family, "Unknown")


def device_name(entry: ConfigEntry, coordinator: NespressoCoordinator) -> str:
    """Name the device after its model, unless the model is only a guess.

    A Venus machine with no platform code anywhere is a Vertuo Next by default
    only. It may be a model the table does not know or another machine on the
    same profile, so it keeps the name it advertised.
    """
    if (
        MachineFamily(entry.data["family"]) == MachineFamily.VERTUO_NEXT
        and platform_code(entry, coordinator) is None
    ):
        return entry.data.get("name", "Nespresso")
    return machine_model(entry, coordinator)


def supports_brewing(entry: ConfigEntry, coordinator: NespressoCoordinator) -> bool:
    """Whether to offer brewing on this machine.

    The Pop and the Creatista acknowledge every brew frame we have and stay
    idle, so a button and its two settings would be furniture. The option
    overrides that, because "this model does not brew" is a conclusion drawn
    from a handful of machines and the way to revisit it is to let someone try.
    """
    if entry.options.get(CONF_FORCE_BREW_BUTTON, False):
        return True
    return platform_code(entry, coordinator) not in NO_BREW_PLATFORM_CODES


def has_milk_unit(entry: ConfigEntry, coordinator: NespressoCoordinator) -> bool:
    """Whether this machine has a milk system.

    Only the Creatista and the Lattissima do. On anything else the milk nibble
    would read "offline" for ever, and an entity that can only say no is worse
    than no entity.
    """
    return platform_code(entry, coordinator) in MILK_PLATFORM_CODES


def machine_device_info(
    entry: ConfigEntry, coordinator: NespressoCoordinator
) -> DeviceInfo:
    """Describe the machine to the device registry.

    Twelve entities spelled this out identically, which was eleven chances for
    two of them to disagree about what the device is called.
    """
    info = DeviceInfo(
        identifiers={(DOMAIN, entry.data["address"])},
        name=device_name(entry, coordinator),
        manufacturer="Nespresso",
        model=machine_model(entry, coordinator),
    )
    info.update(device_versions(coordinator))
    return info


def device_versions(coordinator: NespressoCoordinator) -> DeviceInfo:
    """The serial and versions the machine has told us, and only those.

    A field passed as None clears what the registry holds, so a Vertuo Up set
    up while asleep, which reports none of them, would lose them for good.
    """
    info = DeviceInfo()
    data = coordinator.data
    if data is None:
        return info
    if data.serial_number is not None:
        info["serial_number"] = data.serial_number
    if data.firmware_version is not None:
        info["sw_version"] = data.firmware_version
    if data.hardware_version is not None:
        info["hw_version"] = data.hardware_version
    return info
