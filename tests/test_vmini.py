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

"""Unit tests for the VMini parsers.

The values are the ones a Vertuo Up on firmware 4.5.3 returned (PR 18).
"""

import json

from custom_components.nespresso.ble.parsing import (
    parse_vmini_asset_versions,
    parse_vmini_fota_status,
    parse_vmini_shadow,
    parse_vmini_status,
)
from custom_components.nespresso.ble.protocol import _decode_ble_string

ASSETS = (
    "fmw-main,4.5.3,1.1.0;recipe,4.5.0,1.1.0;hmi,1.2.2,1.0.0;"
    "fmw-connectivity,3.18.0,2.0.0"
)
SCHEMA = (
    "machineStatus,str;descalingAlert,bool;lastCoffeeFamilyID,int;"
    "volumeCustomization,str;temperatureCustomization,str;waterHardness,int;"
    "errorCode,str;firstCoffee,bool;firstRinsing,bool;recipeTag,str;"
    "customizationType,str"
)
DATA = (
    "ready,0,4,25;40;80;150;230;414;630;530;740;355;830,"
    "0;0;0;0;0;0;0;0;0;0;0,4,no error,1,0,unspecified,vol and temp"
)


class TestAssetVersions:
    def test_names_each_asset(self) -> None:
        assert parse_vmini_asset_versions(ASSETS) == {
            "fmw-main": "4.5.3",
            "recipe": "4.5.0",
            "hmi": "1.2.2",
            "fmw-connectivity": "3.18.0",
        }

    def test_nothing_read(self) -> None:
        assert parse_vmini_asset_versions(None) == {}
        assert parse_vmini_asset_versions("") == {}


class TestShadow:
    def test_lists_keep_their_semicolons(self) -> None:
        shadow = parse_vmini_shadow(SCHEMA, DATA)
        assert shadow["machineStatus"] == "ready"
        assert shadow["volumeCustomization"] == (
            "25;40;80;150;230;414;630;530;740;355;830"
        )
        assert shadow["customizationType"] == "vol and temp"
        assert len(shadow) == 11

    def test_needs_both_halves(self) -> None:
        assert parse_vmini_shadow(None, DATA) == {}
        assert parse_vmini_shadow(SCHEMA, None) == {}


class TestStatus:
    def test_idle_machine(self) -> None:
        status = parse_vmini_status(SCHEMA, DATA)
        assert status["machine_state"] == "ready"
        assert status["error_present"] is False
        assert status["error_code_text"] is None
        assert status["descaling_needed"] is False
        assert status["water_hardness"] == 4
        assert json.loads(str(status["shadow_data"]))["recipeTag"] == "unspecified"

    def test_error_and_descaling(self) -> None:
        data = DATA.replace(",0,4,", ",1,4,", 1).replace("no error", "E23 ")
        status = parse_vmini_status(SCHEMA, data)
        assert status["error_present"] is True
        assert status["error_code_text"] == "E23"
        assert status["descaling_needed"] is True

    def test_bytes_after_the_terminator(self) -> None:
        """A Vertuo Up returned "vol and temp\\x00 temp\\x00temp" and NULs.

        A notification has to decode to the same fields as the poll, which
        reads the value through the same helper.
        """
        raw = DATA.encode() + b"\x00 temp\x00temp" + b"\x00" * 20
        assert parse_vmini_status(SCHEMA, _decode_ble_string(raw)) == (
            parse_vmini_status(SCHEMA, DATA)
        )

    def test_no_schema_yet(self) -> None:
        """A notification before the first poll has nothing to zip against."""
        assert parse_vmini_status(None, DATA) == {}


class TestFotaStatus:
    def test_idle_as_read_on_hardware(self) -> None:
        assert parse_vmini_fota_status(bytes.fromhex("000000")) == {
            "fota_status": "no_update",
            "fota_progress": 0,
        }

    def test_progress_is_the_third_byte(self) -> None:
        """CharacFotaStatus reads one byte per field, progress at offset 2."""
        result = parse_vmini_fota_status(bytes([2, 1, 42]))
        assert result["fota_status"] == "downloading"
        assert result["fota_progress"] == 42
