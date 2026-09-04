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
    SensorStateClass,
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
    VERTUO_STATE_NAMES,
    WIFI_STATUS_NAMES,
    MachineFamily,
)
from .coordinator import NespressoCoordinator
from .entity import machine_device_info
from .models import NespressoMachineData
from .timer_sensor import NespressoBrewingDuration

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
        icon="mdi:coffee-maker",
        device_class=SensorDeviceClass.ENUM,
        options=ALL_STATE_OPTIONS,
        families=frozenset({MachineFamily.BARISTA, MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.machine_state,
    ),
    NespressoSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.firmware_version,
    ),
    NespressoSensorDescription(
        key="hardware_version",
        translation_key="hardware_version",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.BARISTA, MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.hardware_version,
    ),
    NespressoSensorDescription(
        key="recipe_count",
        translation_key="recipe_count",
        icon="mdi:book-open-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.BARISTA}),
        value_fn=lambda d: d.recipe_count,
    ),
    NespressoSensorDescription(
        key="profile_version",
        translation_key="profile_version",
        icon="mdi:information-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.BARISTA, MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.profile_version,
    ),
    NespressoSensorDescription(
        key="bootloader_version",
        translation_key="bootloader_version",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.BARISTA, MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.bootloader_version,
    ),
    NespressoSensorDescription(
        key="bluetooth_version",
        translation_key="bluetooth_version",
        icon="mdi:bluetooth",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.BARISTA}),
        value_fn=lambda d: d.bluetooth_version,
    ),
    NespressoSensorDescription(
        key="recipe_db_version",
        translation_key="recipe_db_version",
        icon="mdi:database-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.recipe_db_version,
    ),
    NespressoSensorDescription(
        key="connectivity_fw_version",
        translation_key="connectivity_fw_version",
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.connectivity_fw_version,
    ),
    NespressoSensorDescription(
        key="error_code",
        translation_key="error_code",
        icon="mdi:alert-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.error_code,
    ),
    NespressoSensorDescription(
        key="error_list_code",
        translation_key="error_list_code",
        icon="mdi:alert-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.error_list_code,
    ),
    NespressoSensorDescription(
        key="wifi_status",
        translation_key="wifi_status",
        icon="mdi:wifi",
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(WIFI_STATUS_NAMES.values())),
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.wifi_status,
    ),
    NespressoSensorDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        icon="mdi:wifi-cog",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.wifi_ssid,
    ),
    NespressoSensorDescription(
        key="iot_market_name",
        translation_key="iot_market_name",
        icon="mdi:earth",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.iot_market_name,
    ),
    NespressoSensorDescription(
        key="caps_counter",
        translation_key="caps_counter",
        icon="mdi:counter",
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda d: d.caps_counter,
    ),
    NespressoSensorDescription(
        key="shadow_data",
        translation_key="shadow_data",
        icon="mdi:cloud-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.VMINI}),
        value_fn=lambda d: d.shadow_data,
    ),
    NespressoSensorDescription(
        key="fota_status",
        translation_key="fota_status",
        icon="mdi:cellphone-arrow-down",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.VMINI}),
        value_fn=lambda d: d.fota_status,
    ),
    NespressoSensorDescription(
        key="fota_progress",
        translation_key="fota_progress",
        icon="mdi:progress-download",
        entity_category=EntityCategory.DIAGNOSTIC,
        families=frozenset({MachineFamily.VMINI}),
        value_fn=lambda d: d.fota_progress,
    ),
)


@dataclass(frozen=True)
class NespressoCounterDescription(SensorEntityDescription):
    """Description for a counter that lives on the coordinator, not the model."""

    families: frozenset[MachineFamily] = frozenset(MachineFamily)
    value_fn: Callable[[NespressoCoordinator], int | None] = lambda _: None


COUNTER_DESCRIPTIONS: tuple[NespressoCounterDescription, ...] = (
    NespressoCounterDescription(
        key="brew_total",
        translation_key="brew_total",
        icon="mdi:coffee",
        state_class=SensorStateClass.TOTAL_INCREASING,
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda c: c.brew_total,
    ),
    NespressoCounterDescription(
        key="brews_since_descaling",
        translation_key="brews_since_descaling",
        icon="mdi:coffee-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda c: c.brews_since_descaling,
    ),
    NespressoCounterDescription(
        key="brews_until_descaling",
        translation_key="brews_until_descaling",
        icon="mdi:coffee-off-outline",
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda c: c.brews_until_descaling,
    ),
    NespressoCounterDescription(
        key="days_until_descaling",
        translation_key="days_until_descaling",
        icon="mdi:calendar-clock",
        native_unit_of_measurement="d",
        families=frozenset({MachineFamily.VERTUO_NEXT}),
        value_fn=lambda c: c.days_until_descaling,
    ),
)


class NespressoCounterSensor(CoordinatorEntity[NespressoCoordinator], SensorEntity):
    """Counter derived from state transitions rather than machine data.

    Kept separate from NespressoSensor because these values live on the
    coordinator and stay valid even when the machine cannot be read.
    """

    _attr_has_entity_name = True
    entity_description: NespressoCounterDescription

    def __init__(
        self,
        coordinator: NespressoCoordinator,
        entry: ConfigEntry,
        description: NespressoCounterDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._address = entry.data["address"]
        self._attr_unique_id = f"{self._address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=entry.data.get("name", "Nespresso"),
            manufacturer="Nespresso",
        )

    @property
    def available(self) -> bool:
        """Counters are our own data, so they outlive a lost connection."""
        return True

    @property
    def native_value(self) -> int | None:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        if self.entity_description.key != "brews_since_descaling":
            return None
        return {"days_since_descaling": self.coordinator.days_since_descaling}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nespresso sensor entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: NespressoCoordinator = data["coordinator"]
    family = MachineFamily(entry.data["family"])

    entities: list[SensorEntity] = [
        NespressoSensor(coordinator, entry, desc)
        for desc in SENSOR_DESCRIPTIONS
        if family in desc.families
    ]

    # Real-time brewing duration sensor
    if family in (MachineFamily.BARISTA, MachineFamily.VERTUO_NEXT):
        entities.append(NespressoBrewingDuration(coordinator, entry))

    # Brew counters. The Vertuo Pop has no capsule counter characteristic, so
    # these are counted from state transitions instead.
    entities.extend(
        NespressoCounterSensor(coordinator, entry, desc)
        for desc in COUNTER_DESCRIPTIONS
        if family in desc.families
    )

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
        self._attr_device_info = machine_device_info(entry, coordinator)

    @property
    def native_value(self) -> str | int | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
