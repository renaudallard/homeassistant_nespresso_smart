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

"""Unit tests for raising link security before the first read.

A Bluetooth proxy clears its paired flag on every connection, so the link has to
be encrypted again each time. Learning that from a refused read costs a WARNING
from the ESPHome integration on every poll, which is what these cover.
"""

import asyncio

import pytest

from custom_components.nespresso.ble import protocol


class FakeClient:
    """Enough of a BleakClient for the link handling."""

    def __init__(self, address: str = "AA:BB:CC:DD:EE:FF") -> None:
        self.address = address
        self.pair_calls = 0

    async def pair(self) -> bool:
        self.pair_calls += 1
        return True


@pytest.fixture(autouse=True)
def _clean_state():
    protocol._NEEDS_ENCRYPTION.clear()
    protocol._ELEVATED.clear()
    yield
    protocol._NEEDS_ENCRYPTION.clear()
    protocol._ELEVATED.clear()


class TestPrepareLink:
    def test_unknown_machine_is_left_alone(self) -> None:
        """Nothing is known about it yet, so do not go pairing on spec.

        This is what keeps the proactive path off a local adapter, where
        client.pair() waits on an agent nobody registers.
        """
        client = FakeClient()
        asyncio.run(protocol._prepare_link(client))
        assert client.pair_calls == 0

    def test_known_machine_is_encrypted_up_front(self) -> None:
        client = FakeClient()
        protocol._NEEDS_ENCRYPTION.add(client.address)
        asyncio.run(protocol._prepare_link(client))
        assert client.pair_calls == 1

    def test_not_repeated_on_the_same_client(self) -> None:
        """One pairing request per connection, however many reads follow."""
        client = FakeClient()
        protocol._NEEDS_ENCRYPTION.add(client.address)
        asyncio.run(protocol._prepare_link(client))
        asyncio.run(protocol._prepare_link(client))
        assert client.pair_calls == 1

    def test_a_new_connection_asks_again(self) -> None:
        """The proxy forgets between connections, so each one has to ask."""
        first = FakeClient()
        protocol._NEEDS_ENCRYPTION.add(first.address)
        asyncio.run(protocol._prepare_link(first))
        second = FakeClient()
        asyncio.run(protocol._prepare_link(second))
        assert first.pair_calls == 1
        assert second.pair_calls == 1


class TestElevateRecordsTheAddress:
    def _err(self, code: int) -> Exception:
        inner = type("Inner", (), {"error": code})()
        err = protocol.BleakError("refused")
        err.error = inner
        return err

    def test_att_15_is_remembered_for_next_time(self) -> None:
        client = FakeClient()
        assert asyncio.run(protocol._elevate(client, self._err(15))) is True
        assert client.address in protocol._NEEDS_ENCRYPTION

    def test_att_5_is_remembered_too(self) -> None:
        client = FakeClient()
        assert asyncio.run(protocol._elevate(client, self._err(5))) is True
        assert client.address in protocol._NEEDS_ENCRYPTION

    def test_an_unrelated_error_is_not(self) -> None:
        """ATT 2 is a wrong token, not an unencrypted link."""
        client = FakeClient()
        assert asyncio.run(protocol._elevate(client, self._err(2))) is False
        assert client.address not in protocol._NEEDS_ENCRYPTION
        assert client.pair_calls == 0
