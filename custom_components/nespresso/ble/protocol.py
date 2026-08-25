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
    CMID_TYPE_FINAL,
    CMID_TYPE_NAMES,
    CMID_TYPE_UNPAIRED,
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

# ATT errors a machine returns when it will not answer over a plain link. It
# sends 5, insufficient authentication, while it holds no key for us, and 15,
# insufficient encryption, once it has one and only wants the link turned on.
# A single pairing request covers both, because the proxy runs the full
# exchange when there is no key and starts encryption from the stored one when
# there is. BlueZ makes the same equivalence in its own escalation path.
ATT_NEEDS_ENCRYPTION = frozenset({5, 15})

# ATT error a machine returns when the auth token we wrote is not the one it
# stores. The code is the same whether the token is wrong or absent.
ATT_READ_NOT_PERMITTED = 2

# How long to wait for a machine to accept a token, and how often to ask.
#
# The machine does not answer the CMID write with its verdict. It settles some
# time afterwards, and until it does it keeps reporting an unpaired state. The
# app handles that by reading CMID_TYPE straight after the write and then once
# a second until the value leaves NONE/UNDEFINED
# (VertuoNextMachine.j in the APK). The poll is the part that matters: reading
# the state once after a fixed delay is what left a Creatista stuck, because
# the read came back UNDEFINED, which is not NONE, so the machine looked
# onboarded while it held no token at all.
#
# The app then repeats that whole sequence up to four times, because a user is
# waiting on it and it has one connection to get the job done in. Two is enough
# here: the second covers a write that failed outright, and the poll cycle
# supplies the rest of the retries a few seconds later, against the same
# machine state. Four would put the worst case past the default scan interval,
# and the coordinator tries authentication twice per cycle.
ONBOARD_POLL_ATTEMPTS = 10
ONBOARD_POLL_INTERVAL = 1.0
ONBOARD_ATTEMPTS = 2
ONBOARD_RETRY_DELAY = 2.0

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


def _is_read_not_permitted(err: BaseException) -> bool:
    """True when the machine refused a read because our auth token is wrong.

    One condition, three shapes. Through a Bluetooth proxy the numeric ATT code
    survives on the cause chain. On a local adapter bleak raises a typed error
    carrying the same code. Older bleak leaves the raw BlueZ error behind.

    Never match on the BlueZ error name. BlueZ answers org.bluez.Error.NotPermitted
    for ATT 2 and also for ATT 5, 12 and 15, which mean the link is not encrypted
    and are somebody else's problem entirely: only the detail string separates
    them, "Read not permitted" against "Not paired". Matching the name told users
    to factory reset a machine that merely needed pairing.

    _att_error is deliberately left alone. It sees none of these, so _elevate
    never fires on a local adapter, which is correct: BlueZ raises link security
    by itself and has no pairing agent to answer if we asked.
    """
    if _att_error(err) == ATT_READ_NOT_PERMITTED:
        return True
    code = getattr(err, "code", None)
    if isinstance(code, int):
        return code == ATT_READ_NOT_PERMITTED
    return getattr(err, "dbus_error_details", None) == "Read not permitted"


async def _elevate(client: BleakClient, err: BleakError) -> bool:
    """Encrypt the link when the machine refuses to answer without it.

    Returns True when the caller should retry the operation. BlueZ raises link
    security on its own and retries the operation transparently, so this only
    ever runs on a connection through a Bluetooth proxy, which forwards the
    error and waits for the host to ask. The bond is then negotiated and
    stored by the proxy itself, not by the Home Assistant host.
    """
    if _att_error(err) not in ATT_NEEDS_ENCRYPTION:
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
    client: BleakClient,
    auth_key: str,
    family: MachineFamily,
    send_tx_level: bool = True,
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

    state = await _read_cmid_type(client, uuids["onboard"], address)

    # Onboard whenever the machine holds no usable token. NONE and UNDEFINED
    # both mean exactly that, and the app makes no distinction between them
    # either. Treating UNDEFINED as onboarded is what latched a Creatista into
    # a state it could never leave: the state is not NONE, so onboarding was
    # skipped from then on, and every protected read was refused.
    #
    # A machine that already holds a token keeps it whatever we write, so
    # onboarding one of those achieves nothing, and some answer GATT 0x0E
    # UNLIKELY_ERROR and drop the connection. When the state cannot be read at
    # all, just write the CMID and let the verify decide.
    if state in CMID_TYPE_UNPAIRED:
        state = await _onboard(
            client, uuids, auth_bytes, address, family, state, send_tx_level
        )
        if not client.is_connected:
            # Everything below would fail with "characteristic not found",
            # which describes bleak's empty service cache rather than anything
            # the machine did. _onboard has already said what happened.
            return False

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
            if _is_read_not_permitted(err):
                _explain_refused_read(address, state)
            else:
                _LOGGER.debug("Auth verify read failed for %s: %s", address, err)
            return False

    _LOGGER.debug("Auth succeeded for %s", address)
    return True


def _describe_cmid_type(state: int | None) -> str:
    """Render a pairing key state for a log line."""
    if state is None:
        return "unreadable"
    name = CMID_TYPE_NAMES.get(state)
    return f"0x{state:02x} {name.upper()}" if name else f"0x{state:02x}"


async def _read_cmid_type(client: BleakClient, char: str, address: str) -> int | None:
    """Read the machine's pairing key state, or None when it will not say.

    Only byte 0 carries the state, which is all CharacCMIDType.updateValues
    reads in the APK.
    """
    try:
        data = await _read(client, char)
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
        return None
    except Exception as err:  # noqa: BLE001
        # UNKNOWN, not "not onboarded". This read fails on a link the machine
        # will not answer over, even when it is already onboarded.
        _LOGGER.debug("Could not read onboard status from %s: %s", address, err)
        return None

    if not data:
        _LOGGER.debug("Onboard status read from %s came back empty", address)
        return None

    _LOGGER.debug("Onboard status for %s: %s", address, _describe_cmid_type(data[0]))
    return data[0]


def _report_lost_link(address: str, tx_acknowledged: bool) -> None:
    """Say why the machine went away in the middle of onboarding.

    A link that dies immediately after the TX level request dies for a reason
    we can name. That request asks the machine to reduce its radio power, and a
    machine that has just gone quiet is one a distant receiver stops hearing.
    The official app leans on the same request and tells the user to stay
    within a metre of the machine while it pairs, which is affordable advice
    for a phone in your hand and not for a proxy on a shelf.
    """
    if tx_acknowledged:
        _LOGGER.warning(
            "%s acknowledged the TX level request and then dropped the link, so the auth token never reached it. That request tells the machine to reduce its radio power for the rest of the exchange, and a Bluetooth adapter or proxy that is not close enough stops hearing it the moment it does. Move the proxy next to the machine, within a metre, and reload. It can go back where it was afterwards, since the machine only goes quiet while it is being paired.",
            address,
        )
        return
    _LOGGER.warning(
        "%s dropped the connection while being onboarded, so the auth token never reached it. The next poll will connect again and try once more.",
        address,
    )


def _explain_refused_read(address: str, state: int | None) -> None:
    """Say why the machine refused a protected read, given its pairing state."""
    if state in CMID_TYPE_UNPAIRED:
        _LOGGER.warning(
            "%s never accepted an auth token (CMID_TYPE=%s) and so refuses to answer. This is not a machine paired to somebody else, it is a pairing that did not complete, and a factory reset will not change it. Leave the machine powered on and within range of the Bluetooth adapter or proxy and let the integration keep trying. If it never gets past this, please report it with a debug log.",
            address,
            _describe_cmid_type(state),
        )
        return
    if state is None:
        _LOGGER.warning(
            "%s refuses to answer and would not say whether it holds an auth token. Check that the machine is powered on and in range, then look for the onboard status line in a debug log.",
            address,
        )
        return
    # There is no way back from here over BLE. A machine only stores a token
    # while it holds none, so it acknowledges the write above, keeps the one it
    # has and refuses every protected read. Re-onboarding it was tried until
    # v0.3.3 and never once worked, on any machine. The Nespresso app has no
    # command for it either and tells the user to factory reset.
    _LOGGER.warning(
        "%s is onboarded with a different auth token (CMID_TYPE=%s) and refuses to answer. Factory reset the machine to clear the stored token, then add the integration again leaving the auth token field empty. Note that the token this integration generates lives in the config entry, so deleting the entry loses it and costs another factory reset.",
        address,
        _describe_cmid_type(state),
    )


async def _onboard(
    client: BleakClient,
    uuids: dict[str, str],
    auth_bytes: bytes,
    address: str,
    family: MachineFamily,
    state: int | None,
    send_tx_level: bool = True,
) -> int | None:
    """Give the machine our auth token and wait until it accepts it.

    Matches VertuoNextMachine.setPairingKey in the APK: run the write and its
    poll, and repeat the whole thing on failure. Returns the pairing key state
    the machine last reported, so the caller can tell a token that took from
    one that did not.

    The caller must only reach here with the machine unpaired, which is the
    only condition in which it stores a token. That guarantee is what lets a
    paired state coming back out of here be read as proof that our write took,
    rather than as proof that somebody else's token is still there.
    """
    _LOGGER.info("Onboarding %s (%s) with new auth key", address, family.value)

    for attempt in range(1, ONBOARD_ATTEMPTS + 1):
        state, tx_acknowledged = await _onboard_once(
            client, uuids, auth_bytes, address, state, send_tx_level
        )
        if not client.is_connected:
            # A machine that drops the link mid onboarding never saw the token,
            # so the state cannot have moved and retrying on this connection is
            # pointless: bleak has no services left and every call would come
            # back "characteristic not found".
            _report_lost_link(address, tx_acknowledged)
            return state
        if state is None:
            _LOGGER.debug("Onboarding %s: machine stopped answering", address)
            return None
        if state not in CMID_TYPE_UNPAIRED:
            _LOGGER.info(
                "Onboarded %s on attempt %d, CMID_TYPE is %s",
                address,
                attempt,
                _describe_cmid_type(state),
            )
            return state
        _LOGGER.debug(
            "Onboarding %s attempt %d of %d left CMID_TYPE at %s",
            address,
            attempt,
            ONBOARD_ATTEMPTS,
            _describe_cmid_type(state),
        )
        if attempt < ONBOARD_ATTEMPTS:
            await asyncio.sleep(ONBOARD_RETRY_DELAY)

    _LOGGER.warning(
        "Onboarding %s did not take after %d attempts, CMID_TYPE is still %s",
        address,
        ONBOARD_ATTEMPTS,
        _describe_cmid_type(state),
    )
    return state


async def _onboard_once(
    client: BleakClient,
    uuids: dict[str, str],
    auth_bytes: bytes,
    address: str,
    state: int | None,
    send_tx_level: bool = True,
) -> tuple[int | None, bool]:
    """Write the auth token once and read back what the machine makes of it.

    Also reports whether the TX level request was acknowledged, because a link
    that dies right after one died for a knowable reason.
    """
    tx_acknowledged = False
    # Only a machine that already holds a final token skips the TX level
    # request. The APK sends it for every other state, and abandons the attempt
    # when the write fails rather than writing a token the machine will ignore.
    #
    # With a response, because that is the only kind of write these
    # characteristics accept: they carry the write property and not
    # write-without-response, and AbstractCharacteristicHelper.writeToMachine
    # in the APK never sets a write type and then blocks on the write callback,
    # so every write the app makes is a request. Sending a command instead was
    # a spec violation that no error could report, since a command is answered
    # by nothing at all.
    #
    # Abandoning the attempt here is not the end of it. The caller writes the
    # CMID once more when onboarding gives up, so a machine that refuses this
    # request still gets its token, exactly as it did before.
    if send_tx_level and state != CMID_TYPE_FINAL:
        try:
            await _write(client, uuids["pair"], bytes([1]), response=True)
            tx_acknowledged = True
            _LOGGER.debug("TX level write acknowledged")
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("TX level write failed for %s: %s", address, err)
            return state, False

    try:
        await _write(client, uuids["auth"], auth_bytes, response=True)
        _LOGGER.debug("Onboarding CMID write sent")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Onboarding CMID write failed for %s: %s", address, err)
        return state, tx_acknowledged

    # The write is acknowledged long before the machine decides what to do
    # with it, so read the state back until it settles on something other than
    # unpaired, or the budget runs out.
    state = await _read_cmid_type(client, uuids["onboard"], address)
    for _ in range(ONBOARD_POLL_ATTEMPTS):
        if state is None or state not in CMID_TYPE_UNPAIRED:
            break
        await asyncio.sleep(ONBOARD_POLL_INTERVAL)
        state = await _read_cmid_type(client, uuids["onboard"], address)
    return state, tx_acknowledged


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
