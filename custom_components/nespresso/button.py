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

from bleak import BleakClient, BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MACHINE_FAMILY_NAMES, VMINI_CHAR_FOTA_COMMAND, MachineFamily
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
        device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if device is None:
            _LOGGER.error("Machine not found for FOTA check")
            return

        try:
            client = await establish_connection(
                BleakClient, device, self._address, max_attempts=2
            )
            try:
                _LOGGER.debug("Sending FOTA CHECK_FOR_UPDATE to %s", self._address)
                await client.write_gatt_char(
                    VMINI_CHAR_FOTA_COMMAND, bytes([0x00]), response=True
                )
                _LOGGER.info("FOTA check command sent to %s", self._address)
            finally:
                await client.disconnect()
            await self.coordinator.async_request_refresh()
        except (BleakError, TimeoutError) as err:
            _LOGGER.error("Failed to send FOTA check: %s", err)
