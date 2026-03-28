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

"""Data update coordinator for Nespresso BLE machines."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import timedelta

from bleak import BleakClient, BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .ble.parsing import (
    parse_barista_machine_info,
    parse_barista_status,
    parse_error_information,
    parse_general_user_settings,
    parse_serial_number,
    parse_vertuonext_machine_info,
    parse_vertuonext_status,
    parse_vmini_fota_status,
)
from .ble.protocol import get_protocol
from .const import (
    BARISTA_CHAR_STATUS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    VERTUO_CHAR_STATUS,
    MachineFamily,
)
from .models import NespressoMachineData, RawMachineData

_LOGGER = logging.getLogger(__name__)


class NespressoCoordinator(DataUpdateCoordinator[NespressoMachineData]):
    """Coordinator that connects to a Nespresso machine via BLE and reads status."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        family: MachineFamily,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        persistent: bool = False,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Nespresso {address}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.address = address
        self.family = family
        self.persistent = persistent
        self._client: BleakClient | None = None
        self._status_uuid = self._get_status_uuid()
        self._device_id: str | None = None

    def set_device_id(self, device_id: str) -> None:
        """Set the HA device ID for event firing."""
        self._device_id = device_id

    def _fire_state_triggers(self, new_data: NespressoMachineData) -> None:
        """Fire bus events for device triggers on state changes."""
        if self._device_id is None or self.data is None:
            return
        old_state = self.data.machine_state
        new_state = new_data.machine_state
        if old_state == new_state:
            return

        triggers = []
        if new_state == "brewing":
            triggers.append("brewing_started")
        if old_state == "brewing":
            triggers.append("brewing_finished")
        if new_state == "error":
            triggers.append("error_occurred")
        if new_state == "ready":
            triggers.append("ready")
        if new_state == "standby":
            triggers.append("standby")

        for trigger_type in triggers:
            self.hass.bus.async_fire(
                f"{DOMAIN}_state_change",
                {
                    "device_id": self._device_id,
                    "type": trigger_type,
                    "old_state": old_state,
                    "new_state": new_state,
                },
            )

    def _get_status_uuid(self) -> str | None:
        """Return the status characteristic UUID for GATT notifications."""
        if self.family == MachineFamily.BARISTA:
            return BARISTA_CHAR_STATUS
        if self.family == MachineFamily.VERTUO_NEXT:
            return VERTUO_CHAR_STATUS
        return None

    async def async_shutdown(self) -> None:
        """Disconnect persistent client on shutdown."""
        await self._disconnect()
        await super().async_shutdown()

    async def _disconnect(self) -> None:
        """Disconnect the persistent BLE client if connected."""
        if self._client is not None:
            try:
                await self._client.disconnect()
            except (BleakError, TimeoutError):
                pass
            self._client = None

    def _on_status_notification(self, _sender: object, data: bytearray) -> None:
        """Handle BLE GATT notification for status changes.

        This callback runs on the BLE thread, so schedule the update
        on the HA event loop.
        """
        self.hass.loop.call_soon_threadsafe(self._handle_status_update, bytes(data))

    def _handle_status_update(self, data: bytes) -> None:
        """Process status notification data on the event loop."""
        if self.data is None:
            return
        try:
            if self.family == MachineFamily.BARISTA:
                status = parse_barista_status(data)
            elif self.family == MachineFamily.VERTUO_NEXT:
                status = parse_vertuonext_status(data)
            else:
                return

            current = asdict(self.data)
            current["machine_state"] = str(status["machine_state"])
            current["error_present"] = bool(status["error_present"])

            if self.family == MachineFamily.VERTUO_NEXT:
                for key in (
                    "water_tank_empty",
                    "cleaning_needed",
                    "descaling_needed",
                    "led_signaling",
                    "capsule_container_full",
                    "brewing_unit_closed",
                    "milk_frother_running",
                    "cup_length_prog",
                ):
                    current[key] = bool(status.get(key, False))

            self.async_set_updated_data(NespressoMachineData(**current))
        except (ValueError, IndexError) as err:
            _LOGGER.debug("Failed to parse notification: %s", err)

    async def _async_update_data(self) -> NespressoMachineData:
        """Connect, read all characteristics, parse, disconnect."""
        # Disconnect any stale persistent client before reconnecting
        await self._disconnect()

        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is None:
            raise UpdateFailed("Machine not found; it may be off or out of range")

        try:
            client = await establish_connection(
                BleakClient,
                device,
                self.address,
                max_attempts=3,
            )
        except (BleakError, TimeoutError) as err:
            raise UpdateFailed(f"BLE connection failed: {err}") from err

        try:
            protocol = get_protocol(self.family)
            raw = await protocol.async_read_all(client)

            # Subscribe to notifications in persistent mode
            if self.persistent and self._status_uuid:
                await client.start_notify(
                    self._status_uuid, self._on_status_notification
                )
                self._client = client
            else:
                await client.disconnect()
        except (BleakError, TimeoutError) as err:
            await client.disconnect()
            raise UpdateFailed(f"BLE read failed: {err}") from err
        except Exception as err:
            await client.disconnect()
            raise UpdateFailed(f"Unexpected BLE error: {err}") from err

        try:
            result = self._parse(raw)
            self._fire_state_triggers(result)
            return result
        except (IndexError, ValueError, KeyError) as err:
            raise UpdateFailed(f"Failed to parse machine data: {err}") from err

    def _parse(self, raw: RawMachineData) -> NespressoMachineData:
        """Parse raw BLE data according to the machine family."""
        if self.family == MachineFamily.BARISTA:
            return self._parse_barista(raw)
        if self.family == MachineFamily.VERTUO_NEXT:
            return self._parse_vertuo(raw)
        return self._parse_vmini(raw)

    def _parse_barista(self, raw: RawMachineData) -> NespressoMachineData:
        assert raw.status_bytes is not None
        assert raw.info_bytes is not None

        status = parse_barista_status(raw.status_bytes)
        info = parse_barista_machine_info(raw.info_bytes)
        serial = parse_serial_number(raw.serial_bytes) if raw.serial_bytes else None

        return NespressoMachineData(
            machine_state=str(status["machine_state"]),
            error_present=bool(status["error_present"]),
            firmware_version=info.get("firmware_version"),
            hardware_version=info.get("hardware_version"),
            serial_number=serial,
            bluetooth_version=info.get("bluetooth_version"),
            motor_running=bool(status.get("motor_running", False)),
            induction_heating=bool(status.get("induction_heating", False)),
            setup_complete=bool(status.get("setup_complete", False)),
        )

    def _parse_vertuo(self, raw: RawMachineData) -> NespressoMachineData:
        assert raw.status_bytes is not None
        assert raw.info_bytes is not None

        status = parse_vertuonext_status(raw.status_bytes)
        info = parse_vertuonext_machine_info(raw.info_bytes)
        serial = parse_serial_number(raw.serial_bytes) if raw.serial_bytes else None

        water_hardness = None
        auto_power_off = None
        if raw.user_settings_bytes:
            settings = parse_general_user_settings(raw.user_settings_bytes)
            water_hardness = settings.get("water_hardness")
            auto_power_off = settings.get("auto_power_off")

        error_code = None
        if raw.error_info_bytes and len(raw.error_info_bytes) >= 3:
            err = parse_error_information(raw.error_info_bytes)
            error_code = err.get("error_code")

        return NespressoMachineData(
            machine_state=str(status["machine_state"]),
            error_present=bool(status["error_present"]),
            firmware_version=info.get("firmware_version"),
            hardware_version=info.get("hardware_version"),
            serial_number=serial,
            recipe_db_version=info.get("recipe_db_version"),
            connectivity_fw_version=info.get("connectivity_fw_version"),
            water_tank_empty=bool(status.get("water_tank_empty", False)),
            descaling_needed=bool(status.get("descaling_needed", False)),
            cleaning_needed=bool(status.get("cleaning_needed", False)),
            capsule_container_full=bool(status.get("capsule_container_full", False)),
            brewing_unit_closed=bool(status.get("brewing_unit_closed", False)),
            milk_frother_running=bool(status.get("milk_frother_running", False)),
            led_signaling=bool(status.get("led_signaling", False)),
            cup_length_prog=bool(status.get("cup_length_prog", False)),
            water_hardness=water_hardness,
            auto_power_off=auto_power_off,
            error_code=error_code,
        )

    def _parse_vmini(self, raw: RawMachineData) -> NespressoMachineData:
        serial = parse_serial_number(raw.serial_bytes) if raw.serial_bytes else None

        fota_status = None
        fota_progress = None
        if raw.fota_status_bytes:
            fota = parse_vmini_fota_status(raw.fota_status_bytes)
            fota_status = str(fota.get("fota_status", "unknown"))
            fota_progress = int(fota.get("fota_progress", 0))

        return NespressoMachineData(
            machine_state="unknown",
            error_present=False,
            firmware_version=raw.firmware_version,
            hardware_version=raw.software_version,
            serial_number=serial,
            shadow_data=raw.shadow_header,
            fota_status=fota_status,
            fota_progress=fota_progress,
        )
