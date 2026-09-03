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


"""Unit tests for naming the machine model.

Every Venus machine answers to the same service UUID, so the family cannot tell
a Pop from a Creatista. The platform code in the serial number and the BLE name
can, and MachineTypeKt in the APK v1.2.5 says which code is which.
"""

import sys
from dataclasses import dataclass
from unittest.mock import MagicMock

# Stub Home Assistant before any nespresso imports
sys.modules.setdefault("homeassistant", MagicMock())
sys.modules.setdefault("homeassistant.config_entries", MagicMock())
sys.modules.setdefault("homeassistant.helpers", MagicMock())
sys.modules.setdefault("homeassistant.helpers.device_registry", MagicMock())

from custom_components.nespresso.const import VERTUO_PLATFORM_NAMES
from custom_components.nespresso.entity import machine_model, platform_code


@dataclass
class FakeEntry:
    data: dict[str, str]


@dataclass
class FakeCoordinator:
    data: object | None = None


@dataclass
class FakeMachineData:
    serial_number: str | None = None
    iot_market_name: str | None = None


def resolve(
    name: str = "", serial: str = "", market: str = "", family: str = "vertuo_next"
):
    entry = FakeEntry({"family": family, "name": name, "address": "AA:BB:CC:DD:EE:FF"})
    coordinator = FakeCoordinator(FakeMachineData(serial or None, market or None))
    return platform_code(entry, coordinator), machine_model(entry, coordinator)


class TestPlatformCode:
    def test_reads_the_ble_name(self) -> None:
        """Both shapes of name seen in the wild carry the code."""
        assert resolve(name="Vertuo_CV5_78421CC0B0EE") == ("CV5", "Vertuo Creatista")
        assert resolve(name="CV2_5443B29C51B2") == ("CV2", "Vertuo Pop")

    def test_falls_back_to_the_serial(self) -> None:
        """An advertisement without a name still leaves the serial."""
        assert resolve(serial="23222CV2f2001582072") == ("CV2", "Vertuo Pop")

    def test_falls_back_to_the_market_name(self) -> None:
        assert resolve(market="VERTUO DV6 SILVER") == ("DV6", "Vertuo Pop+")

    def test_is_case_insensitive(self) -> None:
        assert resolve(name="vertuo_dv5_001122334455") == ("DV5", "Vertuo Lattissima")

    def test_names_the_family_when_nothing_says_more(self) -> None:
        """A machine that told us nothing is still a Vertuo Next as far as we know."""
        assert resolve(name="Venus_001122334455") == (None, "Vertuo Next")
        assert resolve() == (None, "Vertuo Next")

    def test_leaves_the_other_families_alone(self) -> None:
        """Their family already names them, and W10 or MD2 could match anything."""
        assert resolve(name="Barista_001122334455", family="barista") == (
            None,
            "Barista",
        )
        assert resolve(serial="19023DB3Z098612E098", family="vmini") == (
            None,
            "Vertuo Mini",
        )


class TestTable:
    def test_codes_are_three_upper_case_characters(self) -> None:
        """The lookup upper-cases what it searches, so the keys must match."""
        for code, name in VERTUO_PLATFORM_NAMES.items():
            assert len(code) == 3
            assert code == code.upper()
            assert name.startswith("Vertuo ")
