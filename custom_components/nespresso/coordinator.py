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

import asyncio
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
    parse_caps_counter,
    parse_barista_machine_params,
    parse_error_information,
    parse_profile_version,
    parse_general_user_settings,
    parse_serial_number,
    parse_vertuonext_machine_info,
    parse_vertuonext_status,
    parse_vmini_fota_status,
)
from .ble.protocol import generate_auth_key, get_protocol
from .ble.recipe import parse_recipe_info
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
        self.auth_key: str | None = None
        self._ble_lock = asyncio.Lock()
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

        _LOGGER.debug(
            "State transition: %s -> %s, triggers=%s", old_state, new_state, triggers
        )
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
        client = self._client
        self._client = None  # Clear reference first to prevent re-entry
        if client is not None:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    def _on_status_notification(self, _sender: object, data: bytearray) -> None:
        """Handle BLE GATT notification for status changes.

        This callback runs on the BLE thread, so schedule the update
        on the HA event loop.
        """
        _LOGGER.debug("BLE notification received: %s (len=%d)", data.hex(), len(data))
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
                    "bootloader_active",
                ):
                    current[key] = bool(status.get(key, False))

            self.async_set_updated_data(NespressoMachineData(**current))
        except (ValueError, IndexError) as err:
            _LOGGER.debug("Failed to parse notification: %s", err)

    async def async_read_modify_write_char(
        self, char_uuid: str, modify_fn: object
    ) -> None:
        """Read a characteristic, modify it, and write back atomically.

        modify_fn receives a bytearray and should mutate it in place.
        """
        async with self._ble_lock:
            device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if device is None:
                raise BleakError("Machine not found")

            client = await establish_connection(
                BleakClient, device, self.address, max_attempts=2
            )
            try:
                if self.auth_key:
                    from .ble.protocol import _authenticate, _try_pair

                    await _try_pair(client)
                    await _authenticate(client, self.auth_key, self.family)
                    await asyncio.sleep(1)

                current = await client.read_gatt_char(char_uuid)
                _LOGGER.debug(
                    "Read-modify-write %s current: %s", char_uuid, current.hex()
                )
                data = bytearray(current)
                modify_fn(data)  # type: ignore[operator]
                _LOGGER.debug("Read-modify-write %s new: %s", char_uuid, data.hex())
                await client.write_gatt_char(char_uuid, bytes(data), response=True)
            finally:
                await client.disconnect()

    async def async_write_char(self, char_uuid: str, data: bytes) -> None:
        """Write to a BLE characteristic with proper locking and auth.

        Acquires the BLE lock to prevent concurrent connections, connects
        with auth, writes, disconnects, and refreshes.
        """
        async with self._ble_lock:
            device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if device is None:
                raise BleakError("Machine not found")

            client = await establish_connection(
                BleakClient, device, self.address, max_attempts=2
            )
            try:
                if self.auth_key:
                    from .ble.protocol import _authenticate, _try_pair

                    await _try_pair(client)
                    await _authenticate(client, self.auth_key, self.family)
                    await asyncio.sleep(1)

                await client.write_gatt_char(char_uuid, data, response=True)
                _LOGGER.debug("Write %s: %s", char_uuid, data.hex())
            finally:
                await client.disconnect()

    async def _async_update_data(self) -> NespressoMachineData:
        """Connect, read all characteristics, parse, disconnect."""
        async with self._ble_lock:
            return await self._async_update_data_locked()

    async def _async_update_data_locked(self) -> NespressoMachineData:
        """Actual update logic, must be called under _ble_lock."""
        _LOGGER.debug(
            "Update cycle start: address=%s family=%s persistent=%s",
            self.address,
            self.family.value,
            self.persistent,
        )
        # Disconnect any stale persistent client before reconnecting
        await self._disconnect()

        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is None:
            _LOGGER.debug("Device %s not found in BLE cache", self.address)
            raise UpdateFailed("Machine not found; it may be off or out of range")

        _LOGGER.debug(
            "Connecting to %s (name=%r rssi=%s)",
            device.address,
            device.name,
            getattr(device, "rssi", "N/A"),
        )

        try:
            client = await establish_connection(
                BleakClient,
                device,
                self.address,
                max_attempts=3,
            )
        except (BleakError, TimeoutError) as err:
            _LOGGER.debug("Connection failed: %s", err)
            raise UpdateFailed(f"BLE connection failed: {err}") from err

        _LOGGER.debug("Connected to %s, MTU=%s", self.address, client.mtu_size)

        try:
            if self.auth_key is None:
                self.auth_key = generate_auth_key()
                _LOGGER.debug("Generated new auth key: %s****", self.auth_key[:4])

            # Auth upfront - all families require it (CMID or MachineToken)
            from .ble.protocol import _authenticate, _try_pair

            await _try_pair(client)
            await _authenticate(client, self.auth_key, self.family)

            protocol = get_protocol(self.family)
            raw = await protocol.async_read_all(client, self.auth_key)

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
            _LOGGER.debug(
                "Parsed %s: state=%s error=%s fw=%s hw=%s serial=%s",
                self.family.value,
                result.machine_state,
                result.error_present,
                result.firmware_version,
                result.hardware_version,
                result.serial_number,
            )
            self._fire_state_triggers(result)
            return result
        except (IndexError, ValueError, KeyError) as err:
            _LOGGER.debug("Parse failed: %s (raw=%r)", err, raw)
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
            profile_version=parse_profile_version(raw.profile_version_bytes)
            if raw.profile_version_bytes
            else None,
            bootloader_version=info.get("bootloader_version"),
            bluetooth_version=info.get("bluetooth_version"),
            motor_running=bool(status.get("motor_running", False)),
            induction_heating=bool(status.get("induction_heating", False)),
            setup_complete=bool(status.get("setup_complete", False)),
            recipe_count=parse_recipe_info(raw.recipe_info_bytes).max_recipes
            if raw.recipe_info_bytes and len(raw.recipe_info_bytes) >= 8
            else None,
            ble_disabled=parse_barista_machine_params(raw.machine_params_bytes).get(
                "ble_disabled", False
            )
            if raw.machine_params_bytes
            else None,
            gatt_dump=raw.gatt_dump,
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

        caps_counter = None
        if raw.caps_counter_bytes:
            caps_counter = parse_caps_counter(raw.caps_counter_bytes)

        return NespressoMachineData(
            machine_state=str(status["machine_state"]),
            error_present=bool(status["error_present"]),
            firmware_version=info.get("firmware_version"),
            hardware_version=info.get("hardware_version"),
            serial_number=serial,
            profile_version=parse_profile_version(raw.profile_version_bytes)
            if raw.profile_version_bytes
            else None,
            bootloader_version=info.get("bootloader_version"),
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
            caps_counter=caps_counter,
            error_list_code=parse_error_information(raw.error_list_bytes).get(
                "error_code"
            )
            if raw.error_list_bytes and len(raw.error_list_bytes) >= 3
            else None,
            iot_market_name=parse_serial_number(raw.iot_market_bytes)
            if raw.iot_market_bytes
            else None,
            gatt_dump=raw.gatt_dump,
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
            gatt_dump=raw.gatt_dump,
        )
