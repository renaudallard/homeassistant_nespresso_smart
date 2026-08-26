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

"""Unit tests for the CCommandReq frame.

A Vertuo Next tolerates a short write, so a 10-byte packet capture passed for
the whole command until a Creatista acknowledged one and did nothing. The
width is checked against CharacCommandReq.setValue, which allocates 0x13.
"""

import pytest

from custom_components.nespresso.ble.protocol import (
    COMMAND_DATA_LEN,
    build_command_frame,
)
from custom_components.nespresso.const import COMMAND_FRAME_LEN


class TestBuildCommandFrame:
    def test_frame_is_always_nineteen_bytes(self) -> None:
        """0x13 in the APK, and the same width comes back on the response."""
        assert COMMAND_FRAME_LEN == 19
        assert len(build_command_frame(3, 5, b"\x04")) == 19
        assert len(build_command_frame(3, 7, b"")) == 19

    def test_header_and_payload_placement(self) -> None:
        frame = build_command_frame(3, 5, bytes([4, 0, 0, 0, 0, 2, 1]))
        assert frame[0] == 3  # cmdID
        assert frame[1] == 5  # subCmdID
        assert frame[2] == 7  # dataControl carries the length
        assert frame[3:10] == bytes([4, 0, 0, 0, 0, 2, 1])
        assert frame[10:] == b"\x00" * 9  # padded to the fixed data array

    def test_brew_frame_matches_the_bytes_that_worked_on_a_vertuo_next(self) -> None:
        """The old 10-byte command, now padded rather than changed.

        Espresso at medium: type 1, temp 0. The first ten bytes must be
        byte-identical to what shipped before, or this is a new command
        rather than the same one correctly sized.
        """
        frame = build_command_frame(3, 5, bytes([4, 0, 0, 0, 0, 0, 1]))
        assert frame[:10].hex() == "03050704000000000001"

    def test_empty_payload_sets_a_zero_length(self) -> None:
        frame = build_command_frame(3, 7, b"")
        assert frame[:3] == bytes([3, 7, 0])
        assert frame[3:] == b"\x00" * 16

    def test_full_width_payload_fits(self) -> None:
        frame = build_command_frame(1, 2, bytes(range(COMMAND_DATA_LEN)))
        assert COMMAND_DATA_LEN == 16
        assert frame[2] == 16
        assert frame[3:] == bytes(range(16))

    def test_over_long_payload_is_refused(self) -> None:
        with pytest.raises(ValueError):
            build_command_frame(3, 5, bytes(COMMAND_DATA_LEN + 1))
