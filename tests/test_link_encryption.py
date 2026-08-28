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


def test_pair_budget_outlasts_the_transport() -> None:
    """We must not be the layer that gives up first.

    aioesphomeapi arms a single 30 second deadline for the pairing request and
    never re-arms it. Cancelling before that expires means the log gets a bare
    TimeoutError instead of the reason, which is what left an entire issue's
    worth of failures with no code attached to any of them.
    """
    assert protocol.BLE_PAIR_TIMEOUT > 30.0


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
    protocol._PAIR_FAILURES.clear()
    yield
    protocol._NEEDS_ENCRYPTION.clear()
    protocol._ELEVATED.clear()
    protocol._PAIR_FAILURES.clear()


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


class FailingClient(FakeClient):
    """A machine that will not pair, however often it is asked."""

    def __init__(self, address: str = "AA:BB:CC:DD:EE:FF", error: str = "") -> None:
        super().__init__(address)
        self.error = error or "Pairing failed due to error: 97"

    async def pair(self) -> bool:
        self.pair_calls += 1
        raise protocol.BleakError(self.error)


def _ask(address: str, error: str = "") -> FailingClient:
    """One connection's worth of asking, since each one brings a new client."""
    client = FailingClient(address, error)
    asyncio.run(protocol._pair(client))
    return client


class TestPairBackoff:
    def test_the_first_failures_are_all_attempted(self) -> None:
        """A transient refusal must not cost the machine its next few tries."""
        attempts = sum(_ask("AA:BB:CC:DD:EE:FF").pair_calls for _ in range(4))
        assert attempts == 4

    def test_it_goes_quiet_after_the_threshold(self) -> None:
        for _ in range(protocol.PAIR_QUIET_AFTER):
            _ask("AA:BB:CC:DD:EE:FF")
        assert _ask("AA:BB:CC:DD:EE:FF").pair_calls == 0

    def test_it_never_gives_up(self) -> None:
        """A machine can be reset and re-onboarded at any moment."""
        asked = [bool(_ask("AA:BB:CC:DD:EE:FF").pair_calls) for _ in range(60)]
        assert asked.count(True) > 1
        assert True in asked[protocol.PAIR_RETRY_EVERY :]

    def test_a_second_machine_is_unaffected(self) -> None:
        """The count is per address, not global."""
        for _ in range(protocol.PAIR_QUIET_AFTER + 1):
            _ask("AA:BB:CC:DD:EE:FF")
        assert _ask("11:22:33:44:55:66").pair_calls == 1

    def test_recovery_waits_for_the_next_retry_slot(self) -> None:
        """The price of backing off, stated rather than hidden.

        A machine that starts working again is not noticed until an attempt
        comes round, so up to about ten minutes pass after a factory reset
        before the integration tries it. Reloading the entry does not shorten
        that, since the count lives in this module.
        """
        for _ in range(protocol.PAIR_QUIET_AFTER):
            _ask("AA:BB:CC:DD:EE:FF")
        working = FakeClient()
        asyncio.run(protocol._pair(working))
        assert working.pair_calls == 0

    def test_success_clears_the_count(self) -> None:
        """A machine that comes back is served at full rate from then on."""
        protocol._PAIR_FAILURES["AA:BB:CC:DD:EE:FF"] = protocol.PAIR_RETRY_EVERY
        working = FakeClient()
        asyncio.run(protocol._pair(working))
        assert working.pair_calls == 1
        assert "AA:BB:CC:DD:EE:FF" not in protocol._PAIR_FAILURES
        assert _ask("AA:BB:CC:DD:EE:FF").pair_calls == 1


class TestPairErrorCode:
    def test_the_code_is_read_off_the_message(self) -> None:
        """bleak-esphome formats it into the string and nowhere else."""
        err = protocol.BleakError("Pairing failed due to error: 97")
        assert protocol._pair_error_code(err) == 97

    def test_97_is_not_a_passkey_failure(self) -> None:
        """ESP_AUTH_SMP_PASSKEY_FAIL is 78. Claiming 97 was it sent users nowhere."""
        assert "passkey" not in protocol.PAIR_ERROR_REASONS[97]
        assert "passkey" in protocol.PAIR_ERROR_REASONS[78]

    def test_a_timeout_carries_no_code(self) -> None:
        assert protocol._pair_error_code(TimeoutError()) is None


class TalkingClient(FakeClient):
    """A machine that pairs and then answers, to prove the bail is selective."""

    def __init__(self) -> None:
        super().__init__()
        self.reads = 0
        self.writes = 0

    async def read_gatt_char(self, char: str) -> bytearray:
        self.reads += 1
        return bytearray(b"\x02")  # CMID_TYPE FINAL, so no onboarding

    async def write_gatt_char(self, char: str, data: bytes, response: bool) -> None:
        self.writes += 1


class SilentClient(FailingClient):
    """A machine that never pairs and never answers, which is the real shape.

    read and write hang rather than raise, because that is what the reporter's
    proxy did: the machine simply did not answer on a plain link and there was
    no ATT error to report, so each operation burned BLE_OP_TIMEOUT.
    """

    def __init__(self) -> None:
        super().__init__()
        self.reads = 0
        self.writes = 0

    async def read_gatt_char(self, char: str) -> bytearray:
        self.reads += 1
        await asyncio.sleep(3600)
        return bytearray()

    async def write_gatt_char(self, char: str, data: bytes, response: bool) -> None:
        self.writes += 1
        await asyncio.sleep(3600)


class TestPrepareLinkVerdict:
    """_prepare_link now says whether protected reads are worth attempting."""

    def test_unknown_machine_is_worth_trying(self) -> None:
        """Nothing is known against it, so the reactive path gets its chance."""
        assert asyncio.run(protocol._prepare_link(FakeClient())) is True

    def test_a_successful_pairing_is_worth_trying(self) -> None:
        client = FakeClient()
        protocol._NEEDS_ENCRYPTION.add(client.address)
        assert asyncio.run(protocol._prepare_link(client)) is True

    def test_a_failed_pairing_is_not(self) -> None:
        client = FailingClient()
        protocol._NEEDS_ENCRYPTION.add(client.address)
        assert asyncio.run(protocol._prepare_link(client)) is False

    def test_a_backed_off_attempt_is_not_either(self) -> None:
        """Nothing asked for encryption, so the link is still plain."""
        for _ in range(protocol.PAIR_QUIET_AFTER):
            _ask("AA:BB:CC:DD:EE:FF")
        client = FailingClient()
        protocol._NEEDS_ENCRYPTION.add(client.address)
        assert asyncio.run(protocol._prepare_link(client)) is False
        assert client.pair_calls == 0


class TestNoDeadTimeAfterAFailedPairing:
    """A failed pairing must cost the pairing, and nothing after it.

    A reporter's poll ran 28 seconds against a 60 second interval. Twenty of
    those came after the pairing request had already returned its answer, spent
    on an onboard status read and a CMID write that the machine was never going
    to answer over a plain link, at BLE_OP_TIMEOUT apiece.

    It matters beyond the wasted time. When a proxy erases a stale key on a
    failed pairing it is the next connection that recovers, so how fast the
    failed one gets out of the way is the whole of the recovery latency.
    """

    def test_it_gives_up_without_touching_the_machine(self) -> None:
        client = SilentClient()
        protocol._NEEDS_ENCRYPTION.add(client.address)
        assert (
            asyncio.run(
                protocol._authenticate(
                    client, "8" + "0" * 15, protocol.MachineFamily.VERTUO_NEXT
                )
            )
            is False
        )
        assert client.pair_calls == 1
        assert client.reads == 0
        assert client.writes == 0

    def test_an_encrypted_link_is_left_alone(self) -> None:
        """The bail must not fire on a machine whose link came up fine."""
        client = TalkingClient()
        protocol._NEEDS_ENCRYPTION.add(client.address)
        assert (
            asyncio.run(
                protocol._authenticate(
                    client, "8" + "0" * 15, protocol.MachineFamily.VERTUO_NEXT
                )
            )
            is True
        )
        assert client.reads > 0
        assert client.writes > 0
