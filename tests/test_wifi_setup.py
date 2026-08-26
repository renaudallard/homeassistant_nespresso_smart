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

"""Unit tests for WiFi provisioning.

The setup frame reconfigures a real machine's network, so the layout is checked
against CharacWifiSetup.setValue in the APK byte by byte rather than by eye.
"""

import pytest

from custom_components.nespresso.ble.parsing import parse_wifi_scan_entry
from custom_components.nespresso.ble.protocol import (
    WIFI_CONNECTION_INDEX_MANUAL,
    WIFI_SETUP_FRAME_LEN,
    build_wifi_setup_frame,
)


class TestBuildWifiSetupFrame:
    def test_length_and_field_offsets(self) -> None:
        """0x77 bytes: type at 0, SSID at 1, security at 33, key at 34, index at 118."""
        frame = build_wifi_setup_frame("MyNet", "hunter2", 3, 7)
        assert len(frame) == WIFI_SETUP_FRAME_LEN == 119
        assert frame[0] == 0  # DHCP
        assert frame[1:6] == b"MyNet"
        assert frame[6:33] == b"\x00" * 27  # SSID zero padded to 32
        assert frame[33] == 3  # WPA2
        assert frame[34:41] == b"hunter2"
        assert frame[41:98] == b"\x00" * 57  # key zero padded to 64
        assert frame[118] == 7

    def test_address_block_is_zero_for_dhcp(self) -> None:
        """Bytes 98-117 are IPv4, subnet, gateway and both DNS entries."""
        frame = build_wifi_setup_frame("MyNet", "pw", 3)
        assert frame[98:118] == b"\x00" * 20

    def test_manual_index_defaults_to_255(self) -> None:
        frame = build_wifi_setup_frame("MyNet", "pw", 3)
        assert frame[118] == WIFI_CONNECTION_INDEX_MANUAL == 0xFF

    def test_open_network_has_an_empty_key_block(self) -> None:
        frame = build_wifi_setup_frame("Guest", "", 0)
        assert frame[33] == 0
        assert frame[34:98] == b"\x00" * 64

    def test_full_length_ssid_and_key_fit_exactly(self) -> None:
        frame = build_wifi_setup_frame("S" * 32, "P" * 64, 3)
        assert frame[1:33] == b"S" * 32
        assert frame[33] == 3
        assert frame[34:98] == b"P" * 64
        assert frame[118] == 0xFF

    def test_over_long_ssid_is_refused(self) -> None:
        """The APK arraycopies with no clamp, so this would corrupt the frame."""
        with pytest.raises(ValueError):
            build_wifi_setup_frame("S" * 33, "pw", 3)

    def test_empty_ssid_is_refused(self) -> None:
        with pytest.raises(ValueError):
            build_wifi_setup_frame("", "pw", 3)

    def test_over_long_key_is_refused(self) -> None:
        with pytest.raises(ValueError):
            build_wifi_setup_frame("MyNet", "P" * 65, 3)

    def test_multibyte_ssid_is_measured_in_bytes(self) -> None:
        """32 characters of 3-byte UTF-8 is 96 bytes and must not be accepted."""
        with pytest.raises(ValueError):
            build_wifi_setup_frame("\u3042" * 32, "pw", 3)
        frame = build_wifi_setup_frame("\u3042" * 10, "pw", 3)
        assert frame[1:31] == "\u3042".encode() * 10


class TestParseWifiScanEntry:
    def _entry(self, security: int, ssid: bytes, rssi: int, index: int) -> bytes:
        return (
            bytes([security])
            + ssid.ljust(32, b"\x00")
            + rssi.to_bytes(2, "big", signed=True)
            + bytes([index])
            + b"\x11\x22\x33\x44\x55\x66"
        )

    def test_a_network(self) -> None:
        result = parse_wifi_scan_entry(self._entry(3, b"MyNet", -55, 4))
        assert result == {
            "ssid": "MyNet",
            "security": "wpa2",
            "security_type": 3,
            "signal_strength": -55,
            "connection_index": 4,
        }

    def test_end_of_list_returns_none(self) -> None:
        """Security 0xFF with an empty SSID ends the list."""
        assert parse_wifi_scan_entry(self._entry(0xFF, b"", 0, 0)) is None

    def test_unknown_security_is_not_end_of_list(self) -> None:
        """0xF0 is a real network whose security the machine could not name."""
        result = parse_wifi_scan_entry(self._entry(0xF0, b"Odd", -70, 2))
        assert result is not None
        assert result["security"] == "unknown"

    def test_short_entry_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_wifi_scan_entry(b"\x00" * 35)
