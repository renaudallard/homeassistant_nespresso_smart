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

    # Vertuo Next specific
    water_tank_empty: bool | None = None
    descaling_needed: bool | None = None
    cleaning_needed: bool | None = None
    capsule_container_full: bool | None = None
    brewing_unit_closed: bool | None = None
    milk_frother_running: bool | None = None
    water_hardness: int | None = None
    auto_power_off: int | None = None
    error_code: int | None = None

    # Barista specific
    motor_running: bool | None = None

    # VMini specific
    shadow_data: str | None = None


@dataclass(slots=True)
class RawMachineData:
    """Raw bytes read from BLE characteristics before parsing."""

    status_bytes: bytes | None = None
    info_bytes: bytes | None = None
    serial_bytes: bytes | None = None
    user_settings_bytes: bytes | None = None
    error_info_bytes: bytes | None = None
    # VMini uses decoded strings from standard BLE Device Info
    firmware_version: str | None = None
    software_version: str | None = None
    model_number: str | None = None
    manufacturer: str | None = None
    pairing_byte: int | None = None
    wifi_mac: str | None = None
    shadow_header: str | None = None
