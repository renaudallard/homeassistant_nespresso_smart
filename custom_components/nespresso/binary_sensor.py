"""Binary sensor entities for Nespresso Smart integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MACHINE_FAMILY_NAMES, MachineFamily
from .coordinator import NespressoCoordinator
from .models import NespressoMachineData


@dataclass(frozen=True)
class NespressoBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor description with machine family filter."""

    families: frozenset[MachineFamily] = frozenset(MachineFamily)
    value_fn: Callable[[NespressoMachineData], bool | None] = lambda _: None


BINARY_SENSOR_DESCRIPTIONS: tuple[NespressoBinarySensorDescription, ...] = (
    NespressoBinarySensorDescription(
        key="error_present",
        translation_key="error_present",
        name="Error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        families=frozenset({MachineFamily.BARISTA, MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.error_present,
    ),
    NespressoBinarySensorDescription(
        key="water_tank_empty",
        translation_key="water_tank_empty",
        name="Water tank empty",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:cup-water",
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.water_tank_empty,
    ),
    NespressoBinarySensorDescription(
        key="descaling_needed",
        translation_key="descaling_needed",
        name="Descaling needed",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-circle-outline",
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.descaling_needed,
    ),
    NespressoBinarySensorDescription(
        key="cleaning_needed",
        translation_key="cleaning_needed",
        name="Cleaning needed",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:broom",
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.cleaning_needed,
    ),
    NespressoBinarySensorDescription(
        key="capsule_container_full",
        translation_key="capsule_container_full",
        name="Capsule container full",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:delete-variant",
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.capsule_container_full,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nespresso binary sensor entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: NespressoCoordinator = data["coordinator"]
    family = MachineFamily(entry.data["family"])

    entities = [
        NespressoBinarySensor(coordinator, entry, desc)
        for desc in BINARY_SENSOR_DESCRIPTIONS
        if family in desc.families
    ]
    async_add_entities(entities)


class NespressoBinarySensor(
    CoordinatorEntity[NespressoCoordinator], BinarySensorEntity
):
    """A Nespresso machine binary sensor."""

    entity_description: NespressoBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NespressoCoordinator,
        entry: ConfigEntry,
        description: NespressoBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.data['address']}_{description.key}"
        family = MachineFamily(entry.data["family"])
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["address"])},
            name=entry.data.get("name", "Nespresso"),
            manufacturer="Nespresso",
            model=MACHINE_FAMILY_NAMES.get(family, "Unknown"),
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
