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

"""Barista recipe management protocol.

Implements recipe CRUD operations via CHAR_RECIPE_COMMAND (write) and
CHAR_RECIPE_RESPONSE (read/notify). Binary recipe format with CRC-16
validation, verified against WhiteRecipe.java and RecipeCommand.java.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import IntEnum

from bleak import BleakClient

from ..const import (
    BARISTA_CHAR_RECIPE_COMMAND,
    BARISTA_CHAR_RECIPE_INFO,
    BARISTA_CHAR_RECIPE_RESPONSE,
)

_LOGGER = logging.getLogger(__name__)

CRC16_POLY = 0x1021


class RecipeCommand(IntEnum):
    """Recipe command IDs from RecipeCommand.RecipeCommands."""

    INSERT = 0
    APPEND = 1
    REPLACE = 2
    DELETE = 3
    MOVE = 4
    SET_TEMPORARY = 5
    CLEAR = 6
    GET = 7
    COUNT = 8
    GET_CRCS = 9
    GET_ID = 10


class RecipeResponseStatus(IntEnum):
    """Response status from WhiteRecipeResponseType."""

    SUCCESS = 32
    FAILED = 33
    INVALID_STATE = 34
    OUT_OF_RANGE = 35
    WRONG_CRC = 36
    FORMAT_ERROR = 37
    NOT_SUPPORTED = 38
    MEMORY_FULL = 39


@dataclass(frozen=True, slots=True)
class RecipePhase:
    """A single recipe phase. Serializes to 6 bytes MSB."""

    motor_speed: int  # 300-4000 RPM
    acceleration: int  # 50-2000
    temperature: int  # 0-70 C
    duration_seconds: int  # 0-240 s

    def to_bytes(self) -> bytes:
        """Serialize to 6 bytes MSB."""
        return (
            self.motor_speed.to_bytes(2, "big")
            + self.acceleration.to_bytes(2, "big")
            + bytes([self.temperature & 0xFF, self.duration_seconds & 0xFF])
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> RecipePhase:
        """Deserialize from 6 bytes MSB."""
        return cls(
            motor_speed=int.from_bytes(data[0:2], "big"),
            acceleration=int.from_bytes(data[2:4], "big"),
            temperature=data[4],
            duration_seconds=data[5],
        )


@dataclass(frozen=True, slots=True)
class RecipeInfo:
    """Machine recipe slot information from CHAR_RECIPE_INFO."""

    max_recipes: int
    nb_default_recipes: int
    max_recipe_size: int
    max_recipe_steps: int
    max_recipe_phases: int
    max_recipe_name_length: int
    max_step_name_length: int


def crc16(data: bytes) -> int:
    """CRC-16 with polynomial 0x1021, matching WhiteRecipe.java."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ CRC16_POLY
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return crc


def parse_recipe_info(data: bytes) -> RecipeInfo:
    """Parse 8-byte CHAR_RECIPE_INFO."""
    if len(data) < 8:
        raise ValueError(f"Recipe info requires >= 8 bytes, got {len(data)}")
    return RecipeInfo(
        max_recipes=data[0],
        nb_default_recipes=data[1],
        max_recipe_size=int.from_bytes(data[2:4], "big"),
        max_recipe_steps=data[4],
        max_recipe_phases=data[5],
        max_recipe_name_length=data[6],
        max_step_name_length=data[7],
    )


async def read_recipe_info(client: BleakClient) -> RecipeInfo:
    """Read recipe slot information from the machine."""
    data = await client.read_gatt_char(BARISTA_CHAR_RECIPE_INFO)
    info = parse_recipe_info(bytes(data))
    _LOGGER.debug("Recipe info: %s", info)
    return info


async def send_recipe_command(
    client: BleakClient,
    command: RecipeCommand,
    data: bytes = b"",
) -> bytes:
    """Send a recipe command and wait for response.

    Writes to CHAR_RECIPE_COMMAND, then reads CHAR_RECIPE_RESPONSE.
    Returns the response data bytes.
    """
    # Build command packet: 1 byte command + 1 byte data_control + data
    data_len = len(data) & 0x1F
    payload = bytes([command & 0xFF, data_len]) + data
    payload = payload[:18]  # max 18 bytes

    _LOGGER.debug("Recipe command: cmd=%s data=%s", command.name, payload.hex())
    await client.write_gatt_char(BARISTA_CHAR_RECIPE_COMMAND, payload, response=True)

    await asyncio.sleep(0.5)

    response = await client.read_gatt_char(BARISTA_CHAR_RECIPE_RESPONSE)
    resp_bytes = bytes(response)
    _LOGGER.debug("Recipe response: %s", resp_bytes.hex())

    if len(resp_bytes) >= 3:
        status = resp_bytes[2]
        status_name = "UNKNOWN"
        try:
            status_name = RecipeResponseStatus(status).name
        except ValueError:
            pass
        _LOGGER.debug("Recipe response status: %s (%d)", status_name, status)

    return resp_bytes


async def get_recipe_count(client: BleakClient) -> int:
    """Get the number of recipes stored on the machine."""
    resp = await send_recipe_command(client, RecipeCommand.COUNT)
    if len(resp) >= 4:
        return resp[3]
    return 0
