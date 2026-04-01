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

"""Button entities for Nespresso Smart integration."""

from __future__ import annotations

import logging

from bleak import BleakError
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MACHINE_FAMILY_NAMES,
    VERTUO_CHAR_COMMAND_REQ,
    VMINI_CHAR_FOTA_COMMAND,
    MachineFamily,
)
from .coordinator import NespressoCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nespresso button entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: NespressoCoordinator = data["coordinator"]
    family = MachineFamily(entry.data["family"])

    entities: list[ButtonEntity] = []
    if family == MachineFamily.VMINI:
        entities.append(NespressoFotaCheckButton(coordinator, entry))
    if family == MachineFamily.VERTUO_NEXT:
        entities.append(NespressoVertuoBrewButton(coordinator, entry))
    async_add_entities(entities)


class NespressoFotaCheckButton(CoordinatorEntity[NespressoCoordinator], ButtonEntity):
    """Button to check for firmware updates on VMini."""

    _attr_has_entity_name = True
    _attr_name = "Check firmware update"
    _attr_icon = "mdi:cellphone-arrow-down"

    def __init__(
        self,
        coordinator: NespressoCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._address = entry.data["address"]
        self._attr_unique_id = f"{self._address}_fota_check"
        family = MachineFamily(entry.data["family"])
        data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=entry.data.get("name", "Nespresso"),
            manufacturer="Nespresso",
            model=MACHINE_FAMILY_NAMES.get(family, "Unknown"),
            serial_number=data.serial_number if data else None,
            sw_version=data.firmware_version if data else None,
            hw_version=data.hardware_version if data else None,
        )

    async def async_press(self) -> None:
        """Send CHECK_FOR_UPDATE command (0x00) to CHAR_FOTA_COMMAND."""
        try:
            await self.coordinator.async_write_char(
                VMINI_CHAR_FOTA_COMMAND, bytes([0x00])
            )
            _LOGGER.info("FOTA check command sent to %s", self._address)
            await self.coordinator.async_request_refresh()
        except (BleakError, TimeoutError) as err:
            _LOGGER.error("Failed to send FOTA check: %s", err)


class NespressoVertuoBrewButton(CoordinatorEntity[NespressoCoordinator], ButtonEntity):
    """Button to start brewing on Vertuo Next.

    Uses the brew type and temperature from the corresponding select entities.
    Command format: [cmdID=3, subCmdID=5, dataControl=7, 4, 0, 0, 0, 0, temp, brew_type]
    Written to CHAR_COMMAND_REQ (06AA3A42).
    """

    _attr_has_entity_name = True
    _attr_name = "Brew"
    _attr_icon = "mdi:coffee"

    def __init__(
        self,
        coordinator: NespressoCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._address = entry.data["address"]
        self._attr_unique_id = f"{self._address}_vertuo_brew"
        family = MachineFamily(entry.data["family"])
        data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=entry.data.get("name", "Nespresso"),
            manufacturer="Nespresso",
            model=MACHINE_FAMILY_NAMES.get(family, "Unknown"),
            serial_number=data.serial_number if data else None,
            sw_version=data.firmware_version if data else None,
            hw_version=data.hardware_version if data else None,
        )

    async def async_press(self) -> None:
        """Send brew command to the machine.

        Waits for the machine to reach a brewable state (ready, heating
        will resolve on its own). Times out after 120 seconds.
        """
        import asyncio

        from .select import VERTUO_BREW_TYPE_VALUES, VERTUO_TEMPERATURE_VALUES

        brewable = {"ready", "ready_old_capsule"}
        waiting = {"heating", "initializing"}

        # Wait for machine to be ready
        state = self.coordinator.data.machine_state if self.coordinator.data else None
        if state in waiting:
            _LOGGER.info("Machine is %s, waiting for ready...", state)
            for _ in range(24):  # 24 * 5s = 120s max
                await asyncio.sleep(5)
                await self.coordinator.async_request_refresh()
                state = (
                    self.coordinator.data.machine_state
                    if self.coordinator.data
                    else None
                )
                if state not in waiting:
                    break
            else:
                _LOGGER.error("Timeout waiting for machine to be ready")
                return

        if state not in brewable:
            _LOGGER.error(
                "Machine is in state '%s', cannot brew (need: %s)", state, brewable
            )
            return

        brew_type = VERTUO_BREW_TYPE_VALUES.get(self.coordinator.brew_type, 1)
        temp = VERTUO_TEMPERATURE_VALUES.get(self.coordinator.brew_temperature, 0)

        # CCommandReq wire format: 19 bytes (matches APK CharacCommandReq.setValue)
        buf = bytearray(19)
        buf[0] = 3  # cmdID: machine command
        buf[1] = 5  # subCmdID: start brew
        buf[2] = 7  # dataControl: dataLength=7
        buf[3] = 4  # data[0]: brew subtype
        buf[8] = temp  # data[5]: temperature
        buf[9] = brew_type  # data[6]: brew type

        _LOGGER.info(
            "Brewing on %s: type=%d temp=%d cmd=%s",
            self._address,
            brew_type,
            temp,
            buf.hex(),
        )

        try:
            await self.coordinator.async_write_char(VERTUO_CHAR_COMMAND_REQ, bytes(buf))
            _LOGGER.info("Brew command sent to %s", self._address)
            await self.coordinator.async_request_refresh()
        except (BleakError, TimeoutError) as err:
            _LOGGER.error("Failed to send brew command: %s", err)
