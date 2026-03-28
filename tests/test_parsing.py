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

"""Unit tests for BLE byte-parsing functions.

Test vectors are derived from the decompiled Java source in the Nespresso
Smart APK v1.2.5. Each test documents the exact byte layout and expected
parsing result.
"""

import pytest

import sys
from unittest.mock import MagicMock

# Stub homeassistant before any nespresso imports
sys.modules.setdefault("homeassistant", MagicMock())
sys.modules.setdefault("homeassistant.components", MagicMock())
sys.modules.setdefault("homeassistant.components.bluetooth", MagicMock())
sys.modules.setdefault("homeassistant.components.sensor", MagicMock())
sys.modules.setdefault("homeassistant.components.binary_sensor", MagicMock())
sys.modules.setdefault("homeassistant.config_entries", MagicMock())
sys.modules.setdefault("homeassistant.const", MagicMock())
sys.modules.setdefault("homeassistant.core", MagicMock())
sys.modules.setdefault("homeassistant.helpers", MagicMock())
sys.modules.setdefault("homeassistant.helpers.device_registry", MagicMock())
sys.modules.setdefault("homeassistant.helpers.entity_platform", MagicMock())
sys.modules.setdefault("homeassistant.helpers.update_coordinator", MagicMock())
sys.modules.setdefault("homeassistant.data_entry_flow", MagicMock())
sys.modules.setdefault("bleak", MagicMock())
sys.modules.setdefault("bleak_retry_connector", MagicMock())

from custom_components.nespresso.ble.parsing import (  # noqa: E402
    parse_barista_machine_info,
    parse_barista_status,
    parse_general_user_settings,
    parse_serial_number,
    parse_version_v2,
    parse_version_v3,
    parse_vertuonext_machine_info,
    parse_vertuonext_status,
)


# ---------------------------------------------------------------------------
# Version parsing (matches Utils.getVersionV2 / getVersionV3)
# ---------------------------------------------------------------------------


class TestVersionParsing:
    def test_version_v2_simple(self) -> None:
        # 305 -> "3.5"
        assert parse_version_v2(305) == "3.5"

    def test_version_v2_zero(self) -> None:
        assert parse_version_v2(0) == "0.0"

    def test_version_v2_leading_zero_minor(self) -> None:
        # 102 -> "1.2"
        assert parse_version_v2(102) == "1.2"

    def test_version_v2_large(self) -> None:
        # 1234 -> "12.34"
        assert parse_version_v2(1234) == "12.34"

    def test_version_v3_simple(self) -> None:
        # 10203 -> "1.2.3"
        assert parse_version_v3(10203) == "1.2.3"

    def test_version_v3_zero(self) -> None:
        assert parse_version_v3(0) == "0.0.0"

    def test_version_v3_large(self) -> None:
        # 20501 -> "2.5.1"
        assert parse_version_v3(20501) == "2.5.1"


# ---------------------------------------------------------------------------
# Serial number parsing
# ---------------------------------------------------------------------------


class TestSerialNumber:
    def test_null_terminated(self) -> None:
        data = b"ABC1234567890\x00\x00\x00\x00\x00\x00"
        assert parse_serial_number(data) == "ABC1234567890"

    def test_no_null(self) -> None:
        data = b"SN12345"
        assert parse_serial_number(data) == "SN12345"

    def test_empty(self) -> None:
        data = b"\x00\x00\x00"
        assert parse_serial_number(data) == ""

    def test_full_19_bytes(self) -> None:
        data = b"1234567890123456789"
        assert parse_serial_number(data) == "1234567890123456789"


# ---------------------------------------------------------------------------
# Barista status parsing
# Verified against: com.sdataway.barista.sdk.models.MachineStatus
#   byte[0] bit0: bootloaderActive
#   byte[0] bit3: errorPresent
#   byte[0] bit4: isMotorRunning
#   byte[1]: machineState = (byte[1] & 0xFC) >> 2
# ---------------------------------------------------------------------------


class TestBaristaStatus:
    def test_ready_no_error(self) -> None:
        # byte0=0x00, byte1: state READY=1, (1 << 2) = 0x04
        result = parse_barista_status(b"\x00\x04")
        assert result["machine_state"] == "ready"
        assert result["error_present"] is False
        assert result["motor_running"] is False

    def test_standby(self) -> None:
        # state STANDBY=0, byte1=0x00
        result = parse_barista_status(b"\x00\x00")
        assert result["machine_state"] == "standby"

    def test_brewing_with_motor(self) -> None:
        # byte0: bit4=motor -> 0x10
        # byte1: state RECIPE_EXECUTING=2, (2 << 2) = 0x08
        result = parse_barista_status(b"\x10\x08")
        assert result["machine_state"] == "brewing"
        assert result["motor_running"] is True

    def test_error_state(self) -> None:
        # byte0: bit3=error -> 0x08
        # byte1: state ERROR=4, (4 << 2) = 0x10
        result = parse_barista_status(b"\x08\x10")
        assert result["machine_state"] == "error"
        assert result["error_present"] is True

    def test_overheated(self) -> None:
        # byte1: state OVERHEATED=5, (5 << 2) = 0x14
        result = parse_barista_status(b"\x00\x14")
        assert result["machine_state"] == "overheated"

    def test_recipe_paused(self) -> None:
        # byte1: state RECIPE_PAUSED=7, (7 << 2) = 0x1C
        result = parse_barista_status(b"\x00\x1c")
        assert result["machine_state"] == "paused"

    def test_out_of_box(self) -> None:
        # byte1: state OUT_OF_BOX=6, (6 << 2) = 0x18
        result = parse_barista_status(b"\x00\x18")
        assert result["machine_state"] == "setup"

    def test_local_settings(self) -> None:
        # byte1: state LOCAL_SETTINGS=3, (3 << 2) = 0x0C
        result = parse_barista_status(b"\x00\x0c")
        assert result["machine_state"] == "local_settings"

    def test_unknown_state(self) -> None:
        # byte1: an undefined state value, e.g. (63 << 2) = 0xFC
        result = parse_barista_status(b"\x00\xfc")
        assert result["machine_state"] == "unknown"

    def test_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="2 bytes"):
            parse_barista_status(b"\x00")


# ---------------------------------------------------------------------------
# Vertuo Next status parsing
# Verified against: com.sdataway.vertuonext.sdk.models.MachineStatus
#   byte[0] bit0: waterTankEmpty
#   byte[0] bit1: cleaningNeeded
#   byte[0] bit2: descalingNeeded
#   byte[0] bit4: errorPresent
#   byte[1] bit6: capsuleContainerFull
#   byte[1] bit7: brewingUnitClosed
#   machineState = (byte[1] & 0x0F) + (byte[2] & 0xF0)
# ---------------------------------------------------------------------------


class TestVertuoNextStatus:
    def test_ready_clean(self) -> None:
        # byte0=0x00, byte1: low nibble=2 -> 0x02, byte2=0x00
        # state = (0x02 & 0x0F) + (0x00 & 0xF0) = 2 = READY
        result = parse_vertuonext_status(b"\x00\x02\x00")
        assert result["machine_state"] == "ready"
        assert result["water_tank_empty"] is False
        assert result["cleaning_needed"] is False
        assert result["descaling_needed"] is False
        assert result["error_present"] is False
        assert result["capsule_container_full"] is False
        assert result["brewing_unit_closed"] is False

    def test_water_tank_empty(self) -> None:
        # byte0 bit0 set -> 0x01
        result = parse_vertuonext_status(b"\x01\x02\x00")
        assert result["water_tank_empty"] is True
        assert result["machine_state"] == "ready"

    def test_cleaning_needed(self) -> None:
        # byte0 bit1 -> 0x02
        result = parse_vertuonext_status(b"\x02\x02\x00")
        assert result["cleaning_needed"] is True

    def test_descaling_needed(self) -> None:
        # byte0 bit2 -> 0x04
        result = parse_vertuonext_status(b"\x04\x02\x00")
        assert result["descaling_needed"] is True

    def test_error_present(self) -> None:
        # byte0 bit4 -> 0x10
        result = parse_vertuonext_status(b"\x10\x02\x00")
        assert result["error_present"] is True

    def test_capsule_container_full(self) -> None:
        # byte1 bit6 -> 0x42 (bit6 set + low nibble 2 for READY)
        result = parse_vertuonext_status(b"\x00\x42\x00")
        assert result["capsule_container_full"] is True
        assert result["machine_state"] == "ready"

    def test_brewing_unit_closed(self) -> None:
        # byte1 bit7 -> 0x82 (bit7 set + low nibble 2 for READY)
        result = parse_vertuonext_status(b"\x00\x82\x00")
        assert result["brewing_unit_closed"] is True
        assert result["machine_state"] == "ready"

    def test_brewing_state(self) -> None:
        # state BREWING=4: (byte1 & 0x0F)=4, (byte2 & 0xF0)=0
        result = parse_vertuonext_status(b"\x00\x04\x00")
        assert result["machine_state"] == "brewing"

    def test_standby_state(self) -> None:
        # state STANDBY=12: (byte1 & 0x0F)=0xC, (byte2 & 0xF0)=0
        result = parse_vertuonext_status(b"\x00\x0c\x00")
        assert result["machine_state"] == "standby"

    def test_power_save_state(self) -> None:
        # state POWER_SAVE=9: (byte1 & 0x0F)=9, (byte2 & 0xF0)=0
        result = parse_vertuonext_status(b"\x00\x09\x00")
        assert result["machine_state"] == "power_save"

    def test_updating_state(self) -> None:
        # state UPDATING=13: (byte1 & 0x0F)=0xD, (byte2 & 0xF0)=0
        result = parse_vertuonext_status(b"\x00\x0d\x00")
        assert result["machine_state"] == "updating"

    def test_capsule_reading_state(self) -> None:
        # state CAPSULE_READING=17: (byte1 & 0x0F)=1, (byte2 & 0xF0)=0x10
        # 17 = 0x11 -> low nibble 1, high nibble 0x10
        result = parse_vertuonext_status(b"\x00\x01\x10")
        assert result["machine_state"] == "capsule_reading"

    def test_emptying_ready_state(self) -> None:
        # state EMPTYING_READY=33: (byte1 & 0x0F)=1, (byte2 & 0xF0)=0x20
        # 33 = 0x21 -> low nibble 1, high nibble 0x20
        result = parse_vertuonext_status(b"\x00\x01\x20")
        assert result["machine_state"] == "emptying_ready"

    def test_rinsing_paused_state(self) -> None:
        # state RINSING_PAUSED=36: (byte1 & 0x0F)=4, (byte2 & 0xF0)=0x20
        # 36 = 0x24 -> low nibble 4, high nibble 0x20
        result = parse_vertuonext_status(b"\x00\x04\x20")
        assert result["machine_state"] == "rinsing_paused"

    def test_all_alerts(self) -> None:
        # byte0: water(0x01) + cleaning(0x02) + descaling(0x04) + error(0x10) = 0x17
        result = parse_vertuonext_status(b"\x17\x02\x00")
        assert result["water_tank_empty"] is True
        assert result["cleaning_needed"] is True
        assert result["descaling_needed"] is True
        assert result["error_present"] is True

    def test_unknown_state(self) -> None:
        # byte1=0x0F, byte2=0xF0 -> state = 15 + 240 = 255
        # 255 is not in VERTUO_STATE_NAMES (UNKNOWN is in enum but not mapped)
        result = parse_vertuonext_status(b"\x00\x0f\xf0")
        assert result["machine_state"] == "unknown"

    def test_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="3 bytes"):
            parse_vertuonext_status(b"\x00\x00")


# ---------------------------------------------------------------------------
# Barista machine info parsing
# Verified against: com.sdataway.barista.sdk.characteristics.CharacMachineInfo
#   bytes 0-1: hardwareVersion (MSB, getVersionV2)
#   bytes 4-5: firmwareVersion (MSB, getVersionV2)
# ---------------------------------------------------------------------------


class TestBaristaMachineInfo:
    def test_normal(self) -> None:
        # HW version: 0x01 0x31 = 305 -> "3.5"
        # BL version: 0x00 0x64 = 100 (unused)
        # FW version: 0x00 0xC8 = 200 -> "2.0"
        # BT version: 0x00 0x01 = 1 (unused)
        data = b"\x01\x31\x00\x64\x00\xc8\x00\x01\x00\x00\x00\x00\x00\x00"
        result = parse_barista_machine_info(data)
        assert result["hardware_version"] == "3.5"
        assert result["firmware_version"] == "2.0"

    def test_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="8 bytes"):
            parse_barista_machine_info(b"\x00\x00\x00")


# ---------------------------------------------------------------------------
# Vertuo Next machine info parsing
# Verified against: com.sdataway.vertuonext.sdk.characteristics.CharacMachineInfo
#   bytes 0-1: hardwareVersion (MSB, getVersionV2)
#   bytes 4-5: firmwareVersion (MSB, getVersionV2)
# ---------------------------------------------------------------------------


class TestVertuoNextMachineInfo:
    def test_normal(self) -> None:
        # HW: 0x02 0x00 = 512 -> "5.12"
        # BL: 0x00 0x01
        # FW: 0x01 0x00 = 256 -> "2.56"
        # Recipe: 0x00 0x01
        # Conn FW: 0x00 0x01
        data = b"\x02\x00\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00"
        result = parse_vertuonext_machine_info(data)
        assert result["hardware_version"] == "5.12"
        assert result["firmware_version"] == "2.56"

    def test_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="10 bytes"):
            parse_vertuonext_machine_info(b"\x00\x00\x00")


# ---------------------------------------------------------------------------
# General user settings parsing
# Verified against: CharacGeneralUserSettings
#   bytes 0-1: machineAPOTime (2-byte unsigned LSB)
#   byte 2: waterHardness (unsigned)
# ---------------------------------------------------------------------------


class TestGeneralUserSettings:
    def test_normal(self) -> None:
        # APO time: 0xE8 0x03 = 1000 (LSB: low byte first)
        # Water hardness: 0x02
        # Active time: 0x0F
        data = b"\xe8\x03\x02\x0f"
        result = parse_general_user_settings(data)
        assert result["auto_power_off"] == 1000
        assert result["water_hardness"] == 2

    def test_zero_values(self) -> None:
        data = b"\x00\x00\x00\x00"
        result = parse_general_user_settings(data)
        assert result["auto_power_off"] == 0
        assert result["water_hardness"] == 0

    def test_max_water_hardness(self) -> None:
        data = b"\x00\x00\xff\x00"
        result = parse_general_user_settings(data)
        assert result["water_hardness"] == 255

    def test_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="4 bytes"):
            parse_general_user_settings(b"\x00\x00")
