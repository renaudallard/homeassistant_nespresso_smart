"""BLE protocol implementations for Nespresso machine families.

Each protocol class knows which GATT characteristics to read for its
machine family. All I/O happens here; parsing is delegated to parsing.py.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from bleak import BleakClient

from ..const import (
    BARISTA_CHAR_INFO,
    BARISTA_CHAR_SERIAL,
    BARISTA_CHAR_STATUS,
    VMINI_CHAR_FW_REV,
    VMINI_CHAR_MANUFACTURER,
    VMINI_CHAR_MODEL,
    VMINI_CHAR_PAIRING,
    VMINI_CHAR_SERIAL,
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


class AbstractNespressoProtocol(ABC):
    """Base class for BLE protocol implementations."""

    @abstractmethod
    async def async_read_all(self, client: BleakClient) -> RawMachineData:
        """Read all relevant characteristics in a single session."""


class BaristaProtocol(AbstractNespressoProtocol):
    """BLE protocol for Barista (Original Line) machines."""

    async def async_read_all(self, client: BleakClient) -> RawMachineData:
        status = await client.read_gatt_char(BARISTA_CHAR_STATUS)
        info = await client.read_gatt_char(BARISTA_CHAR_INFO)
        serial = await client.read_gatt_char(BARISTA_CHAR_SERIAL)
        _LOGGER.debug(
            "Barista raw: status=%s info=%s serial=%s",
            status.hex(),
            info.hex(),
            serial.hex(),
        )
        return RawMachineData(
            status_bytes=bytes(status),
            info_bytes=bytes(info),
            serial_bytes=bytes(serial),
        )


class VertuoNextProtocol(AbstractNespressoProtocol):
    """BLE protocol for Vertuo Next (Venus Line) machines."""

    async def async_read_all(self, client: BleakClient) -> RawMachineData:
        status = await client.read_gatt_char(VERTUO_CHAR_STATUS)
        info = await client.read_gatt_char(VERTUO_CHAR_INFO)
        serial = await client.read_gatt_char(VERTUO_CHAR_SERIAL)
        settings = await client.read_gatt_char(VERTUO_CHAR_USER_SETTINGS)
        _LOGGER.debug(
            "VertuoNext raw: status=%s info=%s serial=%s settings=%s",
            status.hex(),
            info.hex(),
            serial.hex(),
            settings.hex(),
        )
        return RawMachineData(
            status_bytes=bytes(status),
            info_bytes=bytes(info),
            serial_bytes=bytes(serial),
            user_settings_bytes=bytes(settings),
        )


class VMiniProtocol(AbstractNespressoProtocol):
    """BLE protocol for VMini (Vertuo Mini) machines."""

    async def async_read_all(self, client: BleakClient) -> RawMachineData:
        serial = await client.read_gatt_char(VMINI_CHAR_SERIAL)
        pairing = await client.read_gatt_char(VMINI_CHAR_PAIRING)
        fw = await client.read_gatt_char(VMINI_CHAR_FW_REV)
        model = await client.read_gatt_char(VMINI_CHAR_MODEL)
        manufacturer = await client.read_gatt_char(VMINI_CHAR_MANUFACTURER)
        _LOGGER.debug(
            "VMini raw: serial=%s pairing=%s fw=%s model=%s",
            serial.hex(),
            pairing.hex(),
            fw.hex(),
            model.hex(),
        )
        return RawMachineData(
            serial_bytes=bytes(serial),
            pairing_byte=pairing[0] if pairing else None,
            firmware_version=_decode_ble_string(bytes(fw)),
            model_number=_decode_ble_string(bytes(model)),
            manufacturer=_decode_ble_string(bytes(manufacturer)),
        )


_PROTOCOL_MAP: dict[MachineFamily, type[AbstractNespressoProtocol]] = {
    MachineFamily.BARISTA: BaristaProtocol,
    MachineFamily.VERTUO_NEXT: VertuoNextProtocol,
    MachineFamily.VMINI: VMiniProtocol,
}


def get_protocol(family: MachineFamily) -> AbstractNespressoProtocol:
    """Return the protocol instance for a given machine family."""
    return _PROTOCOL_MAP[family]()
