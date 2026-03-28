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
)
from .ble.protocol import get_protocol
from .const import DEFAULT_SCAN_INTERVAL, MachineFamily
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
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Nespresso {address}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.address = address
        self.family = family

    async def _async_update_data(self) -> NespressoMachineData:
        """Connect, read all characteristics, parse, disconnect."""
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
        except (BleakError, TimeoutError) as err:
            raise UpdateFailed(f"BLE read failed: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected BLE error: {err}") from err
        finally:
            await client.disconnect()

        try:
            return self._parse(raw)
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
            motor_running=bool(status.get("motor_running", False)),
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
            water_tank_empty=bool(status.get("water_tank_empty", False)),
            descaling_needed=bool(status.get("descaling_needed", False)),
            cleaning_needed=bool(status.get("cleaning_needed", False)),
            capsule_container_full=bool(status.get("capsule_container_full", False)),
            brewing_unit_closed=bool(status.get("brewing_unit_closed", False)),
            milk_frother_running=bool(status.get("milk_frother_running", False)),
            water_hardness=water_hardness,
            auto_power_off=auto_power_off,
            error_code=error_code,
        )

    def _parse_vmini(self, raw: RawMachineData) -> NespressoMachineData:
        serial = parse_serial_number(raw.serial_bytes) if raw.serial_bytes else None

        return NespressoMachineData(
            machine_state="unknown",
            error_present=False,
            firmware_version=raw.firmware_version,
            hardware_version=None,
            serial_number=serial,
        )
