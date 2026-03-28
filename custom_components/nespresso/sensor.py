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

"""Sensor entities for Nespresso Smart integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BARISTA_STATE_NAMES,
    DOMAIN,
    MACHINE_FAMILY_NAMES,
    VERTUO_STATE_NAMES,
    MachineFamily,
)
from .coordinator import NespressoCoordinator
from .models import NespressoMachineData

ALL_STATE_OPTIONS: list[str] = sorted(
    set(BARISTA_STATE_NAMES.values()) | set(VERTUO_STATE_NAMES.values()) | {"unknown"}
)


@dataclass(frozen=True)
class NespressoSensorDescription(SensorEntityDescription):
    """Sensor description with machine family filter."""

    families: frozenset[MachineFamily] = frozenset(MachineFamily)
    value_fn: Callable[[NespressoMachineData], str | int | None] = lambda _: None


SENSOR_DESCRIPTIONS: tuple[NespressoSensorDescription, ...] = (
    NespressoSensorDescription(
        key="machine_state",
        translation_key="machine_state",
        name="State",
        icon="mdi:coffee-maker",
        device_class=SensorDeviceClass.ENUM,
        options=ALL_STATE_OPTIONS,
        families=frozenset({MachineFamily.BARISTA, MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.machine_state,
    ),
    NespressoSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        name="Firmware version",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.firmware_version,
    ),
    NespressoSensorDescription(
        key="hardware_version",
        translation_key="hardware_version",
        name="Hardware version",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.BARISTA, MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.hardware_version,
    ),
    NespressoSensorDescription(
        key="water_hardness",
        translation_key="water_hardness",
        name="Water hardness",
        icon="mdi:water",
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.water_hardness,
    ),
    NespressoSensorDescription(
        key="auto_power_off",
        translation_key="auto_power_off",
        name="Auto power off",
        icon="mdi:timer-off-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.auto_power_off,
    ),
    NespressoSensorDescription(
        key="error_code",
        translation_key="error_code",
        name="Error code",
        icon="mdi:alert-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.error_code,
    ),
    NespressoSensorDescription(
        key="shadow_data",
        translation_key="shadow_data",
        name="Device shadow",
        icon="mdi:cloud-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.VMINI}),
        value_fn=lambda d: d.shadow_data,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nespresso sensor entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: NespressoCoordinator = data["coordinator"]
    family = MachineFamily(entry.data["family"])

    entities = [
        NespressoSensor(coordinator, entry, desc)
        for desc in SENSOR_DESCRIPTIONS
        if family in desc.families
    ]
    async_add_entities(entities)


class NespressoSensor(CoordinatorEntity[NespressoCoordinator], SensorEntity):
    """A Nespresso machine sensor."""

    entity_description: NespressoSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NespressoCoordinator,
        entry: ConfigEntry,
        description: NespressoSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.data['address']}_{description.key}"
        family = MachineFamily(entry.data["family"])
        data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["address"])},
            name=entry.data.get("name", "Nespresso"),
            manufacturer="Nespresso",
            model=MACHINE_FAMILY_NAMES.get(family, "Unknown"),
            serial_number=data.serial_number if data else None,
            sw_version=data.firmware_version if data else None,
            hw_version=data.hardware_version if data else None,
        )

    @property
    def native_value(self) -> str | int | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
