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

"""BLE protocol implementations for Nespresso machine families.

Each protocol class knows which GATT characteristics to read for its
machine family. All I/O happens here; parsing is delegated to parsing.py.
"""

from __future__ import annotations

import asyncio
import binascii
import logging
import uuid
from abc import ABC, abstractmethod

from bleak import BleakClient

from ..const import (
    BARISTA_CHAR_INFO,
    BARISTA_CHAR_SERIAL,
    BARISTA_CHAR_STATUS,
    VERTUO_CHAR_AUTH,
    VERTUO_CHAR_COMMAND_RSP,
    VERTUO_CHAR_ONBOARD_STATUS,
    VERTUO_CHAR_PAIR,
    VMINI_CHAR_FOTA_STATUS,
    VMINI_CHAR_FW_REV,
    VMINI_CHAR_MANUFACTURER,
    VMINI_CHAR_MODEL,
    VMINI_CHAR_PAIRING,
    VMINI_CHAR_SERIAL,
    VMINI_CHAR_SHADOW_HEADER,
    VMINI_CHAR_SW_REV,
    VMINI_CHAR_WIFI_CURRENT,
    VMINI_CHAR_WIFI_MAC,
    VERTUO_CHAR_ERROR_INFO,
    VERTUO_CHAR_INFO,
    VERTUO_CHAR_SERIAL,
    VERTUO_CHAR_STATUS,
    VERTUO_CHAR_USER_SETTINGS,
    MachineFamily,
)
from ..models import RawMachineData

_LOGGER = logging.getLogger(__name__)


def _decode_ble_string(data: bytes) -> str:
    """Decode a null-terminated BLE string characteristic."""
    return data.split(b"\x00", 1)[0].decode("utf-8", errors="replace")


def generate_auth_key() -> str:
    """Generate a random 16-hex-char auth key for machine onboarding."""
    return uuid.uuid4().hex[:16]


async def _authenticate(client: BleakClient, auth_key: str) -> bool:
    """Authenticate with the Nespresso machine after BLE pairing.

    Nespresso machines require application-level auth: a 16-char hex key
    written to CHAR_AUTH (CMID). Without this, GATT reads are denied.

    Based on: github.com/bulldog5046/ha_nespresso_integration
    """
    address = client.address

    # Check onboard status
    try:
        onboard_data = await client.read_gatt_char(VERTUO_CHAR_ONBOARD_STATUS)
        is_onboarded = onboard_data != bytearray(b"\x00")
        _LOGGER.debug(
            "Onboard status for %s: %s (raw=%s)",
            address,
            is_onboarded,
            onboard_data.hex(),
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Could not read onboard status: %s", err)
        is_onboarded = False

    # Onboard if needed
    if not is_onboarded:
        _LOGGER.info("Onboarding %s with new auth key", address)
        try:
            await client.write_gatt_char(
                VERTUO_CHAR_PAIR, bytearray([1]), response=True
            )
            await client.write_gatt_char(
                VERTUO_CHAR_AUTH, binascii.unhexlify(auth_key), response=True
            )
            await asyncio.sleep(2)

            onboard_data = await client.read_gatt_char(VERTUO_CHAR_ONBOARD_STATUS)
            is_onboarded = onboard_data != bytearray(b"\x00")
            _LOGGER.debug("Onboard status after write: %s", is_onboarded)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Onboarding failed for %s: %s", address, err)

    # Authenticate with stored key
    try:
        _LOGGER.debug(
            "Authenticating %s with key %s...", address, auth_key[:4] + "****"
        )
        await client.write_gatt_char(
            VERTUO_CHAR_AUTH, binascii.unhexlify(auth_key), response=True
        )
        _LOGGER.debug("Auth key written successfully")
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.error("Authentication failed for %s: %s", address, err)
        return False


async def _try_pair(client: BleakClient) -> bool:
    """Attempt BLE pairing via bleak, then bluetoothctl fallback."""
    address = client.address

    # Try bleak pairing first
    try:
        result = await client.pair()
        _LOGGER.debug("bleak pair() returned: %s", result)
        if result is True:
            return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("bleak pair() raised: %s", err)

    # Fallback: use bluetoothctl directly (works in Docker as root)
    _LOGGER.info("Trying bluetoothctl pairing for %s", address)
    try:
        proc = await asyncio.create_subprocess_exec(
            "bluetoothctl",
            "pair",
            address,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        _LOGGER.debug(
            "bluetoothctl pair: rc=%s stdout=%r stderr=%r",
            proc.returncode,
            stdout.decode(errors="replace").strip(),
            stderr.decode(errors="replace").strip(),
        )

        # Also trust the device so it reconnects automatically
        proc2 = await asyncio.create_subprocess_exec(
            "bluetoothctl",
            "trust",
            address,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc2.communicate(), timeout=10)

        if proc.returncode == 0:
            _LOGGER.info("bluetoothctl pairing succeeded for %s", address)
            return True

        _LOGGER.warning(
            "bluetoothctl pairing failed (rc=%s) for %s",
            proc.returncode,
            address,
        )
    except FileNotFoundError:
        _LOGGER.debug("bluetoothctl not found")
    except TimeoutError:
        _LOGGER.warning("bluetoothctl pairing timed out for %s", address)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("bluetoothctl pairing error: %s", err)

    return False


async def _dump_all_characteristics(client: BleakClient) -> dict[str, str]:
    """Read and log every readable characteristic on the device.

    This is the primary debugging tool for reverse engineering unknown
    command IDs, WiFi byte formats, and other undocumented protocol data.
    Results are included in diagnostics downloads.
    """
    dump: dict[str, str] = {}
    for service in client.services:
        for char in service.characteristics:
            if "read" not in char.properties:
                dump[char.uuid] = f"<not readable, props={char.properties}>"
                continue
            try:
                value = await client.read_gatt_char(char.uuid)
                raw_hex = bytes(value).hex()
                try:
                    text = bytes(value).decode("utf-8", errors="replace")
                except Exception:  # noqa: BLE001
                    text = ""
                dump[char.uuid] = raw_hex
                _LOGGER.debug(
                    "GATT %s [%s] = %s (text=%r)",
                    service.uuid,
                    char.uuid,
                    raw_hex,
                    text,
                )
            except Exception as err:  # noqa: BLE001
                dump[char.uuid] = f"<read error: {err}>"
                _LOGGER.debug(
                    "GATT %s [%s] read error: %s",
                    service.uuid,
                    char.uuid,
                    err,
                )
    return dump


async def _read_char(
    client: BleakClient,
    char_uuid: str,
    name: str,
    auth_key: str | None = None,
) -> bytearray:
    """Read a GATT characteristic, auto-pairing and authenticating on NotPermitted."""
    try:
        value = await client.read_gatt_char(char_uuid)
        _LOGGER.debug("Read %s [%s]: %s", name, char_uuid, value.hex())
        return value
    except Exception as err:
        err_str = str(err).lower()
        if "notpermitted" not in err_str and "not permitted" not in err_str:
            _LOGGER.error("Failed to read %s [%s]: %s", name, char_uuid, err)
            raise

        _LOGGER.info(
            "Read %s denied, attempting pair + auth for %s",
            name,
            client.address,
        )

        # Step 1: BLE-level pairing
        await _try_pair(client)
        await asyncio.sleep(1)

        # Step 2: Application-level authentication
        if auth_key:
            await _authenticate(client, auth_key)
            await asyncio.sleep(1)

        # Retry after pair + auth
        try:
            value = await client.read_gatt_char(char_uuid)
            _LOGGER.info("Read %s succeeded after pair + auth", name)
            return value
        except Exception as retry_err:
            _LOGGER.error(
                "Read %s still failed after pair + auth: %s",
                name,
                retry_err,
            )
            raise retry_err from err


class AbstractNespressoProtocol(ABC):
    """Base class for BLE protocol implementations."""

    @abstractmethod
    async def async_read_all(
        self, client: BleakClient, auth_key: str | None = None
    ) -> RawMachineData:
        """Read all relevant characteristics in a single session."""


class BaristaProtocol(AbstractNespressoProtocol):
    """BLE protocol for Barista (Original Line) machines."""

    async def async_read_all(
        self, client: BleakClient, auth_key: str | None = None
    ) -> RawMachineData:
        status = await _read_char(client, BARISTA_CHAR_STATUS, "status", auth_key)
        info = await _read_char(client, BARISTA_CHAR_INFO, "machine_info", auth_key)
        serial = await _read_char(client, BARISTA_CHAR_SERIAL, "serial", auth_key)
        # GATT dump only when debug logging is active
        gatt_dump = None
        if _LOGGER.isEnabledFor(logging.DEBUG):
            gatt_dump = await _dump_all_characteristics(client)

        return RawMachineData(
            status_bytes=bytes(status),
            info_bytes=bytes(info),
            serial_bytes=bytes(serial),
            gatt_dump=gatt_dump,
        )


class VertuoNextProtocol(AbstractNespressoProtocol):
    """BLE protocol for Vertuo Next (Venus Line) machines."""

    async def async_read_all(
        self, client: BleakClient, auth_key: str | None = None
    ) -> RawMachineData:
        status = await _read_char(client, VERTUO_CHAR_STATUS, "status", auth_key)
        info = await _read_char(client, VERTUO_CHAR_INFO, "machine_info", auth_key)
        serial = await _read_char(client, VERTUO_CHAR_SERIAL, "serial", auth_key)
        settings = await _read_char(
            client, VERTUO_CHAR_USER_SETTINGS, "user_settings", auth_key
        )
        error_info = await _read_char(
            client, VERTUO_CHAR_ERROR_INFO, "error_info", auth_key
        )

        # Read command response for any unsolicited data (debugging)
        try:
            cmd_rsp = await client.read_gatt_char(VERTUO_CHAR_COMMAND_RSP)
            _LOGGER.debug("VertuoNext command response: %s", cmd_rsp.hex())
        except Exception:  # noqa: BLE001
            _LOGGER.debug("VertuoNext command response not readable")
        # GATT dump only when debug logging is active
        gatt_dump = None
        if _LOGGER.isEnabledFor(logging.DEBUG):
            gatt_dump = await _dump_all_characteristics(client)

        return RawMachineData(
            status_bytes=bytes(status),
            info_bytes=bytes(info),
            serial_bytes=bytes(serial),
            user_settings_bytes=bytes(settings),
            error_info_bytes=bytes(error_info),
            gatt_dump=gatt_dump,
        )


class VMiniProtocol(AbstractNespressoProtocol):
    """BLE protocol for VMini (Vertuo Mini) machines."""

    async def async_read_all(
        self, client: BleakClient, auth_key: str | None = None
    ) -> RawMachineData:
        serial = await _read_char(client, VMINI_CHAR_SERIAL, "serial", auth_key)
        pairing = await _read_char(client, VMINI_CHAR_PAIRING, "pairing", auth_key)
        fw = await _read_char(client, VMINI_CHAR_FW_REV, "firmware_rev", auth_key)
        sw = await _read_char(client, VMINI_CHAR_SW_REV, "software_rev", auth_key)
        model = await _read_char(client, VMINI_CHAR_MODEL, "model", auth_key)
        manufacturer = await _read_char(
            client, VMINI_CHAR_MANUFACTURER, "manufacturer", auth_key
        )
        # Optional chars that may not be available before WiFi setup
        wifi_mac = None
        wifi_current = None
        shadow = None
        fota_status = None
        try:
            fota_status = await client.read_gatt_char(VMINI_CHAR_FOTA_STATUS)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("VMini FOTA status not available")
        try:
            wifi_mac = await client.read_gatt_char(VMINI_CHAR_WIFI_MAC)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("VMini WiFi MAC not available")
        try:
            wifi_current = await client.read_gatt_char(VMINI_CHAR_WIFI_CURRENT)
            _LOGGER.debug(
                "VMini WiFi current setting raw: %s (len=%d, text=%r)",
                wifi_current.hex(),
                len(wifi_current),
                bytes(wifi_current).decode("utf-8", errors="replace"),
            )
        except Exception:  # noqa: BLE001
            _LOGGER.debug("VMini WiFi current setting not available")
        try:
            shadow = await client.read_gatt_char(VMINI_CHAR_SHADOW_HEADER)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("VMini shadow header not available")
        _LOGGER.debug(
            "VMini raw: serial=%s pairing=%s fw=%s model=%s shadow=%s",
            serial.hex(),
            pairing.hex(),
            fw.hex(),
            model.hex(),
            shadow.hex() if shadow else "N/A",
        )
        # GATT dump only when debug logging is active
        gatt_dump_result = None
        if _LOGGER.isEnabledFor(logging.DEBUG):
            gatt_dump_result = await _dump_all_characteristics(client)

        return RawMachineData(
            serial_bytes=bytes(serial),
            pairing_byte=pairing[0] if pairing else None,
            firmware_version=_decode_ble_string(bytes(fw)),
            software_version=_decode_ble_string(bytes(sw)),
            model_number=_decode_ble_string(bytes(model)),
            manufacturer=_decode_ble_string(bytes(manufacturer)),
            wifi_mac=_decode_ble_string(bytes(wifi_mac)) if wifi_mac else None,
            shadow_header=_decode_ble_string(bytes(shadow)) if shadow else None,
            fota_status_bytes=bytes(fota_status) if fota_status else None,
            wifi_current_bytes=bytes(wifi_current) if wifi_current else None,
            gatt_dump=gatt_dump_result,
        )


_PROTOCOL_MAP: dict[MachineFamily, type[AbstractNespressoProtocol]] = {
    MachineFamily.BARISTA: BaristaProtocol,
    MachineFamily.VERTUO_NEXT: VertuoNextProtocol,
    MachineFamily.VMINI: VMiniProtocol,
}


def get_protocol(family: MachineFamily) -> AbstractNespressoProtocol:
    """Return the protocol instance for a given machine family."""
    return _PROTOCOL_MAP[family]()
