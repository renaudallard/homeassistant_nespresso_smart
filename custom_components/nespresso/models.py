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
    water_hardness: int | None = None

    # Barista specific
    motor_running: bool | None = None


@dataclass(slots=True)
class RawMachineData:
    """Raw bytes read from BLE characteristics before parsing."""

    status_bytes: bytes | None = None
    info_bytes: bytes | None = None
    serial_bytes: bytes | None = None
    user_settings_bytes: bytes | None = None
    # VMini uses decoded strings from standard BLE Device Info
    firmware_version: str | None = None
    model_number: str | None = None
    manufacturer: str | None = None
    pairing_byte: int | None = None
