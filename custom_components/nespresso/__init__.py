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

"""Nespresso Smart BLE integration for Home Assistant."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .ble.parsing import nespresso_manufacturer_data
from .ble.protocol import generate_auth_key
from .config_flow import (
    CONF_PERSISTENT_CONNECTION,
    CONF_SCAN_INTERVAL,
    CONF_SEND_TX_LEVEL,
)
from .const import (
    CONF_DESCALING_CAPSULES,
    CONF_DESCALING_DAYS,
    DEFAULT_DESCALING_CAPSULES,
    DEFAULT_DESCALING_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    WIFI_SECURITY_TYPES,
    MachineFamily,
)
from .coordinator import NespressoCoordinator, counter_store
from .entity import machine_model

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.EVENT,
]


SERVICE_SCAN_WIFI = "scan_wifi"
SERVICE_CONFIGURE_WIFI = "configure_wifi"

ATTR_ENTRY_ID = "config_entry_id"

_SCAN_WIFI_SCHEMA = vol.Schema({vol.Required(ATTR_ENTRY_ID): cv.string})

_CONFIGURE_WIFI_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): cv.string,
        vol.Required("market"): vol.All(cv.string, vol.Length(min=2, max=2)),
        vol.Required("ssid"): cv.string,
        vol.Optional("password", default=""): cv.string,
        vol.Optional("security", default="wpa2"): vol.In(sorted(WIFI_SECURITY_TYPES)),
        vol.Optional("connection_index", default=255): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        ),
    }
)


def _coordinator(hass: HomeAssistant, entry_id: str) -> NespressoCoordinator:
    """Look up the coordinator a service call is aimed at."""
    data = hass.data.get(DOMAIN, {}).get(entry_id)
    if data is None:
        raise ValueError(f"No Nespresso machine configured under {entry_id}")
    coordinator: NespressoCoordinator = data["coordinator"]
    return coordinator


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register the WiFi services once, not per config entry."""
    if hass.services.has_service(DOMAIN, SERVICE_SCAN_WIFI):
        return

    async def _scan(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call.data[ATTR_ENTRY_ID])
        networks = await coordinator.async_scan_wifi()
        return {"networks": networks}

    async def _configure(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data[ATTR_ENTRY_ID])
        await coordinator.async_configure_wifi(
            call.data["market"],
            call.data["ssid"],
            call.data["password"],
            WIFI_SECURITY_TYPES[call.data["security"]],
            call.data["connection_index"],
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN_WIFI,
        _scan,
        schema=_SCAN_WIFI_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CONFIGURE_WIFI, _configure, schema=_CONFIGURE_WIFI_SCHEMA
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nespresso from a config entry."""
    address: str = entry.data["address"]
    family = MachineFamily(entry.data["family"])
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    persistent = entry.options.get(CONF_PERSISTENT_CONNECTION, False)
    send_tx_level = entry.options.get(CONF_SEND_TX_LEVEL, True)

    _LOGGER.debug(
        "Setting up Nespresso %s: family=%s interval=%ds persistent=%s",
        address,
        family.value,
        scan_interval,
        persistent,
    )

    coordinator = NespressoCoordinator(
        hass, address, family, scan_interval, persistent, send_tx_level
    )

    # Restore or generate auth key (must persist before first_refresh
    # so the same key survives ConfigEntryNotReady retries)
    auth_key = entry.data.get("auth_key")
    if auth_key:
        coordinator.auth_key = auth_key
        _LOGGER.debug("Restored auth key: %s****", auth_key[:4])
    else:
        auth_key = generate_auth_key()
        coordinator.auth_key = auth_key
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "auth_key": auth_key}
        )
        _LOGGER.debug("Generated and persisted auth key: %s****", auth_key[:4])

    await coordinator.async_load_counters(
        entry.options.get(CONF_DESCALING_CAPSULES, DEFAULT_DESCALING_CAPSULES),
        entry.options.get(CONF_DESCALING_DAYS, DEFAULT_DESCALING_DAYS),
    )

    await coordinator.async_config_entry_first_refresh()

    # Register device and set device_id for trigger events
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        name=entry.data.get("name", "Nespresso"),
        manufacturer="Nespresso",
        model=machine_model(entry, coordinator),
    )
    coordinator.set_device_id(device_entry.id)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    # Trigger immediate refresh when machine becomes available via BLE
    @callback
    def _async_on_ble_event(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        if not coordinator.last_update_success:
            _LOGGER.debug("Machine %s detected, triggering refresh", address)
            hass.async_create_task(coordinator.async_request_refresh())

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_on_ble_event,
            bluetooth.BluetoothCallbackMatcher(address=address, connectable=True),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    # Passive fast path. The Venus advertisement carries the same MachineStatus
    # bytes as the connected characteristic, roughly twice a second, so state
    # and flags update almost instantly instead of once per scan interval.
    # Registered separately from the availability callback above so the
    # existing behaviour is untouched, and with connectable=False so
    # advertisements seen by non-connectable scanners (ESPHome proxies) count
    # too.
    @callback
    def _async_on_advertisement(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        raw = nespresso_manufacturer_data(service_info.manufacturer_data)
        if not coordinator.async_apply_advertisement(raw):
            return
        # The state moved, so pull what the advertisement cannot carry -
        # counters, error codes, settings. async_request_refresh is debounced
        # by DataUpdateCoordinator, so a burst of transitions still results in
        # a single connection.
        hass.async_create_task(coordinator.async_request_refresh())

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_on_advertisement,
            bluetooth.BluetoothCallbackMatcher(address=address, connectable=False),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )

    await _async_register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Nespresso %s setup complete, device_id=%s", address, device_entry.id)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the stored brew counters when the machine is removed."""
    await counter_store(hass, entry.data["address"]).async_remove()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Nespresso config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
