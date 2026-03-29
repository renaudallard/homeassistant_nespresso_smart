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
    BARISTA_CHAR_AUTH,
    BARISTA_CHAR_INFO,
    BARISTA_CHAR_MACHINE_PARAMS,
    BARISTA_CHAR_PROFILE_VERSION,
    BARISTA_CHAR_RECIPE_INFO,
    BARISTA_CHAR_ONBOARD_STATUS,
    BARISTA_CHAR_PAIR,
    BARISTA_CHAR_SERIAL,
    BARISTA_CHAR_STATUS,
    VERTUO_CHAR_AUTH,
    VERTUO_CHAR_CAPS_COUNTER,
    VERTUO_CHAR_COMMAND_RSP,
    VERTUO_CHAR_ERROR_INFO,
    VERTUO_CHAR_ERROR_SELECTION,
    VERTUO_CHAR_INFO,
    VERTUO_CHAR_IOT_MARKET,
    VERTUO_CHAR_MACHINE_PARAMS,
    VERTUO_CHAR_ONBOARD_STATUS,
    VERTUO_CHAR_PAIR,
    VERTUO_CHAR_PROFILE_VERSION,
    VERTUO_CHAR_SERIAL,
    VERTUO_CHAR_STATUS,
    VERTUO_CHAR_USER_SETTINGS,
    VMINI_CHAR_MACHINE_TOKEN,
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


# "pair" key maps to CHAR_TX_LEVEL_CHANGE_REQUEST in the APK.
# Writing 0x01 (REDUCE_POWER) initiates the pairing/onboarding sequence.
_AUTH_UUIDS: dict[str, dict[str, str]] = {
    MachineFamily.BARISTA: {
        "auth": BARISTA_CHAR_AUTH,
        "onboard": BARISTA_CHAR_ONBOARD_STATUS,
        "pair": BARISTA_CHAR_PAIR,
    },
    MachineFamily.VERTUO_NEXT: {
        "auth": VERTUO_CHAR_AUTH,
        "onboard": VERTUO_CHAR_ONBOARD_STATUS,
        "pair": VERTUO_CHAR_PAIR,
    },
}


# Strategies tried in order. The working one is remembered.
AUTH_STRATEGY_UNKNOWN = "unknown"
AUTH_STRATEGY_DIRECT = "direct"  # No pair, write with response
AUTH_STRATEGY_PAIR_THEN_WRITE = "pair"  # pair() + write with response
AUTH_STRATEGY_FIRE_AND_FORGET = "fire_and_forget"  # No pair, write without response

# Module-level cache: address -> working strategy
_auth_strategy_cache: dict[str, str] = {}


async def _authenticate(
    client: BleakClient, auth_key: str, family: MachineFamily
) -> bool:
    """Authenticate with the Nespresso machine.

    Tries multiple strategies and remembers which one works:
    1. Direct: write CMID with response (no BLE pairing)
    2. Pair then write: client.pair() + write CMID with response
    3. Fire and forget: write CMID without response (avoids ATT errors)
    """
    address = client.address

    if family == MachineFamily.VMINI:
        return await _authenticate_vmini(client, auth_key)

    uuids = _AUTH_UUIDS.get(family)
    if not uuids:
        _LOGGER.debug("No auth UUIDs for family %s", family)
        return False

    auth_bytes = binascii.unhexlify(auth_key)

    # Check onboard status
    try:
        onboard_data = await client.read_gatt_char(uuids["onboard"])
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
        await _onboard(client, uuids, auth_bytes, address, family)

    # Authenticate using known strategy or try all
    cached = _auth_strategy_cache.get(address)
    if cached and cached != AUTH_STRATEGY_UNKNOWN:
        _LOGGER.debug("Using cached auth strategy: %s", cached)
        return await _try_strategy(client, uuids, auth_bytes, cached, address)

    # Try each strategy until one works
    # fire_and_forget first: doesn't corrupt bleak if it fails
    # direct second: may get ATT error that corrupts connection
    # pair last: most disruptive, may corrupt connection
    for strategy in (
        AUTH_STRATEGY_FIRE_AND_FORGET,
        AUTH_STRATEGY_DIRECT,
        AUTH_STRATEGY_PAIR_THEN_WRITE,
    ):
        _LOGGER.info("Trying auth strategy '%s' for %s", strategy, address)
        if await _try_strategy(client, uuids, auth_bytes, strategy, address):
            _auth_strategy_cache[address] = strategy
            _LOGGER.info(
                "Auth strategy '%s' succeeded for %s, remembering", strategy, address
            )
            return True

    _LOGGER.error("All auth strategies failed for %s", address)
    return False


async def _onboard(
    client: BleakClient,
    uuids: dict[str, str],
    auth_bytes: bytes,
    address: str,
    family: MachineFamily,
) -> None:
    """Onboard a new machine: write TX level + CMID."""
    _LOGGER.info("Onboarding %s (%s) with new auth key", address, family.value)

    try:
        await client.write_gatt_char(uuids["pair"], bytearray([1]), response=False)
        _LOGGER.debug("TX level write sent")
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("TX level write failed (non-fatal): %s", err)

    await asyncio.sleep(1)

    try:
        await client.write_gatt_char(uuids["auth"], auth_bytes, response=False)
        _LOGGER.debug("Onboarding CMID write sent")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Onboarding CMID write failed for %s: %s", address, err)

    await asyncio.sleep(3)


async def _try_strategy(
    client: BleakClient,
    uuids: dict[str, str],
    auth_bytes: bytes,
    strategy: str,
    address: str,
) -> bool:
    """Try a single auth strategy. Returns True if the subsequent read works."""
    try:
        if strategy == AUTH_STRATEGY_PAIR_THEN_WRITE:
            try:
                await client.pair()
                await asyncio.sleep(2)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("pair() failed: %s", err)
                return False
            await client.write_gatt_char(uuids["auth"], auth_bytes, response=True)

        elif strategy == AUTH_STRATEGY_DIRECT:
            await client.write_gatt_char(uuids["auth"], auth_bytes, response=True)

        elif strategy == AUTH_STRATEGY_FIRE_AND_FORGET:
            await client.write_gatt_char(uuids["auth"], auth_bytes, response=False)
            await asyncio.sleep(1)

        # Verify auth worked by reading a protected characteristic
        await client.read_gatt_char(uuids["onboard"])
        _LOGGER.debug("Strategy '%s' auth verified", strategy)
        return True

    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Strategy '%s' failed: %s", strategy, err)
        return False


async def _authenticate_vmini(client: BleakClient, auth_key: str) -> bool:
    """Authenticate VMini using 36-byte MachineToken."""
    address = client.address
    try:
        token = auth_key.encode("utf-8").ljust(36, b"\x00")
        _LOGGER.debug(
            "Writing VMini machine token for %s: %s...",
            address,
            token[:8].hex(),
        )
        await client.write_gatt_char(VMINI_CHAR_MACHINE_TOKEN, token, response=True)
        _LOGGER.debug("VMini machine token written successfully")
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.error("VMini authentication failed for %s: %s", address, err)
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
    family: MachineFamily = MachineFamily.VERTUO_NEXT,
) -> bytearray:
    """Read a GATT characteristic. Auth is done upfront by the coordinator."""
    try:
        value = await client.read_gatt_char(char_uuid)
        _LOGGER.debug("Read %s [%s]: %s", name, char_uuid, value.hex())
        return value
    except Exception as err:
        _LOGGER.error("Failed to read %s [%s]: %s", name, char_uuid, err)
        raise


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
        f = MachineFamily.BARISTA
        status = await _read_char(client, BARISTA_CHAR_STATUS, "status", auth_key, f)
        info = await _read_char(client, BARISTA_CHAR_INFO, "machine_info", auth_key, f)
        serial = await _read_char(client, BARISTA_CHAR_SERIAL, "serial", auth_key, f)
        profile = await _read_char(
            client, BARISTA_CHAR_PROFILE_VERSION, "profile_version", auth_key, f
        )
        params = await _read_char(
            client, BARISTA_CHAR_MACHINE_PARAMS, "machine_params", auth_key, f
        )
        # Recipe information (optional)
        recipe_info = None
        try:
            recipe_info = await client.read_gatt_char(BARISTA_CHAR_RECIPE_INFO)
            _LOGGER.debug("Recipe info raw: %s", recipe_info.hex())
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Recipe info not available")
        # GATT dump only when debug logging is active
        gatt_dump = None
        if _LOGGER.isEnabledFor(logging.DEBUG):
            gatt_dump = await _dump_all_characteristics(client)

        return RawMachineData(
            status_bytes=bytes(status),
            info_bytes=bytes(info),
            serial_bytes=bytes(serial),
            profile_version_bytes=bytes(profile),
            machine_params_bytes=bytes(params),
            recipe_info_bytes=bytes(recipe_info) if recipe_info else None,
            gatt_dump=gatt_dump,
        )


class VertuoNextProtocol(AbstractNespressoProtocol):
    """BLE protocol for Vertuo Next (Venus Line) machines."""

    async def async_read_all(
        self, client: BleakClient, auth_key: str | None = None
    ) -> RawMachineData:
        f = MachineFamily.VERTUO_NEXT
        status = await _read_char(client, VERTUO_CHAR_STATUS, "status", auth_key, f)
        info = await _read_char(client, VERTUO_CHAR_INFO, "machine_info", auth_key, f)
        serial = await _read_char(client, VERTUO_CHAR_SERIAL, "serial", auth_key, f)
        profile = await _read_char(
            client, VERTUO_CHAR_PROFILE_VERSION, "profile_version", auth_key, f
        )
        params = await _read_char(
            client, VERTUO_CHAR_MACHINE_PARAMS, "machine_params", auth_key, f
        )
        settings = await _read_char(
            client, VERTUO_CHAR_USER_SETTINGS, "user_settings", auth_key, f
        )
        # Select current active error (index 0) then read error info
        try:
            await client.write_gatt_char(
                VERTUO_CHAR_ERROR_SELECTION, bytes([0]), response=True
            )
            _LOGGER.debug("Error selection set to index 0 (current active)")
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Error selection write not available")
        error_info = await _read_char(
            client, VERTUO_CHAR_ERROR_INFO, "error_info", auth_key, f
        )

        # Also read error at index 1 (error present in list) for diagnostics
        error_list_entry = None
        try:
            await client.write_gatt_char(
                VERTUO_CHAR_ERROR_SELECTION, bytes([1]), response=True
            )
            error_list_entry = await client.read_gatt_char(VERTUO_CHAR_ERROR_INFO)
            _LOGGER.debug("Error list entry raw: %s", error_list_entry.hex())
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Error list entry not available")

        # Capsule counter (optional, may not be available on all models)
        caps_counter = None
        try:
            caps_counter = await client.read_gatt_char(VERTUO_CHAR_CAPS_COUNTER)
            _LOGGER.debug("Capsule counter raw: %s", caps_counter.hex())
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Capsule counter not available")

        # IoT market name (optional)
        iot_market = None
        try:
            iot_market = await client.read_gatt_char(VERTUO_CHAR_IOT_MARKET)
            _LOGGER.debug("IoT market name: %s", _decode_ble_string(bytes(iot_market)))
        except Exception:  # noqa: BLE001
            _LOGGER.debug("IoT market name not available")

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
            profile_version_bytes=bytes(profile),
            machine_params_bytes=bytes(params),
            user_settings_bytes=bytes(settings),
            error_info_bytes=bytes(error_info),
            caps_counter_bytes=bytes(caps_counter) if caps_counter else None,
            error_list_bytes=bytes(error_list_entry) if error_list_entry else None,
            iot_market_bytes=bytes(iot_market) if iot_market else None,
            gatt_dump=gatt_dump,
        )


class VMiniProtocol(AbstractNespressoProtocol):
    """BLE protocol for VMini (Vertuo Mini) machines."""

    async def async_read_all(
        self, client: BleakClient, auth_key: str | None = None
    ) -> RawMachineData:
        f = MachineFamily.VMINI
        serial = await _read_char(client, VMINI_CHAR_SERIAL, "serial", auth_key, f)
        pairing = await _read_char(client, VMINI_CHAR_PAIRING, "pairing", auth_key, f)
        fw = await _read_char(client, VMINI_CHAR_FW_REV, "firmware_rev", auth_key, f)
        sw = await _read_char(client, VMINI_CHAR_SW_REV, "software_rev", auth_key, f)
        model = await _read_char(client, VMINI_CHAR_MODEL, "model", auth_key, f)
        manufacturer = await _read_char(
            client, VMINI_CHAR_MANUFACTURER, "manufacturer", auth_key, f
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
