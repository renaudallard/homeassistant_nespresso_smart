"""What a poll reads, and which reads it can do without."""

import asyncio

import pytest

from custom_components.nespresso.ble import protocol
from custom_components.nespresso.ble.parsing import (
    parse_barista_status,
    parse_vmini_status,
)
from custom_components.nespresso.const import (
    VMINI_CHAR_FOTA_STATUS,
    VMINI_CHAR_SHADOW_DATA,
    VMINI_CHAR_SHADOW_HEADER,
)

SCHEMA = "machineStatus,str;descalingAlert,bool"


class Machine:
    """A machine answering from a table, failing on everything else."""

    address = "AA:BB:CC:DD:EE:01"
    services = ()

    def __init__(self, values: dict[str, bytes]) -> None:
        self.values = values

    async def read_gatt_char(self, char: str) -> bytearray:
        if char not in self.values:
            raise protocol.BleakError(f"no {char}")
        return bytearray(self.values[char])


def read_all(machine: Machine) -> object:
    return asyncio.run(protocol.VMiniProtocol().async_read_all(machine, lambda _: None))


class TestReadOptional:
    def test_a_missing_characteristic_is_none(self) -> None:
        assert asyncio.run(protocol._read_optional(Machine({}), "x", "x")) is None

    def test_a_present_one_is_its_value(self) -> None:
        machine = Machine({"x": b"\x01\x02"})
        assert asyncio.run(protocol._read_optional(machine, "x", "x")) == b"\x01\x02"


class TestVertuoUpReads:
    def test_reads_without_the_device_information_service(self) -> None:
        """A Vertuo Up exposes none of it, and must still set up."""
        raw = read_all(
            Machine(
                {
                    VMINI_CHAR_SHADOW_HEADER: SCHEMA.encode() + b"\x00",
                    VMINI_CHAR_SHADOW_DATA: b"ready,0\x00",
                    VMINI_CHAR_FOTA_STATUS: b"\x00\x00\x00",
                }
            )
        )
        assert raw.serial_bytes is None
        assert raw.firmware_version is None
        assert raw.shadow_data == "ready,0"
        assert raw.fota_status_bytes == b"\x00\x00\x00"

    def test_fails_without_the_shadow_data(self) -> None:
        """The state itself: a poll without it would publish unknown."""
        with pytest.raises(protocol.BleakError):
            read_all(Machine({VMINI_CHAR_SHADOW_HEADER: SCHEMA.encode()}))


class TestFlagsTheTriggersLeaveOut:
    """device_trigger.NEVER_RAISED hides these triggers on these families.

    Should a parser start setting one of the flags, its trigger has to come
    back, so this fails first.
    """

    def test_barista_sets_neither_flag(self) -> None:
        status = parse_barista_status(bytes(4))
        assert "descaling_needed" not in status
        assert "water_tank_empty" not in status

    def test_vertuo_up_has_no_water_tank(self) -> None:
        status = parse_vmini_status(
            "machineStatus,str;descalingAlert,bool;waterHardness,int",
            "ready,1,3",
        )
        assert status["descaling_needed"] is True
        assert "water_tank_empty" not in status


def test_no_expert_state_is_standby() -> None:
    """device_trigger.EXPERT_NEVER_RAISED leaves standby out on an Expert."""
    from custom_components.nespresso.const import EXPERT_STATE_NAMES

    assert "standby" not in EXPERT_STATE_NAMES.values()
