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


"""Unit tests for auth key generation and for reading a typed key.

The key is written to the machine unchanged, so its shape has to match what
the Nespresso Smart APK v1.2.5 produces in PairingUtils.getBufferFromByteArray.
"""

import random
import sys
from unittest.mock import MagicMock

# Stub Home Assistant and BLE before any nespresso imports
sys.modules.setdefault("homeassistant", MagicMock())
sys.modules.setdefault("homeassistant.components", MagicMock())
sys.modules.setdefault("homeassistant.components.bluetooth", MagicMock())
sys.modules.setdefault("homeassistant.components.sensor", MagicMock())
sys.modules.setdefault("homeassistant.components.binary_sensor", MagicMock())
sys.modules.setdefault("homeassistant.config_entries", MagicMock())
sys.modules.setdefault("homeassistant.const", MagicMock())
sys.modules.setdefault("homeassistant.core", MagicMock())
sys.modules.setdefault("homeassistant.helpers", MagicMock())
sys.modules.setdefault("homeassistant.helpers.device_registry", MagicMock())
sys.modules.setdefault("homeassistant.helpers.entity_platform", MagicMock())
sys.modules.setdefault("homeassistant.helpers.update_coordinator", MagicMock())
sys.modules.setdefault("homeassistant.helpers.storage", MagicMock())
sys.modules.setdefault("homeassistant.data_entry_flow", MagicMock())
sys.modules.setdefault("bleak", MagicMock())
sys.modules.setdefault("bleak_retry_connector", MagicMock())

from custom_components.nespresso.ble.protocol import (
    CMID_MARKER_NIBBLE,
    generate_auth_key,
    normalize_auth_key,
)


def apk_derive(pairing_key: str) -> str:
    """Derive the CMID the way the APK does, for the tests to compare against.

    A transcription of PairingUtils.prepareHashForPairing followed by
    getBufferFromByteArray, kept in its original byte-shifting form so the
    slice in normalize_auth_key has something independent to agree with.
    """
    raw = bytes.fromhex((pairing_key + "0")[:16])
    out = bytearray(8)
    out[0] = ((raw[0] & 0xF0) >> 4) | 0x80
    for i in range(1, 8):
        out[i] = ((raw[i - 1] & 0x0F) << 4) | ((raw[i] & 0xF0) >> 4)
    return out.hex()


class TestGenerateAuthKey:
    def test_length_and_hex(self) -> None:
        for _ in range(50):
            key = generate_auth_key()
            assert len(key) == 16
            assert len(bytes.fromhex(key)) == 8

    def test_carries_the_marker_nibble(self) -> None:
        """Every CMID the app writes starts 0x8n.

        PairingUtils.getBufferFromByteArray shifts the pairing key right by one
        nibble and ORs 0x80 into the first byte, so the top nibble is always 8.
        A Vertuo Creatista given a key without it recorded the write as
        CMID_TYPE 0x03 UNDEFINED and refused every protected read afterwards.
        """
        assert CMID_MARKER_NIBBLE == "8"
        for _ in range(50):
            key = generate_auth_key()
            assert key[0] == "8"
            assert bytes.fromhex(key)[0] >> 4 == 8

    def test_the_rest_varies(self) -> None:
        """Only the marker is fixed, the remaining 60 bits are random."""
        keys = {generate_auth_key() for _ in range(50)}
        assert len(keys) == 50
        assert len({k[1:] for k in keys}) == 50


class TestNormalizeAuthKey:
    def test_reads_a_pairing_key_from_the_account(self) -> None:
        """32 hex characters is the key the Nespresso account holds.

        This one is the placeholder from the protocol notes, whose derived
        value the account stores as `secret`, ihssPU5fYHE= in base64.
        """
        assert (
            normalize_auth_key("a1b2c3d4e5f60718293a4b5c6d7e8f90") == "8a1b2c3d4e5f6071"
        )

    def test_agrees_with_the_apk(self) -> None:
        """The slice and the byte shift are the same function."""
        rng = random.Random(0)
        for _ in range(200):
            pairing_key = f"{rng.getrandbits(128):032x}"
            assert normalize_auth_key(pairing_key) == apk_derive(pairing_key)

    def test_keeps_a_captured_token(self) -> None:
        """16 hex characters is a CMID already, nothing to derive."""
        assert normalize_auth_key("8a1b2c3d4e5f6071") == "8a1b2c3d4e5f6071"

    def test_tolerates_how_it_was_copied(self) -> None:
        assert normalize_auth_key("  8A1B2C3D4E5F6071 ") == "8a1b2c3d4e5f6071"
        assert normalize_auth_key("8a:1b:2c:3d:4e:5f:60:71") == "8a1b2c3d4e5f6071"

    def test_rejects_everything_else(self) -> None:
        """Better said at the form than raised by unhexlify on every poll."""
        for text in (
            "",
            "   ",
            "8a1b2c3d4e5f607",
            "8a1b2c3d4e5f60712",
            "a1b2c3d4e5f60718293a4b5c6d7e8f9",
            "a1b2c3d4e5f60718293a4b5c6d7e8f901",
            "8a1b2c3d4e5f607g",
            "not a key at all",
        ):
            assert normalize_auth_key(text) is None

    def test_generated_keys_survive_a_round_trip(self) -> None:
        for _ in range(50):
            key = generate_auth_key()
            assert normalize_auth_key(key) == key
