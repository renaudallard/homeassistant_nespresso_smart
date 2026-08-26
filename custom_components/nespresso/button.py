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

from .ble.protocol import build_command_frame
from .const import (
    DOMAIN,
    MACHINE_FAMILY_NAMES,
    VERTUO_CHAR_COMMAND_REQ,
    VERTUO_CHAR_COMMAND_RSP,
    VMINI_CHAR_FOTA_COMMAND,
    MachineFamily,
)
from .coordinator import NespressoCoordinator

_LOGGER = logging.getLogger(__name__)

# Vertuo platform codes with no BLE brew support. The Nespresso app itself
# offers no brew button for these models and the machine ignores every known
# brew command, so exposing a button that silently does nothing is worse than
# not exposing one. The code appears both in the serial number
# ("23222CV2f2001582072") and in the BLE name ("CV2_5443B29C51B2").
NO_BREW_PLATFORM_CODES = ("CV2",)


def _supports_brewing(coordinator: NespressoCoordinator, entry: ConfigEntry) -> bool:
    """Return False for Vertuo models known to reject BLE brew commands."""
    data = coordinator.data
    candidates = (
        entry.data.get("name") or "",
        (data.serial_number if data else None) or "",
        (data.iot_market_name if data else None) or "",
    )
    for text in candidates:
        upper = text.upper()
        for code in NO_BREW_PLATFORM_CODES:
            if code in upper:
                _LOGGER.debug(
                    "Brew button skipped: %r matches non-brewing model %s", text, code
                )
                return False
    return True


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
    if family == MachineFamily.VERTUO_NEXT and _supports_brewing(coordinator, entry):
        entities.append(NespressoVertuoBrewButton(coordinator, entry))
    # Only Vertuo Next: the derived counters this button resets are only
    # created for that family.
    if family == MachineFamily.VERTUO_NEXT:
        entities.append(NespressoResetDescalingButton(coordinator, entry))
    async_add_entities(entities)


class NespressoResetDescalingButton(
    CoordinatorEntity[NespressoCoordinator], ButtonEntity
):
    """Reset the descaling counter after actually descaling the machine."""

    _attr_has_entity_name = True
    _attr_name = "Reset descaling counter"
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator: NespressoCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._address = entry.data["address"]
        self._attr_unique_id = f"{self._address}_reset_descaling"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=entry.data.get("name", "Nespresso"),
            manufacturer="Nespresso",
        )

    @property
    def available(self) -> bool:
        """Local counter, so it works even when the machine is unreachable."""
        return True

    async def async_press(self) -> None:
        """Zero the brew count and restart the descaling clock."""
        self.coordinator.async_reset_descaling()


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
        self._brew_pending = False
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

        Only one brew at a time. If pressed multiple times while waiting,
        subsequent presses are ignored.
        """
        if self._brew_pending:
            _LOGGER.debug("Brew already pending, ignoring duplicate press")
            return
        self._brew_pending = True

        try:
            await self._do_brew()
        finally:
            self._brew_pending = False
            await self.coordinator.async_release_kept_connection()

    async def _do_brew(self) -> None:
        """Internal brew logic."""
        import asyncio

        from .select import VERTUO_BREW_TYPE_VALUES, VERTUO_TEMPERATURE_VALUES

        # Tell the coordinator to keep the next poll connection alive
        # so we can send the brew on the same authenticated session
        self.coordinator._keep_connection = True

        waiting = {"heating", "initializing", "ready_old_capsule"}
        waking = {"power_save", "standby"}

        # Wait for machine to be ready
        state = self.coordinator.data.machine_state if self.coordinator.data else None
        if state in waking:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": "The machine is in power save mode. "
                    "Press the button on the machine to wake it up. "
                    "Brewing will start automatically when the machine is ready.",
                    "title": "Nespresso: machine asleep",
                    "notification_id": "nespresso_power_save",
                },
            )
            _LOGGER.info("Machine is %s, waiting up to 5 min for wake...", state)
            import time

            deadline = time.monotonic() + 300
            while state in waking and time.monotonic() < deadline:
                await asyncio.sleep(5)
                await self.coordinator.async_request_refresh()
                state = (
                    self.coordinator.data.machine_state
                    if self.coordinator.data
                    else None
                )
            await self.hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {"notification_id": "nespresso_power_save"},
            )
            if state in waking:
                _LOGGER.error("Timeout waiting for machine to wake up")
                return
        if state == "ready_old_capsule":
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": "Please eject the used capsule and insert a fresh one. "
                    "Brewing will start automatically when the machine is ready.",
                    "title": "Nespresso: replace capsule",
                    "notification_id": "nespresso_capsule",
                },
            )
        if state in waiting:
            _LOGGER.info("Machine is %s, waiting for ready...", state)
            while state in waiting:
                await asyncio.sleep(5)
                await self.coordinator.async_request_refresh()
                state = (
                    self.coordinator.data.machine_state
                    if self.coordinator.data
                    else None
                )

        if state != "ready":
            _LOGGER.error("Machine is in state '%s', cannot brew (need: ready)", state)
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"The machine is in state '{state}' and cannot brew. "
                    "It needs to be in 'ready' state.",
                    "title": "Nespresso: cannot brew",
                    "notification_id": "nespresso_brew_error",
                },
            )
            return

        await self.hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": "nespresso_capsule"},
        )

        brew_type = VERTUO_BREW_TYPE_VALUES.get(self.coordinator.brew_type, 1)
        temp = VERTUO_TEMPERATURE_VALUES.get(self.coordinator.brew_temperature, 0)

        # Try simple CCommandReq first (works on Vertuo Next).
        #
        # CharacCommandReq.setValue in the APK allocates 19 bytes and so does
        # the response: three header bytes and a fixed 16-byte data array. This
        # was 10 bytes, the length of a packet capture from a Vertuo Next, and
        # that machine answers a short write anyway. A Creatista does not: it
        # acknowledges the write, says nothing, and does not brew.
        buf = build_command_frame(
            3,  # cmdID: machine command
            5,  # subCmdID: start brew
            bytes([4, 0, 0, 0, 0, temp, brew_type]),
        )

        _LOGGER.info(
            "Brewing on %s: type=%d temp=%d cmd=%s",
            self._address,
            brew_type,
            temp,
            buf.hex(),
        )

        try:
            rsp = await self.coordinator.async_send_command(
                VERTUO_CHAR_COMMAND_REQ, VERTUO_CHAR_COMMAND_RSP, buf
            )
            if rsp:
                _LOGGER.info("Brew response from %s: %s", self._address, rsp.hex())
            else:
                # Only a Vertuo Next has ever answered this. A Pop and a
                # Creatista both take the write and do nothing, and the
                # official app has no BLE brew command for any model, so
                # there is nothing else to try.
                _LOGGER.warning(
                    "%s did not answer the brew command. Brewing over Bluetooth is "
                    "only known to work on a Vertuo Next.",
                    self._address,
                )
            await self.coordinator.async_request_refresh()
        except (BleakError, TimeoutError) as err:
            _LOGGER.error("Failed to send brew command: %s", err)
