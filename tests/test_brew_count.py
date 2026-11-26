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

"""Unit tests for which state changes count as a brew.

The Vertuo Up states are the ones a machine on firmware 4.5.3 reported
(PR 18). Whether it goes back to "brew/running" after a top-up is not known
yet, so that change is left out.
"""

from custom_components.nespresso.models import counts_as_brew


class TestVertuoNext:
    def test_entering_brewing(self) -> None:
        assert counts_as_brew("ready", "brewing")
        assert counts_as_brew("capsule_reading", "brewing")

    def test_staying_or_leaving(self) -> None:
        assert not counts_as_brew("brewing", "brewing")
        assert not counts_as_brew("brewing", "ready")
        assert not counts_as_brew("ready", "capsule_reading")


class TestVertuoUp:
    def test_a_pour_counts(self) -> None:
        assert counts_as_brew("brew/black reading", "brew/running")
        assert counts_as_brew("ready", "brew/running")

    def test_a_barcode_read_waits_for_the_pour(self) -> None:
        assert not counts_as_brew("ready", "brew/black reading")
        assert not counts_as_brew("brew/black reading", "ready")

    def test_a_pour_missed_between_polls(self) -> None:
        """The pause after it is the first sign of the brew."""
        assert counts_as_brew("ready", "brew/waiting for top up")

    def test_phases_of_one_brew(self) -> None:
        assert not counts_as_brew("brew/running", "brew/waiting for top up")
        assert not counts_as_brew("brew/waiting for top up", "brew/top up")
        assert not counts_as_brew("brew/top up", "ready")

    def test_other_activities(self) -> None:
        assert not counts_as_brew("ready", "descale/running")
