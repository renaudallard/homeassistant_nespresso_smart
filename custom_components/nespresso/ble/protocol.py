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
import weakref
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from functools import partial
from typing import TypeVar

from bleak import BleakClient, BleakError

from ..const import (
    BARISTA_CHAR_AUTH,
    BARISTA_CHAR_INFO,
    BARISTA_CHAR_MACHINE_PARAMS,
    BARISTA_CHAR_ONBOARD_STATUS,
    BARISTA_CHAR_PAIR,
    BARISTA_CHAR_PROFILE_VERSION,
    BARISTA_CHAR_RECIPE_INFO,
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
    VMINI_CHAR_FOTA_STATUS,
    VMINI_CHAR_FW_REV,
    VMINI_CHAR_MACHINE_TOKEN,
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


# Every BLE operation needs an explicit timeout. Neither bleak nor BlueZ
# enforces one: when BlueZ tries to raise link security and the machine does
# not answer, the await hangs forever. Without this, a config entry stayed
# 315 seconds in "initializing" and could not be deleted while it held the
# coordinator lock.
BLE_OP_TIMEOUT = 10.0

# A pairing request needs its own budget. The ESPHome API waits 30 seconds for
# the proxy to answer, so a machine that never finishes the exchange would
# stall a whole poll while the coordinator lock is held.
BLE_PAIR_TIMEOUT = 10.0

# ATT error a machine returns when it will not answer over a plain link.
ATT_INSUFFICIENT_AUTHENTICATION = 5

# Clients whose link we already asked to encrypt. A machine that keeps
# refusing afterwards must not trigger a pairing request per characteristic.
_ELEVATED: weakref.WeakSet[BleakClient] = weakref.WeakSet()

_T = TypeVar("_T")


def _att_error(err: BaseException) -> int | None:
    """Return the ATT error code carried by err, or None.

    bleak-esphome turns the proxy error into a plain BleakError, so the
    numeric status only survives on the cause chain, one level down for a
    direct operation and two when it comes back through establish_connection.
    Read by duck typing on purpose: aioesphomeapi is only installed alongside
    the ESPHome integration, and no bleak exception carries an "error"
    attribute, so this cannot match on a local adapter.
    """
    cause: BaseException | None = err
    while cause is not None:
        code = getattr(getattr(cause, "error", None), "error", None)
        if isinstance(code, int):
            return code
        cause = cause.__cause__
    return None


async def _elevate(client: BleakClient, err: BleakError) -> bool:
    """Encrypt the link when the machine demands authentication.

    Returns True when the caller should retry the operation. BlueZ raises link
    security on its own and retries the operation transparently, so this only
    ever runs on a connection through a Bluetooth proxy, which forwards the
    error and waits for the host to ask. The bond is then negotiated and
    stored by the proxy itself, not by the Home Assistant host.
    """
    if _att_error(err) != ATT_INSUFFICIENT_AUTHENTICATION:
        return False
    if client in _ELEVATED:
        _LOGGER.debug("%s still refuses to answer after pairing", client.address)
        return False
    _ELEVATED.add(client)
    try:
        await asyncio.wait_for(client.pair(), BLE_PAIR_TIMEOUT)
    except NotImplementedError:
        _LOGGER.warning(
            "The Bluetooth proxy serving %s cannot pair. Set 'active: true' under "
            "bluetooth_proxy in the proxy configuration, update its ESPHome "
            "firmware, then reload the integration.",
            client.address,
        )
        return False
    except (BleakError, TimeoutError) as pair_err:
        # The request may still have created a bond on the proxy, which the
        # next connection reuses. Nothing to undo here. A timeout carries no
        # message of its own, so fall back to the exception name.
        _LOGGER.warning(
            "Pairing %s through the Bluetooth proxy failed: %s. If this repeats, "
            "the machine is asking for a passkey, which a proxy cannot provide.",
            client.address,
            str(pair_err) or type(pair_err).__name__,
        )
        return False
    _LOGGER.info("Encrypted the link to %s", client.address)
    return True


async def _gatt_op(client: BleakClient, op: Callable[[], Awaitable[_T]]) -> _T:
    """Run one GATT operation, encrypting the link first if the machine asks."""
    try:
        return await asyncio.wait_for(op(), BLE_OP_TIMEOUT)
    except BleakError as err:
        if not await _elevate(client, err):
            raise
    return await asyncio.wait_for(op(), BLE_OP_TIMEOUT)


async def _read(client: BleakClient, char: str) -> bytearray:
    """Read a characteristic, failing fast instead of hanging."""
    return await _gatt_op(client, partial(client.read_gatt_char, char))


async def _write(
    client: BleakClient, char: str, data: bytes, *, response: bool = True
) -> None:
    """Write a characteristic, failing fast instead of hanging."""
    await _gatt_op(
        client, partial(client.write_gatt_char, char, data, response=response)
    )


# "pair" key maps to CHAR_TX_LEVEL_CHANGE_REQUEST in the APK.
# Writing 0x01 (REDUCE_POWER) initiates the pairing/onboarding sequence.
_AUTH_UUIDS: dict[str, dict[str, str]] = {
    MachineFamily.BARISTA: {
        "auth": BARISTA_CHAR_AUTH,
        "onboard": BARISTA_CHAR_ONBOARD_STATUS,
        "pair": BARISTA_CHAR_PAIR,
        "verify": BARISTA_CHAR_STATUS,
    },
    MachineFamily.VERTUO_NEXT: {
        "auth": VERTUO_CHAR_AUTH,
        "onboard": VERTUO_CHAR_ONBOARD_STATUS,
        "pair": VERTUO_CHAR_PAIR,
        "verify": VERTUO_CHAR_STATUS,
    },
}


async def _authenticate(
    client: BleakClient, auth_key: str, family: MachineFamily
) -> bool:
    """Authenticate with the Nespresso machine.

    Matches the APK flow: write CMID with response, verify by reading
    a protected characteristic. This is not BLE pairing, since the APK does
    not call createBond, and it is separate from link encryption: Android
    negotiates that on its own. Neither transport Home Assistant uses does it
    unprompted, which is why the operations below can fail on a machine that
    has no bond. Through a Bluetooth proxy they come back as an ATT error and
    _gatt_op asks the proxy to pair. Through a local adapter BlueZ raises the
    security itself and then waits for a pairing agent nobody registers, so
    the operation hangs instead.
    """
    address = client.address

    if family == MachineFamily.VMINI:
        return await _authenticate_vmini(client, auth_key)

    uuids = _AUTH_UUIDS.get(family)
    if not uuids:
        _LOGGER.debug("No auth UUIDs for family %s", family)
        return False

    auth_bytes = binascii.unhexlify(auth_key)

    # Check onboard status: True / False / None when unknown
    onboard_data: bytearray | None = None
    is_onboarded: bool | None = None
    try:
        onboard_data = await _read(client, uuids["onboard"])
        is_onboarded = onboard_data != bytearray(b"\x00")
        _LOGGER.debug(
            "Onboard status for %s: %s (raw=%s)",
            address,
            is_onboarded,
            onboard_data.hex(),
        )
    except TimeoutError:
        # A hang here is the signature of an unencrypted link on a local
        # adapter, which no other symptom makes obvious, so spell out the fix.
        # A proxy never hangs on this, it answers with an ATT error that
        # _gatt_op has already handled by the time we get here.
        _LOGGER.warning(
            "Reading onboard status from %s timed out, so the link is not encrypted. Pair the machine once from a terminal on the Home Assistant host: bluetoothctl / agent NoInputNoOutput / default-agent / scan on / pair %s. Note that the default 'agent on' does NOT work: it requests MITM protection with a passkey, which a coffee machine cannot provide. Through an ESPHome Bluetooth proxy this is not the right remedy, the proxy pairs by itself and only needs 'active: true' under bluetooth_proxy.",
            address,
            address,
        )
        is_onboarded = None
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Could not read onboard status: %s", err)
        # UNKNOWN, not "not onboarded". This read fails on a link the machine
        # will not answer over, even when it is already onboarded.
        is_onboarded = None

    # Onboard only when we know for sure it has not happened. When the state
    # is unknown, just write the CMID and let the verify decide. Otherwise an
    # already-onboarded machine gets a second onboarding attempt, which it
    # rejects with GATT 0x0E UNLIKELY_ERROR and drops the connection.
    if is_onboarded is False:
        await _onboard(client, uuids, auth_bytes, address, family)

    # Write CMID with response (matches APK and bulldog)
    try:
        await _write(client, uuids["auth"], auth_bytes, response=True)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("CMID write failed for %s: %s", address, err)
        return False

    # Verify auth by reading a protected characteristic
    verify_uuid = uuids.get("verify") or uuids.get("onboard")
    if verify_uuid:
        try:
            await _read(client, verify_uuid)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Auth verify read failed for %s: %s", address, err)
            if is_onboarded is False:
                return False
            # Machine was already onboarded (likely by the Nespresso app).
            # Force re-onboard to register our CMID, then retry auth.
            _LOGGER.info(
                "Force re-onboard for %s (was onboarded=0x%s)",
                address,
                onboard_data.hex() if onboard_data is not None else "unknown",
            )
            await _onboard(client, uuids, auth_bytes, address, family)
            try:
                await _write(client, uuids["auth"], auth_bytes, response=True)
            except Exception as err2:  # noqa: BLE001
                _LOGGER.debug(
                    "CMID write after re-onboard failed for %s: %s", address, err2
                )
                return False
            try:
                await _read(client, verify_uuid)
            except Exception as err2:  # noqa: BLE001
                _LOGGER.debug(
                    "Auth still failed after re-onboard for %s: %s", address, err2
                )
                return False

    _LOGGER.debug("Auth succeeded for %s", address)
    return True


async def _onboard(
    client: BleakClient,
    uuids: dict[str, str],
    auth_bytes: bytes,
    address: str,
    family: MachineFamily,
) -> bool:
    """Onboard a new machine: write TX level + CMID, verify.

    Matches the APK flow: TX level, CMID, wait 2s, verify CMID_TYPE.
    """
    _LOGGER.info("Onboarding %s (%s) with new auth key", address, family.value)

    try:
        await _write(client, uuids["pair"], bytes([1]), response=False)
        _LOGGER.debug("TX level write sent")
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("TX level write failed (non-fatal): %s", err)

    try:
        await _write(client, uuids["auth"], auth_bytes, response=True)
        _LOGGER.debug("Onboarding CMID write sent")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Onboarding CMID write failed for %s: %s", address, err)
        return False

    await asyncio.sleep(2)

    # Verify onboarding succeeded
    try:
        onboard_data = await _read(client, uuids["onboard"])
        is_final = onboard_data != bytearray(b"\x00")
        _LOGGER.debug(
            "Onboard verify for %s: %s (raw=%s)", address, is_final, onboard_data.hex()
        )
        return is_final
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Onboard verify read failed for %s: %s", address, err)
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
        await _write(client, VMINI_CHAR_MACHINE_TOKEN, token, response=True)
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
                value = await _read(client, char.uuid)
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
        value = await _read(client, char_uuid)
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
            recipe_info = await _read(client, BARISTA_CHAR_RECIPE_INFO)
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
            await _write(client, VERTUO_CHAR_ERROR_SELECTION, bytes([0]), response=True)
            _LOGGER.debug("Error selection set to index 0 (current active)")
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Error selection write not available")
        error_info = await _read_char(
            client, VERTUO_CHAR_ERROR_INFO, "error_info", auth_key, f
        )

        # Also read error at index 1 (error present in list) for diagnostics
        error_list_entry = None
        try:
            await _write(client, VERTUO_CHAR_ERROR_SELECTION, bytes([1]), response=True)
            error_list_entry = await _read(client, VERTUO_CHAR_ERROR_INFO)
            _LOGGER.debug("Error list entry raw: %s", error_list_entry.hex())
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Error list entry not available")

        # Capsule counter (optional, may not be available on all models)
        caps_counter = None
        try:
            caps_counter = await _read(client, VERTUO_CHAR_CAPS_COUNTER)
            _LOGGER.debug("Capsule counter raw: %s", caps_counter.hex())
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Capsule counter not available")

        # IoT market name (optional)
        iot_market = None
        try:
            iot_market = await _read(client, VERTUO_CHAR_IOT_MARKET)
            _LOGGER.debug("IoT market name: %s", _decode_ble_string(bytes(iot_market)))
        except Exception:  # noqa: BLE001
            _LOGGER.debug("IoT market name not available")

        # Read command response for any unsolicited data (debugging)
        try:
            cmd_rsp = await _read(client, VERTUO_CHAR_COMMAND_RSP)
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
            fota_status = await _read(client, VMINI_CHAR_FOTA_STATUS)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("VMini FOTA status not available")
        try:
            wifi_mac = await _read(client, VMINI_CHAR_WIFI_MAC)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("VMini WiFi MAC not available")
        try:
            wifi_current = await _read(client, VMINI_CHAR_WIFI_CURRENT)
            _LOGGER.debug(
                "VMini WiFi current setting raw: %s (len=%d, text=%r)",
                wifi_current.hex(),
                len(wifi_current),
                bytes(wifi_current).decode("utf-8", errors="replace"),
            )
        except Exception:  # noqa: BLE001
            _LOGGER.debug("VMini WiFi current setting not available")
        try:
            shadow = await _read(client, VMINI_CHAR_SHADOW_HEADER)
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
