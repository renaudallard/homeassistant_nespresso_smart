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

"""Data models for the Nespresso Smart integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NespressoMachineData:
    """Parsed machine data returned by the coordinator."""

    # Universal fields
    machine_state: str
    error_present: bool
    firmware_version: str | None
    hardware_version: str | None
    serial_number: str | None
    bootloader_version: str | None = None
    profile_version: str | None = None
    bluetooth_version: str | None = None
    recipe_db_version: str | None = None
    connectivity_fw_version: str | None = None

    # Vertuo Next specific
    water_tank_empty: bool | None = None
    descaling_needed: bool | None = None
    cleaning_needed: bool | None = None
    capsule_container_full: bool | None = None
    brewing_unit_closed: bool | None = None
    milk_frother_running: bool | None = None
    milk_unit_state: str | None = None
    led_signaling: bool | None = None
    cup_length_prog: bool | None = None
    water_hardness: int | None = None
    wifi_status: str | None = None
    wifi_ssid: str | None = None
    error_code: int | None = None
    caps_counter: int | None = None
    iot_market_name: str | None = None
    error_list_code: int | None = None

    # Barista specific
    motor_running: bool | None = None
    induction_heating: bool | None = None
    setup_complete: bool | None = None
    ble_disabled: bool | None = None
    recipe_count: int | None = None

    # VMini specific
    shadow_data: str | None = None
    error_code_text: str | None = None
    fota_status: str | None = None
    fota_progress: int | None = None

    # Debug: full GATT characteristic dump
    gatt_dump: dict[str, dict[str, str]] | None = None


# Status flags that fire a device trigger when the machine raises them. The
# trigger type is the field name.
FLAG_TRIGGERS: tuple[str, ...] = ("descaling_needed", "water_tank_empty")


def is_brew_state(state: str) -> bool:
    """Return whether a machine state means a brew is in progress.

    The Barista and the Vertuo Next decode their numeric BREWING state to
    "brewing". A Vertuo Up's shadow namespaces its brew phases instead,
    seen on hardware as "brew/running" and "brew/waiting for top up"
    (fw 4.5.3), so anything under "brew/" counts. The top-up pause has to
    count as brewing: the machine goes from it to "brew/top up" and back
    to it, and only leaves the namespace when the capsule is ejected, so
    treating the pause as finished would report one coffee as two. Other
    activities keep their own namespaces ("descale/...", "rinse/...") and
    are not brews.
    """
    return state == "brewing" or state.startswith("brew/")


def is_brew_run_state(state: str) -> bool:
    """Return whether a machine state means extraction is actually pouring.

    A Vertuo Up only reports "brew/running" while a fresh extraction pours
    and gives the top-up phase its own states - seen on hardware as
    "brew/waiting for top up" while it waits for the button and "brew/top up"
    while the top-up pours (fw 4.5.3). Brew counting keys on pouring, so a
    top-up is never a new brew and a new capsule started from the pause
    always is. "brewing" is the Barista/Vertuo Next pour state.
    """
    return state in ("brewing", "brew/running")


def counts_as_brew(previous: str, current: str) -> bool:
    """Return whether a change from previous to current is a new brew.

    Entering a pour always is. So is entering the brew namespace from
    outside it, since a whole pour can fit between two polls, except into a
    barcode read, which may never reach a pour. A phase change inside one
    brew is not.
    """
    if previous == current or not is_brew_state(current):
        return False
    if is_brew_run_state(current):
        return True
    return not is_brew_state(previous) and not current.endswith(" reading")


def machine_triggers(old: NespressoMachineData, new: NespressoMachineData) -> list[str]:
    """Name the device triggers that fire when old gives way to new.

    States fire on the way in, and brewing also on the way out. The flags fire
    when the machine raises them, so a tank that stays empty across several
    polls fires once, when it emptied. A family whose parser never sets a flag
    leaves it None, which never fires.
    """
    triggers: list[str] = []
    if new.machine_state != old.machine_state:
        if is_brew_state(new.machine_state) and not is_brew_state(old.machine_state):
            triggers.append("brewing_started")
        if is_brew_state(old.machine_state) and not is_brew_state(new.machine_state):
            triggers.append("brewing_finished")
        if new.machine_state == "error":
            triggers.append("error_occurred")
        elif new.machine_state in ("ready", "standby"):
            triggers.append(new.machine_state)
    for flag in FLAG_TRIGGERS:
        if getattr(new, flag) and not getattr(old, flag):
            triggers.append(flag)
    return triggers


@dataclass(slots=True)
class RawMachineData:
    """Raw bytes read from BLE characteristics before parsing."""

    status_bytes: bytes | None = None
    info_bytes: bytes | None = None
    serial_bytes: bytes | None = None
    profile_version_bytes: bytes | None = None
    machine_params_bytes: bytes | None = None
    recipe_info_bytes: bytes | None = None
    user_settings_bytes: bytes | None = None
    error_info_bytes: bytes | None = None
    caps_counter_bytes: bytes | None = None
    error_list_bytes: bytes | None = None
    iot_market_bytes: bytes | None = None
    # VMini uses decoded strings from standard BLE Device Info
    firmware_version: str | None = None
    software_version: str | None = None
    shadow_header: str | None = None
    shadow_data: str | None = None
    asset_versions: str | None = None
    fota_status_bytes: bytes | None = None
    wifi_current_bytes: bytes | None = None
    gatt_dump: dict[str, dict[str, str]] | None = None
