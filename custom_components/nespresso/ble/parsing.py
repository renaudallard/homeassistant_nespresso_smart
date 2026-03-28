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

"""Pure byte-parsing functions for Nespresso BLE characteristics.

All functions are pure: bytes in, structured data out. No I/O, no BLE, no HA
dependencies. Parsing logic is verified against the decompiled Java source
from the Nespresso Smart APK v1.2.5.
"""

from __future__ import annotations

from ..const import BARISTA_STATE_NAMES, VERTUO_STATE_NAMES


def _get_bit(byte_val: int, bit_pos: int) -> bool:
    """Extract a single bit. Matches ByteBufferManager.getBitValue."""
    return bool(byte_val & (1 << bit_pos))


def _get_2bytes_unsigned_msb(data: bytes, offset: int) -> int:
    """Read 2-byte unsigned big-endian. Matches get2BytesUnsignedMSB."""
    return ((data[offset] & 0xFF) << 8) | (data[offset + 1] & 0xFF)


def _get_2bytes_unsigned_lsb(data: bytes, offset: int) -> int:
    """Read 2-byte unsigned little-endian. Matches get2BytesUnsignedLSB."""
    return ((data[offset + 1] & 0xFF) << 8) | (data[offset] & 0xFF)


def parse_version_v2(value: int) -> str:
    """Format major.minor from a 16-bit MSB value. Matches Utils.getVersionV2."""
    return f"{value // 100}.{value % 100}"


def parse_version_v3(value: int) -> str:
    """Format major.minor.patch from a 16-bit MSB value. Matches Utils.getVersionV3."""
    major = value // 10000
    remainder = value % 10000
    return f"{major}.{remainder // 100}.{remainder % 100}"


def parse_serial_number(data: bytes) -> str:
    """Decode null-terminated UTF-8 serial number. All families use this."""
    return data.split(b"\x00", 1)[0].decode("utf-8", errors="replace")


def parse_barista_status(data: bytes) -> dict[str, object]:
    """Parse Barista machine status bytes.

    Source: com.sdataway.barista.sdk.models.MachineStatus constructor
      byte[0] bit0: bootloaderActive
      byte[0] bits5-6: pairingKeyState = (byte[0] & 0x60) >> 5
      byte[0] bit3: errorPresent
      byte[0] bit4: isMotorRunning
      byte[1]: machineState = (byte[1] & 0xFC) >> 2
    """
    if len(data) < 2:
        raise ValueError(f"Barista status requires >= 2 bytes, got {len(data)}")

    b0 = data[0]
    b1 = data[1]
    state_val = (b1 & 0xFC) >> 2

    return {
        "machine_state": BARISTA_STATE_NAMES.get(state_val, "unknown"),
        "error_present": _get_bit(b0, 3),
        "motor_running": _get_bit(b0, 4),
    }


def parse_vertuonext_status(data: bytes) -> dict[str, object]:
    """Parse Vertuo Next machine status bytes.

    Source: com.sdataway.vertuonext.sdk.models.MachineStatus constructor
      byte[0] bit0: waterTankEmpty
      byte[0] bit1: cleaningNeeded
      byte[0] bit2: descalingNeeded
      byte[0] bit4: errorPresent
      byte[1] bit7: brewingUnitClosed
      byte[1] bit6: capsuleContainerFull
      machineState = (byte[1] & 0x0F) + (byte[2] & 0xF0)
    """
    if len(data) < 3:
        raise ValueError(f"Vertuo Next status requires >= 3 bytes, got {len(data)}")

    b0 = data[0]
    b1 = data[1]
    b2 = data[2]
    state_val = (b1 & 0x0F) + (b2 & 0xF0)

    return {
        "machine_state": VERTUO_STATE_NAMES.get(state_val, "unknown"),
        "water_tank_empty": _get_bit(b0, 0),
        "cleaning_needed": _get_bit(b0, 1),
        "descaling_needed": _get_bit(b0, 2),
        "error_present": _get_bit(b0, 4),
        "capsule_container_full": _get_bit(b1, 6),
        "brewing_unit_closed": _get_bit(b1, 7),
    }


def parse_barista_machine_info(data: bytes) -> dict[str, str | None]:
    """Parse 14-byte Barista machine info.

    Source: com.sdataway.barista.sdk.characteristics.CharacMachineInfo
      bytes 0-1: hardwareVersion (MSB, getVersionV2)
      bytes 2-3: bootloaderVersion (MSB, getVersionV2)
      bytes 4-5: firmwareVersion (MSB, getVersionV2)
      bytes 6-7: bluetoothVersion (MSB, getVersionV2)
      bytes 8-13: deviceAddress (MAC)
    """
    if len(data) < 8:
        raise ValueError(f"Barista machine info requires >= 8 bytes, got {len(data)}")

    hw = parse_version_v2(_get_2bytes_unsigned_msb(data, 0))
    fw = parse_version_v2(_get_2bytes_unsigned_msb(data, 4))

    return {
        "hardware_version": hw,
        "firmware_version": fw,
    }


def parse_vertuonext_machine_info(data: bytes) -> dict[str, str | None]:
    """Parse 16-byte Vertuo Next machine info.

    Source: com.sdataway.vertuonext.sdk.characteristics.CharacMachineInfo
      bytes 0-1: hardwareVersion (MSB, getVersionV2)
      bytes 2-3: bootloaderVersion (MSB, getVersionV2)
      bytes 4-5: firmwareVersion (MSB, getVersionV2)
      bytes 6-7: recipeDatabaseVersion (MSB)
      bytes 8-9: connectivityFirmwareVersion (MSB, getVersionV3)
      bytes 10-15: deviceAddress (MAC)
    """
    if len(data) < 10:
        raise ValueError(
            f"Vertuo Next machine info requires >= 10 bytes, got {len(data)}"
        )

    hw = parse_version_v2(_get_2bytes_unsigned_msb(data, 0))
    fw = parse_version_v2(_get_2bytes_unsigned_msb(data, 4))

    return {
        "hardware_version": hw,
        "firmware_version": fw,
    }


def parse_general_user_settings(data: bytes) -> dict[str, int]:
    """Parse 4-byte Vertuo Next general user settings.

    Source: com.sdataway.vertuonext.sdk.characteristics.CharacGeneralUserSettings
      bytes 0-1: machineAPOTime (2-byte unsigned LSB)
      byte 2: waterHardness (1-byte unsigned)
      byte 3: activeTime2StandBy (1-byte unsigned)
    """
    if len(data) < 4:
        raise ValueError(f"User settings requires >= 4 bytes, got {len(data)}")

    return {
        "auto_power_off": _get_2bytes_unsigned_lsb(data, 0),
        "water_hardness": data[2] & 0xFF,
    }
