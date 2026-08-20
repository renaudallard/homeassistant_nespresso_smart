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
import json
import logging
import time
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

from bleak import BleakClient, BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .ble.parsing import (
    parse_barista_machine_info,
    parse_barista_machine_params,
    parse_barista_status,
    parse_caps_counter,
    parse_error_information,
    parse_general_user_settings,
    parse_profile_version,
    parse_serial_number,
    parse_venus_advertisement,
    parse_vertuonext_machine_info,
    parse_vertuonext_status,
    parse_vmini_fota_status,
)
from .ble.protocol import generate_auth_key, get_protocol
from .ble.recipe import parse_recipe_info
from .const import (
    BARISTA_CHAR_STATUS,
    COUNTER_SAVE_DELAY,
    COUNTER_STORAGE_VERSION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    VERTUO_CHAR_STATUS,
    MachineFamily,
)
from .models import NespressoMachineData, RawMachineData

_LOGGER = logging.getLogger(__name__)

_VERSION = json.loads((Path(__file__).parent / "manifest.json").read_text()).get(
    "version", "unknown"
)


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
        self.brew_type: str = "espresso"
        self.brew_temperature: str = "medium"
        self._keep_connection = False
        self._ble_lock = asyncio.Lock()

        # Brew counters. Persisted separately from the config entry so a
        # reload does not reset them.
        self.brew_total = 0
        self.brews_since_descaling = 0
        self.last_descaling: float | None = None
        self.descaling_capsules = 0
        self.descaling_days = 0
        self._counter_store: Store = Store(
            hass, COUNTER_STORAGE_VERSION, f"{DOMAIN}.counters.{address}"
        )
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
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error disconnecting BLE client: %s", err)

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
                ):
                    current[key] = bool(status.get(key, False))

            self._async_track_brew(self.data.machine_state, current["machine_state"])
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
                    from .ble.protocol import _authenticate

                    await _authenticate(client, self.auth_key, self.family)

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

            try:
                client = await establish_connection(
                    BleakClient, device, self.address, max_attempts=2
                )
            except (BleakError, TimeoutError) as err:
                if "connection abort" not in str(err).lower():
                    raise
                _LOGGER.info("Write connection abort, clearing stale bond")
                try:
                    tmp = BleakClient(device)
                    await tmp.unpair()
                except Exception as unpair_err:  # noqa: BLE001
                    _LOGGER.debug("Failed to clear stale bond: %s", unpair_err)
                await asyncio.sleep(3)
                device = bluetooth.async_ble_device_from_address(
                    self.hass, self.address, connectable=True
                )
                if device is None:
                    raise
                client = await establish_connection(
                    BleakClient, device, self.address, max_attempts=2
                )

            try:
                if self.auth_key:
                    from .ble.protocol import _authenticate

                    await _authenticate(client, self.auth_key, self.family)

                await client.write_gatt_char(char_uuid, data, response=True)
                _LOGGER.debug("Write %s: %s", char_uuid, data.hex())
            finally:
                await client.disconnect()

    async def async_send_command(
        self, cmd_uuid: str, rsp_uuid: str, data: bytes, retries: int = 3
    ) -> bytes | None:
        """Send a command and wait for the response notification.

        Reuses the persistent connection if available (same session as
        the poll that authenticated and read status). Falls back to a
        new connection otherwise.
        """
        async with self._ble_lock:
            own_client = False
            client = self._client
            if client is not None and client.is_connected:
                _LOGGER.debug("Reusing persistent connection for command")
            else:
                own_client = True
                await asyncio.sleep(2)
                device = bluetooth.async_ble_device_from_address(
                    self.hass, self.address, connectable=True
                )
                if device is None:
                    raise BleakError("Machine not found")
                try:
                    client = await establish_connection(
                        BleakClient, device, self.address, max_attempts=2
                    )
                except (BleakError, TimeoutError) as err:
                    err_str = str(err).lower()
                    if "already in progress" in err_str:
                        _LOGGER.debug("BLE busy, retrying after delay")
                        await asyncio.sleep(3)
                        client = await establish_connection(
                            BleakClient, device, self.address, max_attempts=2
                        )
                    elif "connection abort" in err_str:
                        _LOGGER.info("Command connection abort, clearing stale bond")
                        try:
                            tmp = BleakClient(device)
                            await tmp.unpair()
                        except Exception as unpair_err:  # noqa: BLE001
                            _LOGGER.debug("Failed to clear stale bond: %s", unpair_err)
                        await asyncio.sleep(3)
                        device = bluetooth.async_ble_device_from_address(
                            self.hass, self.address, connectable=True
                        )
                        if device is None:
                            raise
                        client = await establish_connection(
                            BleakClient, device, self.address, max_attempts=2
                        )
                    else:
                        raise
                if self.auth_key:
                    from .ble.protocol import _authenticate

                    await _authenticate(client, self.auth_key, self.family)

            try:
                response: bytearray | None = None

                def on_notify(_sender: object, rsp_data: bytearray) -> None:
                    nonlocal response
                    response = rsp_data
                    _LOGGER.debug("Command response: %s", rsp_data.hex())

                await client.start_notify(rsp_uuid, on_notify)

                for attempt in range(retries):
                    response = None
                    await client.write_gatt_char(cmd_uuid, data, response=True)
                    _LOGGER.debug(
                        "Command write attempt %d: %s", attempt + 1, data.hex()
                    )
                    for _ in range(5):
                        if response is not None:
                            break
                        await asyncio.sleep(1)
                    if response is not None:
                        break
                    await asyncio.sleep(1)

                await client.stop_notify(rsp_uuid)
                return bytes(response) if response is not None else None
            finally:
                if own_client:
                    await client.disconnect()

    async def async_release_kept_connection(self) -> None:
        """Release the temporary connection kept for brew."""
        self._keep_connection = False
        if not self.persistent:
            client = self._client
            self._client = None  # Clear first to prevent re-entry
            if client is not None:
                try:
                    await client.disconnect()
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Error disconnecting BLE client: %s", err)

    async def async_bst_send(self, cmd_uuid: str, rsp_uuid: str, data: bytes) -> bool:
        """Send data via BST protocol on the kept connection."""
        async with self._ble_lock:
            client = self._client
            if client is None or not client.is_connected:
                _LOGGER.error("No persistent connection for BST send")
                return False

            from .ble.bst import bst_send

            return await bst_send(client, cmd_uuid, rsp_uuid, data)

    async def async_load_counters(
        self, descaling_capsules: int, descaling_days: int
    ) -> None:
        """Restore brew counters from disk. Call once before the first refresh."""
        self.descaling_capsules = descaling_capsules
        self.descaling_days = descaling_days
        if stored := await self._counter_store.async_load():
            self.brew_total = stored.get("brew_total", 0)
            self.brews_since_descaling = stored.get("brews_since_descaling", 0)
            self.last_descaling = stored.get("last_descaling")
        if self.last_descaling is None:
            # No reference point yet, so start the clock now. Otherwise the
            # time half of the schedule could never trigger.
            self.last_descaling = time.time()
            self._async_save_counters()

    @property
    def days_since_descaling(self) -> int | None:
        """Whole days since the descaling counter was last reset."""
        if self.last_descaling is None:
            return None
        return max(0, int((time.time() - self.last_descaling) / 86400))

    @property
    def brews_until_descaling(self) -> int:
        """Brews remaining before the capsule half of the schedule is due."""
        return max(0, self.descaling_capsules - self.brews_since_descaling)

    @property
    def days_until_descaling(self) -> int | None:
        """Days remaining before the time half of the schedule is due."""
        days = self.days_since_descaling
        if days is None:
            return None
        return max(0, self.descaling_days - days)

    @callback
    def async_reset_descaling(self) -> None:
        """Clear the descaling counter and restart its clock."""
        self.brews_since_descaling = 0
        self.last_descaling = time.time()
        self._async_save_counters()
        self.async_update_listeners()

    @callback
    def _async_track_brew(self, previous: str | None, current: str) -> None:
        """Count one brew per entry into the BREWING state.

        BREWING is distinct from CAPSULE_READING, so an attempt with no capsule
        never reaches this state and is correctly not counted.
        """
        if current != "brewing" or previous == "brewing":
            return
        self.brew_total += 1
        self.brews_since_descaling += 1
        _LOGGER.debug(
            "Brew counted for %s: total=%s since_descaling=%s",
            self.address,
            self.brew_total,
            self.brews_since_descaling,
        )
        self._async_save_counters()

    @callback
    def _async_save_counters(self) -> None:
        """Write counters with a delay so bursts do not thrash the disk."""
        self._counter_store.async_delay_save(
            lambda: {
                "brew_total": self.brew_total,
                "brews_since_descaling": self.brews_since_descaling,
                "last_descaling": self.last_descaling,
            },
            COUNTER_SAVE_DELAY,
        )

    @callback
    def async_apply_advertisement(self, raw: bytes | None) -> bool:
        """Apply the passive advertisement as a fast path between polls.

        The Venus advertisement carries the same MachineStatus bytes as the
        connected characteristic, so state, flags and the brewing unit position
        are available without connecting at all - and roughly twice a second
        instead of once per scan interval.

        Deliberately conservative: this only refines data we already have. It
        never creates the first dataset, so a machine whose connection fails
        still surfaces as unavailable instead of silently reporting partial
        data. Other machine families are ignored entirely.

        Returns True when the machine state itself changed, so the caller can
        pull fresh connected data immediately rather than waiting for the next
        poll.
        """
        if self.family is not MachineFamily.VERTUO_NEXT:
            return False
        current = self.data
        if current is None:
            return False
        parsed = parse_venus_advertisement(raw)
        if parsed is None:
            return False

        fields = {
            key: parsed[key]
            for key in (
                "machine_state",
                "error_present",
                "water_tank_empty",
                "cleaning_needed",
                "descaling_needed",
                "capsule_container_full",
                "brewing_unit_closed",
                "milk_frother_running",
                "led_signaling",
                "cup_length_prog",
            )
            if key in parsed
        }
        if all(getattr(current, key) == value for key, value in fields.items()):
            return False

        new_state = fields.get("machine_state", current.machine_state)
        state_changed = current.machine_state != new_state
        self._async_track_brew(current.machine_state, new_state)
        _LOGGER.debug(
            "Passive update for %s: state=%s (was %s)",
            self.address,
            fields.get("machine_state"),
            current.machine_state,
        )
        self.async_set_updated_data(replace(current, **fields))
        return state_changed

    async def _async_update_data(self) -> NespressoMachineData:
        """Connect, read all characteristics, parse, disconnect."""
        async with self._ble_lock:
            return await self._async_update_data_locked()

    async def _async_update_data_locked(self) -> NespressoMachineData:
        """Actual update logic, must be called under _ble_lock."""
        _LOGGER.debug(
            "Update cycle start: v%s address=%s family=%s persistent=%s",
            _VERSION,
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
            if "connection abort" not in str(err).lower():
                _LOGGER.debug("Connection failed: %s", err)
                raise UpdateFailed(f"BLE connection failed: {err}") from err
            # Stale BlueZ bond from a factory-reset machine.
            # Remove device via D-Bus (no connection needed) and retry.
            _LOGGER.info("Connection abort, clearing stale BlueZ bond")
            try:
                tmp = BleakClient(device)
                await tmp.unpair()
                _LOGGER.debug("BlueZ device removed")
            except Exception as unpair_err:  # noqa: BLE001
                _LOGGER.debug("Failed to remove BlueZ device: %s", unpair_err)
            await asyncio.sleep(3)
            device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if device is None:
                raise UpdateFailed(f"BLE connection failed: {err}") from err
            try:
                client = await establish_connection(
                    BleakClient, device, self.address, max_attempts=3
                )
            except (BleakError, TimeoutError) as err2:
                _LOGGER.debug("Retry after bond clear failed: %s", err2)
                raise UpdateFailed(f"BLE connection failed: {err2}") from err2
            _LOGGER.debug(
                "Connected after bond clear to %s, MTU=%s",
                self.address,
                client.mtu_size,
            )

        _LOGGER.debug("Connected to %s, MTU=%s", self.address, client.mtu_size)

        # Dump GATT characteristic flags for diagnostics (security requirements)
        if client.services:
            for service in client.services:
                for char in service.characteristics:
                    _LOGGER.debug("GATT %s flags=%s", char.uuid, char.properties)

        try:
            if self.auth_key is None:
                self.auth_key = generate_auth_key()
                _LOGGER.debug("Generated new auth key: %s****", self.auth_key[:4])

            from .ble.protocol import _authenticate

            auth_ok = await _authenticate(client, self.auth_key, self.family)
            if not auth_ok:
                _LOGGER.info("Auth failed, reconnecting for retry")
                try:
                    await client.disconnect()
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Error disconnecting before retry: %s", err)
                client = await establish_connection(
                    BleakClient, device, self.address, max_attempts=3
                )
                auth_ok = await _authenticate(client, self.auth_key, self.family)
                if not auth_ok:
                    _LOGGER.warning("Auth failed on second attempt")

            protocol = get_protocol(self.family)
            raw = await protocol.async_read_all(client, self.auth_key)

            # Keep connection alive for persistent mode or pending brew
            if self.persistent and self._status_uuid:
                await client.start_notify(
                    self._status_uuid, self._on_status_notification
                )
                self._client = client
            elif self._keep_connection:
                self._client = client
                _LOGGER.debug("Keeping connection for pending brew")
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
            self._async_track_brew(
                self.data.machine_state if self.data else None, result.machine_state
            )
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
            raw_progress = fota.get("fota_progress", 0)
            fota_progress = (
                int(raw_progress) if isinstance(raw_progress, (int, float, str)) else 0
            )

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
