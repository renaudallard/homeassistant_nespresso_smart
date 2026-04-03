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

"""Byte Sequence Transfer (BST) protocol for Nespresso BLE machines.

Ported from com.sdataway.ble2.BSTProtocol in the Nespresso APK.
Used for sending recipe data to Vertuo Next machines via
CHAR_COMMAND_REQ / CHAR_COMMAND_RSP.
"""

from __future__ import annotations

import asyncio
import logging
import time

from bleak import BleakClient

_LOGGER = logging.getLogger(__name__)

# BST command bytes
CMD_INIT = 0x01
CMD_NEXT = 0x02
CMD_GET = 0x04
CMD_DONE = 0x05

# BST response bytes
RSP_INIT = 0x11
RSP_NEXT = 0x12
RSP_NONE = 0x13

PACKET_SIZE = 20
PAYLOAD_SIZE = 18

# Flags
FLAG_END_SN = 0x01
FLAG_ALTERNATE = 0x02
FLAG_PADDING = 0x04


def _build_init_packet() -> bytes:
    """Build BST CMD_INIT packet."""
    buf = bytearray(PACKET_SIZE)
    buf[0] = CMD_INIT
    buf[19] = int(time.time() * 1000) % 255
    return bytes(buf)


def _build_next_packet() -> bytes:
    """Build BST CMD_NEXT packet."""
    buf = bytearray(PACKET_SIZE)
    buf[0] = CMD_NEXT
    return bytes(buf)


def _build_done_packet() -> bytes:
    """Build BST CMD_DONE packet."""
    buf = bytearray(PACKET_SIZE)
    buf[0] = CMD_DONE
    buf[19] = int(time.time() * 1000) % 255
    return bytes(buf)


def _build_data_packets(data: bytes) -> list[bytes]:
    """Split data into BST data packets (20 bytes each, 18 bytes payload)."""
    packets: list[bytes] = []
    offset = 0
    sn = 0

    while offset < len(data):
        buf = bytearray(PACKET_SIZE)
        buf[0] = sn & 0xFF
        remaining = len(data) - offset
        chunk = min(remaining, PAYLOAD_SIZE)
        buf[2 : 2 + chunk] = data[offset : offset + chunk]

        # Padding for last packet
        if chunk < PAYLOAD_SIZE:
            pad = PAYLOAD_SIZE - chunk
            buf[1] = FLAG_PADDING
            for i in range(chunk + 2, PACKET_SIZE):
                buf[i] = pad

        packets.append(bytes(buf))
        offset += chunk
        sn += 1

    return packets


async def bst_send(
    client: BleakClient,
    cmd_uuid: str,
    rsp_uuid: str,
    data: bytes,
    timeout: float = 10.0,
) -> bool:
    """Send data to the machine via BST protocol.

    Args:
        client: Connected BleakClient
        cmd_uuid: CHAR_COMMAND_REQ UUID
        rsp_uuid: CHAR_COMMAND_RSP UUID
        data: Raw bytes to send
        timeout: Seconds to wait for each response

    Returns:
        True if the transfer completed successfully.
    """
    response: bytearray | None = None
    response_event = asyncio.Event()

    def on_notify(_sender: object, rsp_data: bytearray) -> None:
        nonlocal response
        response = rsp_data
        _LOGGER.debug("BST response: %s", rsp_data.hex())
        response_event.set()

    await client.start_notify(rsp_uuid, on_notify)

    try:
        # Step 1: CMD_INIT
        response = None
        response_event.clear()
        await client.write_gatt_char(cmd_uuid, _build_init_packet(), response=True)
        _LOGGER.debug("BST: sent CMD_INIT")

        try:
            await asyncio.wait_for(response_event.wait(), timeout)
        except TimeoutError:
            _LOGGER.error("BST: timeout waiting for RSP_INIT")
            return False

        if response is None or response[0] != RSP_INIT:
            _LOGGER.error(
                "BST: expected RSP_INIT, got %s", response.hex() if response else "None"
            )
            return False

        _LOGGER.debug("BST: got RSP_INIT")

        # Step 2: CMD_NEXT
        response = None
        response_event.clear()
        await client.write_gatt_char(cmd_uuid, _build_next_packet(), response=True)
        _LOGGER.debug("BST: sent CMD_NEXT")

        try:
            await asyncio.wait_for(response_event.wait(), timeout)
        except TimeoutError:
            _LOGGER.error("BST: timeout waiting for RSP_NEXT")
            return False

        if response is None or response[0] != RSP_NEXT:
            _LOGGER.error(
                "BST: expected RSP_NEXT, got %s", response.hex() if response else "None"
            )
            return False

        _LOGGER.debug("BST: got RSP_NEXT")

        # Step 3: Send data packets
        packets = _build_data_packets(data)
        for i, pkt in enumerate(packets):
            await client.write_gatt_char(cmd_uuid, pkt, response=True)
            _LOGGER.debug("BST: sent data packet %d/%d", i + 1, len(packets))

        # Step 4: CMD_DONE
        response = None
        response_event.clear()
        await client.write_gatt_char(cmd_uuid, _build_done_packet(), response=True)
        _LOGGER.debug("BST: sent CMD_DONE")

        # Wait briefly for any final response
        try:
            await asyncio.wait_for(response_event.wait(), 3.0)
            _LOGGER.debug(
                "BST: final response: %s", response.hex() if response else "None"
            )
        except TimeoutError:
            _LOGGER.debug("BST: no final response (OK)")

        return True

    finally:
        await client.stop_notify(rsp_uuid)


def encode_recipe_data(recipe_data_str: str) -> bytes:
    """Encode a slash-separated recipeData string to bytes.

    Each value is encoded as a 2-byte big-endian short.
    """
    values = [int(v) for v in recipe_data_str.split("/")]
    buf = bytearray()
    for v in values:
        buf.append((v >> 8) & 0xFF)
        buf.append(v & 0xFF)
    return bytes(buf)
