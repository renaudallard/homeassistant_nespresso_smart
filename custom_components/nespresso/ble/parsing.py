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

import json
from collections.abc import Mapping

from ..const import (
    BARISTA_STATE_NAMES,
    CAPS_COUNTER_MAX,
    CMID_TYPE_NAMES,
    EXPERT_STATE_NAMES,
    MILK_UNIT_STATE_NAMES,
    VERTUO_STATE_NAMES,
    WATER_HARDNESS_MAX,
    WIFI_SECURITY_NAMES,
    WIFI_STATUS_NAMES,
)


def _get_bit(byte_val: int, bit_pos: int) -> bool:
    """Extract a single bit. Matches ByteBufferManager.getBitValue."""
    return bool(byte_val & (1 << bit_pos))


def _get_2bytes_unsigned_msb(data: bytes, offset: int) -> int:
    """Read 2-byte unsigned big-endian. Matches get2BytesUnsignedMSB."""
    return ((data[offset] & 0xFF) << 8) | (data[offset + 1] & 0xFF)


def _get_2bytes_unsigned_lsb(data: bytes, offset: int) -> int:
    """Read 2-byte unsigned little-endian. Matches get2BytesUnsignedLSB."""
    return ((data[offset + 1] & 0xFF) << 8) | (data[offset] & 0xFF)


def _pairing_key_state(b0: int) -> str:
    """Decode the pairing key state both families carry in byte 0.

    Matches MachineStatus.machineBound in the Vertuo and the Barista SDK:
    PairingKeyState.valueOf((byte[0] & 0x60) >> 5). Only two bits, so the
    UNKNOWN(255) of the connected characteristic cannot appear here.

    This is the one view of the pairing state that survives a machine refusing
    every read, because it rides in the advertisement.
    """
    return CMID_TYPE_NAMES[(b0 & 0x60) >> 5]


def parse_version_v2(value: int) -> str:
    """Format major.minor from a 16-bit MSB value. Matches Utils.getVersionV2."""
    return f"{value // 100}.{value % 100}"


def parse_version_v3(value: int) -> str:
    """Format major.minor.patch from a 16-bit MSB value. Matches Utils.getVersionV3."""
    major = value // 10000
    remainder = value % 10000
    return f"{major}.{remainder // 100}.{remainder % 100}"


def parse_profile_version(data: bytes) -> str:
    """Parse 4-byte profile version. Bytes 0-1 MSB via getVersionV2."""
    if len(data) < 2:
        return "0.0"
    return parse_version_v2(_get_2bytes_unsigned_msb(data, 0))


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
        "pairing_key_state": _pairing_key_state(b0),
        "bootloader_active": _get_bit(b0, 0),
        "error_present": _get_bit(b0, 3),
        "motor_running": _get_bit(b0, 4),
        "induction_heating": _get_bit(b0, 5),
        "last_cmid_valid": _get_bit(b0, 6),
        "setup_complete": _get_bit(b0, 7),
    }


# Company identifiers to accept in an advertisement, most likely first.
#
# The Bluetooth SIG assigns 0x0225 to Nestle Nespresso S.A., and that is NOT
# what these machines send. Every capture from real hardware reaches Home
# Assistant as manufacturer_data keyed 0x2502, because the firmware emits the
# two octets the wrong way round. The key is whatever the decoder read off the
# wire, not what the registry says it should have been, so 0x2502 is the one
# that matches. The registered value is kept as a second candidate in case the
# firmware is ever corrected.
#
# This has been got wrong twice by reasoning from the registry. Check a capture.
NESPRESSO_COMPANY_IDS = (0x2502, 0x0225)


def nespresso_manufacturer_data(
    manufacturer_data: Mapping[int, bytes],
) -> bytes | None:
    """Return the Nespresso payload from an advertisement, or None."""
    for company_id in NESPRESSO_COMPANY_IDS:
        data = manufacturer_data.get(company_id)
        if data is not None:
            return data
    return None


def parse_venus_advertisement(data: bytes | None) -> dict[str, object] | None:
    """Parse the Venus BLE advertisement payload.

    The advertisement carries the *same* three MachineStatus bytes as
    CHAR_MACHINE_STATUS (06aa3a12), so the connected parser applies verbatim.

    Verified on a Vertuo Pop against live connected readings: states
    POWER_SAVE(9), HEATUP(1), READY(2), STANDBY(12), CAPSULE_READING(17) and
    BREWING(4) all matched, and byte0 bits 5-6 tracked CMID_TYPE exactly
    (0 = NONE after a factory reset, 2 = FINAL once onboarded). Those two bits
    come back as pairing_key_state, which is worth reading on a machine that
    refuses every connected read, since it is the only state left visible.

    Returns None for anything that is not a usable payload, so callers can
    ignore advertisements from other machine families without special-casing.
    """
    if data is None or len(data) < 3:
        return None
    return parse_vertuonext_status(data[:3])


def parse_vertuonext_status(data: bytes) -> dict[str, object]:
    """Parse Vertuo Next machine status bytes.

    Source: com.sdataway.vertuonext.sdk.models.MachineStatus constructor
      byte[0] bit0: waterTankEmpty
      byte[0] bit1: cleaningNeeded
      byte[0] bit2: descalingNeeded
      byte[0] bit4: errorPresent
      byte[0] bits5-6: pairingKeyState = (byte[0] & 0x60) >> 5
      byte[1] bit7: brewingUnitClosed
      byte[1] bit6: capsuleContainerFull
      machineState = (byte[1] & 0x0F) + (byte[2] & 0xF0)
      byte[2] bits0-3: milk unit status, see below
      bytes[3..7]: not decoded by anyone, see below

    The low nibble of byte 2 is not in the APK. MachineStatus reads byte 2 for
    the state's high nibble and nothing else, so the app never sees it. It was
    found by watching a Vertuo Creatista: 0 at rest, 1 once warm, and 2 for
    exactly as long as the frother ran, which are positions 0, 1 and 2 of the
    milkUnitStatus enum the cloud reports for the same machine. That enum runs
    0 to 15 and a nibble holds 0 to 15.

    Later captures on the same machine added 4 through a milk cleaning and 10
    through the menu the machine sits in during a full cleaning cycle, so five
    of the sixteen positions are measured and all five land where the cloud
    enum puts them. The remaining eleven names are still the cloud's.

    4 means wanted or under way, not just running: the machine went to 4 the
    moment it started asking for a milk cleaning and stayed there at rest until
    the cleaning was done. Nothing in byte 0 moves for it, so a machine asking
    for a milk cleaning shows up here and in no other bit we read.

    On the same machine byte[1] bit4, which the SDK calls milkFrotherRunning,
    stayed clear through 68 seconds of frothing. The bit is kept because it is
    what the vendor documents and it may work on machines we have not seen, but
    the nibble is what actually moved.

    byte[1] bit7, brewingUnitClosed, does follow the head when someone moves
    it: on that Creatista it set at the instant the machine went to capsule
    reading after a capsule was loaded, and read clear while the machine heated
    with the head open. It also went clear 14 seconds into the milk cleaning
    the machine had asked for and stayed clear for the remaining 167 seconds,
    with the owner confirming they never touched the head. Seen once, so it is
    not a rule, but a consumer of this bit has to expect it to move with nobody
    standing at the machine.

    The characteristic is eight bytes and nothing reads past byte 2, here or in
    the APK. Across the seventeen distinct payloads captured on a Creatista,
    spanning a coffee, frothing, a cleaning cycle, the machine's own menu, an
    open brewing unit, standby and power save, byte 6 held 0x3F and bytes 3, 5
    and 7 held zero.

    Byte 4 is not a constant. It read 0x00 in every power save sample and 0x01
    everywhere else, going to 0x01 when the machine woke and back to 0x00 when
    it returned to power save. Standby keeps it at 0x01, so it is not simply
    awake or asleep. The rest are worth watching on a machine doing something
    we have not tried, since the milk unit was found in an ignored nibble of
    byte 2.
    """
    if len(data) < 3:
        raise ValueError(f"Vertuo Next status requires >= 3 bytes, got {len(data)}")

    b0 = data[0]
    b1 = data[1]
    b2 = data[2]
    state_val = (b1 & 0x0F) + (b2 & 0xF0)
    milk = MILK_UNIT_STATE_NAMES.get(b2 & 0x0F, "unknown")

    return {
        "machine_state": VERTUO_STATE_NAMES.get(state_val, "unknown"),
        "milk_unit_state": milk,
        "pairing_key_state": _pairing_key_state(b0),
        "water_tank_empty": _get_bit(b0, 0),
        "cleaning_needed": _get_bit(b0, 1),
        "descaling_needed": _get_bit(b0, 2),
        "led_signaling": _get_bit(b0, 3),
        "error_present": _get_bit(b0, 4),
        "bootloader_active": _get_bit(b0, 7),
        "milk_frother_running": _get_bit(b1, 4) or milk == "frothing",
        "cup_length_prog": _get_bit(b1, 5),
        "capsule_container_full": _get_bit(b1, 6),
        "brewing_unit_closed": _get_bit(b1, 7),
    }


def _select_bits(data: bytes, first: int, last: int) -> int:
    """Read bits first..last, counted MSB first. Matches ByteConversion.selectBit."""
    value = 0
    for i in range(max(first, 0), min(last, len(data) * 8 - 1) + 1):
        value = (value << 1) | ((data[i // 8] >> (7 - i % 8)) & 1)
    return value


def parse_expert_status(data: bytes, params: bytes | None = None) -> dict[str, object]:
    """Parse the Nespresso Expert machine status (CHAR_MACHINE_STATUS).

    The Expert shares the Venus service UUID but not the Vertuo layout. The
    app decodes it with MachineMonitoringOperations.fromByteToBuilder (bits
    counted MSB first): 0 bootloader, 1-2 pairing key state, 3 error,
    5 descaling needed, 7 water tank empty, 9 capsule container full,
    12-15 machine state, 16 capsule stock low, 17-26 capsule stock
    (above 1000 means stock tracking is off), 46 slider closed (from params).
    The stock bits are not read, since the stock counter is gone. Keys are
    those of parse_vertuonext_status, but the lever only with params.
    """
    if len(data) < 4:
        raise ValueError(f"Expert status requires >= 4 bytes, got {len(data)}")

    status: dict[str, object] = {
        "machine_state": EXPERT_STATE_NAMES.get(_select_bits(data, 12, 15), "unknown"),
        "milk_unit_state": "unknown",
        "pairing_key_state": _pairing_key_state(data[0]),
        "water_tank_empty": bool(_select_bits(data, 7, 7)),
        "cleaning_needed": False,
        "descaling_needed": bool(_select_bits(data, 5, 5)),
        "led_signaling": False,
        "error_present": bool(_select_bits(data, 3, 3)),
        "bootloader_active": bool(_select_bits(data, 0, 0)),
        "milk_frother_running": False,
        "cup_length_prog": False,
        "capsule_container_full": bool(_select_bits(data, 9, 9)),
    }
    if params:
        # Left out without CHAR_MACHINE_PARAMS, so a status notification
        # keeps the last known lever.
        status["brewing_unit_closed"] = parse_expert_lever(params)
    return status


def parse_expert_lever(params: bytes) -> bool:
    """Whether the Expert's slider (lever) is closed, from CHAR_MACHINE_PARAMS.

    The app's toIncompleteMachineStatusBuilder joins status[0:5] with
    params[0:1] and reads bit 46 of that, counted MSB first, as slider closed.
    That is bit 1 of params[0], so it reads the same on its own, as a
    notification of the params delivers it.
    """
    if not params:
        raise ValueError("Expert params are empty")
    return bool(_select_bits(params[:1], 6, 6))


def parse_vertuo_wifi_status(data: bytes) -> dict[str, str | None]:
    """Parse the Vertuo WiFi current setup characteristic.

    Source: CharacWifiCurrentSetup in the APK, a 60-byte record
      bytes 0-31:  SSID, null terminated
      byte 32:     additional info, an error or progress code
      byte 33:     WiFi status
      bytes 34-53: IPv4, subnet, gateway, DNS1, DNS2, four bytes each
      bytes 54-59: BSSID

    The status the app shows is not simply byte 33. When byte 32 is non-zero it
    wins, which is how a code like wrong_password or no_internet reaches the
    user instead of a bare not_connected.

    Only the first 34 bytes are needed here. updateValues decodes those, and a
    separate method fills the address block, which is easy to miss and easy to
    conclude wrongly that the machine never sends it.
    """
    if len(data) < 34:
        raise ValueError(f"Vertuo WiFi status requires >= 34 bytes, got {len(data)}")

    additional_info = data[32]
    status = additional_info if additional_info > 0 else data[33]
    ssid = data[:32].split(b"\x00", 1)[0].decode("utf-8", errors="replace")

    return {
        "wifi_status": WIFI_STATUS_NAMES.get(status, "unknown"),
        "wifi_ssid": ssid or None,
    }


# A scan result whose security byte is this marks the end of the list, not a
# network. 0xF0 is a genuine network of unknown security and must not be
# confused with it.
WIFI_SCAN_END = 0xFF

# Longest scan the integration will walk. The machine ends the list itself, so
# this only bounds a machine that never does.
WIFI_SCAN_MAX_ENTRIES = 30


def parse_wifi_scan_entry(data: bytes) -> dict[str, object] | None:
    """Parse one CHAR_WIFISCANRESULT entry, or None at the end of the list.

    Source: CharacWifiScanResult in the APK, 42 bytes
      byte 0:      security type
      bytes 1-32:  SSID, null terminated
      bytes 33-34: signal strength, big endian signed
      byte 35:     connection index, echoed back when connecting
      bytes 36-41: BSSID
    """
    if len(data) < 36:
        raise ValueError(f"WiFi scan entry requires >= 36 bytes, got {len(data)}")

    security = data[0]
    ssid = data[1:33].split(b"\x00", 1)[0].decode("utf-8", errors="replace")
    if security == WIFI_SCAN_END and not ssid:
        return None

    return {
        "ssid": ssid,
        "security": WIFI_SECURITY_NAMES.get(security, "unknown"),
        "security_type": security,
        "signal_strength": int.from_bytes(data[33:35], "big", signed=True),
        "connection_index": data[35],
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
    bl = parse_version_v2(_get_2bytes_unsigned_msb(data, 2))
    fw = parse_version_v2(_get_2bytes_unsigned_msb(data, 4))
    bt = parse_version_v2(_get_2bytes_unsigned_msb(data, 6))

    return {
        "hardware_version": hw,
        "bootloader_version": bl,
        "firmware_version": fw,
        "bluetooth_version": bt,
    }


def parse_vertuonext_machine_info(data: bytes) -> dict[str, str | None]:
    """Parse 16-byte Vertuo Next machine info.

    Source: com.sdataway.vertuonext.sdk.characteristics.CharacMachineInfo
      bytes 0-1: hardwareVersion (MSB, getVersionV2)
      bytes 2-3: bootloaderVersion (MSB, getVersionV2)
      bytes 4-5: firmwareVersion (MSB, getVersionV2)
      bytes 6-7: recipeDatabaseVersion (MSB, getVersionV2)
      bytes 8-9: connectivityFirmwareVersion (MSB, getVersionV3)
      bytes 10-15: deviceAddress (MAC)
    """
    if len(data) < 10:
        raise ValueError(
            f"Vertuo Next machine info requires >= 10 bytes, got {len(data)}"
        )

    hw = parse_version_v2(_get_2bytes_unsigned_msb(data, 0))
    bl = parse_version_v2(_get_2bytes_unsigned_msb(data, 2))
    fw = parse_version_v2(_get_2bytes_unsigned_msb(data, 4))
    recipe_db = parse_version_v2(_get_2bytes_unsigned_msb(data, 6))
    conn_fw = parse_version_v3(_get_2bytes_unsigned_msb(data, 8))

    return {
        "hardware_version": hw,
        "bootloader_version": bl,
        "firmware_version": fw,
        "recipe_db_version": recipe_db,
        "connectivity_fw_version": conn_fw,
    }


def parse_barista_machine_params(data: bytes) -> dict[str, bool]:
    """Parse Barista machine specific params. Byte 0: bit0=setupComplete, bit2=bleDisabled."""
    if not data:
        return {"ble_disabled": False}
    return {"ble_disabled": _get_bit(data[0], 2)}


def parse_caps_counter(data: bytes) -> int:
    """Parse capsule counter (2-byte unsigned MSB)."""
    if len(data) < 2:
        return data[0] & 0xFF if data else 0
    return _get_2bytes_unsigned_msb(data, 0)


def build_caps_counter(value: int) -> bytes:
    """Encode a capsule counter for CHAR_CAPS_COUNTER.

    The inverse of parse_caps_counter, and the same two bytes MSB first. The
    machine keeps the count itself, so this exists to correct it rather than to
    drive it: after a service visit, or a counter that drifted while Home
    Assistant was not watching.
    """
    if not 0 <= value <= CAPS_COUNTER_MAX:
        raise ValueError(
            f"Capsule counter must be 0 to {CAPS_COUNTER_MAX}, got {value}"
        )
    return value.to_bytes(2, "big")


def parse_error_information(data: bytes) -> dict[str, int]:
    """Parse Vertuo Next error information bytes.

    Source: com.sdataway.vertuonext.sdk.characteristics.CharacErrorInformation
      byte 0: errorSelectionIndex (unsigned)
      bytes 1-2: errorCode (2-byte unsigned LSB)
    """
    if len(data) < 3:
        raise ValueError(f"Error information requires >= 3 bytes, got {len(data)}")

    error_code = _get_2bytes_unsigned_lsb(data, 1)

    return {
        "error_code": error_code,
    }


VMINI_FOTA_STATUS_NAMES: dict[int, str] = {
    0: "no_update",
    1: "update_available",
    2: "downloading",
    3: "verifying",
}


def parse_vmini_fota_status(data: bytes) -> dict[str, object]:
    """Parse VMini FOTA status bytes.

    Source: com.sdataway.vmini.sdk.characteristics.CharacFotaStatus, which
    reads one unsigned byte per field although FotaStatus declares them short.
    A Vertuo Up answers with exactly these three bytes.
      byte 0: currentStatus (FOTAStatusEnum: 0=NO_UPDATE, 1=AVAILABLE, 2=DOWNLOADING, 3=VERIFYING)
      byte 1: target
      byte 2: progress
    """
    if len(data) < 1:
        raise ValueError(f"FOTA status requires >= 1 byte, got {len(data)}")

    status_val = data[0] & 0xFF
    status_name = VMINI_FOTA_STATUS_NAMES.get(status_val, "unknown")
    progress = data[2] if len(data) >= 3 else 0

    return {
        "fota_status": status_name,
        "fota_progress": progress,
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
        "water_hardness": data[2] & 0xFF,
    }


def build_water_hardness(level: int) -> bytes:
    """Encode a water hardness write for CHAR_GENERAL_USER_SETTINGS.

    The same frame the app sends (VertuoNextMachine.setWaterHardnessLevel),
    without reading the characteristic first. It puts 0xFFFF in the APO time
    and 0xFF in activeTime2StandBy, fields it never reads or sets, so they
    are left for the machine to keep.
    """
    if not 0 <= level <= WATER_HARDNESS_MAX:
        raise ValueError(
            f"Water hardness must be 0 to {WATER_HARDNESS_MAX}, got {level}"
        )
    return bytes((0xFF, 0xFF, level, 0xFF))


def parse_vmini_asset_versions(text: str | None) -> dict[str, str]:
    """Parse the VMini asset versions characteristic.

    Semicolon-separated assets, each "name,version,required", as read off a
    Vertuo Up: "fmw-main,4.5.3,1.1.0;recipe,4.5.0,1.1.0;hmi,1.2.2,1.0.0;
    fmw-connectivity,3.18.0,2.0.0". Returns {name: version}; the third field
    is the version the asset requires of something else and is not surfaced.
    """
    versions: dict[str, str] = {}
    if not text:
        return versions
    for asset in text.split(";"):
        parts = asset.split(",")
        if len(parts) >= 2 and parts[0]:
            versions[parts[0]] = parts[1]
    return versions


def parse_vmini_shadow(
    schema_text: str | None, data_text: str | None
) -> dict[str, str]:
    """Zip the VMini shadow schema against the shadow data.

    The schema characteristic is semicolon-separated "name,type" pairs and
    the data characteristic carries one comma-separated value per field, in
    the same order. A field holding a list separates its items with ";" of
    its own, which is why the data splits on "," only. Values stay strings.
    """
    if not schema_text or not data_text:
        return {}
    fields = []
    for field in schema_text.split(";"):
        name = field.split(",")[0].strip()
        if name:
            fields.append(name)
    return dict(zip(fields, data_text.split(",")))


def parse_vmini_status(
    schema_text: str | None, data_text: str | None
) -> dict[str, object]:
    """Turn a VMini shadow into dataset fields.

    The poll and the shadow notification both come through here, so they
    agree on every field. Empty when there is no schema or no data yet.
    """
    shadow = parse_vmini_shadow(schema_text, data_text)
    if not shadow:
        return {}
    error = shadow.get("errorCode", "").strip()
    has_error = bool(error) and error.lower() != "no error"
    fields: dict[str, object] = {
        "machine_state": shadow.get("machineStatus") or "unknown",
        "error_present": has_error,
        "error_code_text": error if has_error else None,
        "shadow_data": json.dumps(shadow),
    }
    if "descalingAlert" in shadow:
        fields["descaling_needed"] = shadow["descalingAlert"] == "1"
    hardness = shadow.get("waterHardness", "")
    if hardness.isdigit():
        fields["water_hardness"] = int(hardness)
    return fields
