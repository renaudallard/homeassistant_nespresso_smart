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

"""Unit tests for the device triggers an update sets off.

The trigger types are the ones device_trigger.py offers. Two of them are flags
rather than states, and for a long time nothing fired them.
"""

from custom_components.nespresso.ble.parsing import (
    parse_barista_status,
    parse_vmini_status,
)
from custom_components.nespresso.const import EXPERT_STATE_NAMES, MachineFamily
from custom_components.nespresso.device_trigger import (
    EXPERT_NEVER_RAISED,
    NEVER_RAISED,
    TRIGGER_TYPES,
)
from custom_components.nespresso.models import NespressoMachineData, machine_triggers


def data(state: str = "ready", **flags: bool | None) -> NespressoMachineData:
    return NespressoMachineData(
        machine_state=state,
        error_present=False,
        firmware_version=None,
        hardware_version=None,
        serial_number=None,
        **flags,
    )


class TestStates:
    def test_entering_a_state(self) -> None:
        assert machine_triggers(data("heating"), data("ready")) == ["ready"]
        assert machine_triggers(data("ready"), data("standby")) == ["standby"]
        assert machine_triggers(data("ready"), data("error")) == ["error_occurred"]
        assert machine_triggers(data("ready"), data("brewing")) == ["brewing_started"]

    def test_leaving_brewing(self) -> None:
        """A brew ends into ready, so both fire, finished first."""
        assert machine_triggers(data("brewing"), data("ready")) == [
            "brewing_finished",
            "ready",
        ]

    def test_a_state_with_no_trigger(self) -> None:
        assert machine_triggers(data("ready"), data("capsule_reading")) == []

    def test_no_change_fires_nothing(self) -> None:
        assert machine_triggers(data("brewing"), data("brewing")) == []

    def test_a_vertuo_up_brew_is_one_brew(self) -> None:
        """Its phases change under "brew/", which starts and ends once."""
        assert machine_triggers(data("ready"), data("brew/black reading")) == [
            "brewing_started"
        ]
        assert (
            machine_triggers(data("brew/running"), data("brew/waiting for top up"))
            == []
        )
        assert machine_triggers(data("brew/top up"), data("ready")) == [
            "brewing_finished",
            "ready",
        ]


class TestFlags:
    def test_a_raised_flag_fires(self) -> None:
        assert machine_triggers(
            data(descaling_needed=False), data(descaling_needed=True)
        ) == ["descaling_needed"]
        assert machine_triggers(
            data(water_tank_empty=False), data(water_tank_empty=True)
        ) == ["water_tank_empty"]

    def test_a_flag_that_stays_up_fires_once(self) -> None:
        assert (
            machine_triggers(data(water_tank_empty=True), data(water_tank_empty=True))
            == []
        )

    def test_a_cleared_flag_is_silent(self) -> None:
        assert (
            machine_triggers(data(descaling_needed=True), data(descaling_needed=False))
            == []
        )

    def test_a_family_without_the_flag_never_fires(self) -> None:
        """A family whose parser never sets the flags leaves them at None."""
        assert machine_triggers(data("standby"), data("ready")) == ["ready"]

    def test_flag_and_state_in_the_same_update(self) -> None:
        """The advertisement can carry both in one payload."""
        assert machine_triggers(
            data("ready", water_tank_empty=False),
            data("tank_empty", water_tank_empty=True),
        ) == ["water_tank_empty"]


def test_every_offered_trigger_can_fire() -> None:
    """Each trigger device_trigger.py offers has a transition that fires it."""
    seen: set[str] = set()
    seen |= set(machine_triggers(data("ready"), data("brewing")))
    seen |= set(machine_triggers(data("brewing"), data("standby")))
    seen |= set(machine_triggers(data("standby"), data("ready")))
    seen |= set(machine_triggers(data("ready"), data("error")))
    seen |= set(
        machine_triggers(
            data(descaling_needed=False, water_tank_empty=False),
            data(descaling_needed=True, water_tank_empty=True),
        )
    )
    assert seen == set(TRIGGER_TYPES)


class TestTriggersLeftOut:
    """What device_trigger.py hides per machine must really never fire there.

    Should a parser start setting one of these, its trigger has to come back,
    so these fail first.
    """

    def test_barista_sets_neither_flag(self) -> None:
        status = parse_barista_status(bytes(4))
        for flag in NEVER_RAISED[MachineFamily.BARISTA]:
            assert flag not in status

    def test_vertuo_up_sets_none_it_hides(self) -> None:
        status = parse_vmini_status(
            "machineStatus,str;descalingAlert,bool;waterHardness,int",
            "ready,1,3",
        )
        for flag in NEVER_RAISED[MachineFamily.VMINI]:
            assert flag not in status
        assert "descaling_needed" not in NEVER_RAISED[MachineFamily.VMINI]

    def test_expert_has_no_state_it_hides(self) -> None:
        assert not EXPERT_NEVER_RAISED & set(EXPERT_STATE_NAMES.values())
