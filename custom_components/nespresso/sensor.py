"""Sensor entities for Nespresso Smart integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MACHINE_FAMILY_NAMES, MachineFamily
from .coordinator import NespressoCoordinator
from .models import NespressoMachineData


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
