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

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .config_flow import CONF_PERSISTENT_CONNECTION, CONF_SCAN_INTERVAL
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MACHINE_FAMILY_NAMES, MachineFamily
from .coordinator import NespressoCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.EVENT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nespresso from a config entry."""
    address: str = entry.data["address"]
    family = MachineFamily(entry.data["family"])
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    persistent = entry.options.get(CONF_PERSISTENT_CONNECTION, False)

    _LOGGER.debug(
        "Setting up Nespresso %s: family=%s interval=%ds persistent=%s",
        address,
        family.value,
        scan_interval,
        persistent,
    )

    coordinator = NespressoCoordinator(hass, address, family, scan_interval, persistent)

    # Restore auth key and strategy
    auth_key = entry.data.get("auth_key")
    if auth_key:
        coordinator.auth_key = auth_key
        _LOGGER.debug("Restored auth key: %s****", auth_key[:4])

    # Only restore cached strategy if saved by the same version
    # (verification logic may change between versions)
    from .ble.protocol import _auth_strategy_cache

    saved_version = entry.data.get("auth_version")
    auth_strategy = entry.data.get("auth_strategy")
    from .coordinator import _VERSION

    if auth_strategy and saved_version == _VERSION:
        _auth_strategy_cache[address] = auth_strategy
        _LOGGER.debug("Restored auth strategy: %s", auth_strategy)
    elif auth_strategy:
        _LOGGER.debug(
            "Discarding cached strategy %s (saved by v%s, now v%s)",
            auth_strategy,
            saved_version,
            _VERSION,
        )

    await coordinator.async_config_entry_first_refresh()

    # Persist auth key and strategy if changed
    from .ble.protocol import _auth_strategy_cache

    current_strategy = _auth_strategy_cache.get(address)
    if (coordinator.auth_key and coordinator.auth_key != auth_key) or (
        current_strategy and current_strategy != auth_strategy
    ):
        new_data = {
            **entry.data,
            "auth_key": coordinator.auth_key or auth_key,
            "auth_strategy": current_strategy or auth_strategy,
            "auth_version": _VERSION,
        }
        hass.config_entries.async_update_entry(entry, data=new_data)
        _LOGGER.debug("Persisted auth key and strategy: %s", current_strategy)

    # Register device and set device_id for trigger events
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        name=entry.data.get("name", "Nespresso"),
        manufacturer="Nespresso",
        model=MACHINE_FAMILY_NAMES.get(family, "Unknown"),
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

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Nespresso %s setup complete, device_id=%s", address, device_entry.id)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Nespresso config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
