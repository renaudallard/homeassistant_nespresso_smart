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
from collections.abc import Iterator
from contextlib import contextmanager

import voluptuous as vol
from bleak import BleakError
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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import UNDEFINED

from .ble.parsing import nespresso_manufacturer_data
from .ble.protocol import generate_auth_key
from .config_flow import (
    CONF_PERSISTENT_CONNECTION,
    CONF_SCAN_INTERVAL,
    CONF_SEND_TX_LEVEL,
)
from .const import (
    COMMAND_CHANNELS,
    CONF_DESCALING_CAPSULES,
    CONF_DESCALING_DAYS,
    DEFAULT_DESCALING_CAPSULES,
    DEFAULT_DESCALING_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EXPERT_ABSENT_BINARY_SENSORS,
    WIFI_SECURITY_TYPES,
    MachineFamily,
)
from .coordinator import NespressoCoordinator, counter_store
from .entity import (
    device_versions,
    has_milk_unit,
    machine_device_info,
    platform_code,
    supports_brewing,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.EVENT,
]

# Entities an older version created and this one does not. The registry entry
# outlives the upgrade, and Home Assistant gives an entry with no entity behind
# it the state unavailable, so they are dropped on the way in.
#
# caps_counter was a sensor up to v0.5.15, created for the whole Vertuo Next
# family whether or not the machine answered on 06AA3A15, so a Pop or a
# Creatista carried one that never held a value. The writable number took over
# in v0.5.16 and is only created where the counter reads back.
#
# auto_power_off_setting showed bytes 0-1 of 06AA3A44 as minutes. The app
# never reads that field and writes 0xFFFF there whenever it sets the water
# hardness. A Vertuo Next and a Creatista both read back 255, the app has no
# such setting and the Vertuo Next did not power off after that long, so it
# was a value of unknown meaning offered as a writable timer.
REMOVED_ENTITIES: tuple[tuple[Platform, str], ...] = (
    (Platform.SENSOR, "caps_counter"),
    (Platform.NUMBER, "auto_power_off_setting"),
)


SERVICE_SCAN_WIFI = "scan_wifi"
SERVICE_CONFIGURE_WIFI = "configure_wifi"
SERVICE_SEND_COMMAND = "send_command"
SERVICE_WATCH = "watch"

ATTR_ENTRY_ID = "config_entry_id"

_SCAN_WIFI_SCHEMA = vol.Schema({vol.Required(ATTR_ENTRY_ID): cv.string})

_SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): cv.string,
        vol.Required("payload"): cv.string,
    }
)

_WATCH_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): cv.string,
        vol.Optional("seconds", default=60): vol.All(
            vol.Coerce(float), vol.Range(min=5, max=1800)
        ),
    }
)

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
        raise ServiceValidationError(f"No Nespresso machine is loaded under {entry_id}")
    coordinator: NespressoCoordinator = data["coordinator"]
    return coordinator


@contextmanager
def _reported(action: str) -> Iterator[None]:
    """Hand a Bluetooth failure to the caller as an error it can show."""
    try:
        yield
    except (BleakError, TimeoutError) as err:
        raise HomeAssistantError(f"{action} failed: {err}") from err


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register the services once, not per config entry.

    All of them are admin only: they rewrite the machine's network, write raw
    frames, hold the machine connected or list the networks around it.
    """
    if hass.services.has_service(DOMAIN, SERVICE_SCAN_WIFI):
        return

    async def _scan(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call.data[ATTR_ENTRY_ID])
        with _reported("WiFi scan"):
            networks = await coordinator.async_scan_wifi()
        return {"networks": networks}

    async def _configure(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data[ATTR_ENTRY_ID])
        with _reported("WiFi setup"):
            try:
                await coordinator.async_configure_wifi(
                    call.data["market"],
                    call.data["ssid"],
                    call.data["password"],
                    WIFI_SECURITY_TYPES[call.data["security"]],
                    call.data["connection_index"],
                )
            except ValueError as err:
                # An SSID or a passphrase longer than the frame holds.
                raise ServiceValidationError(str(err)) from err

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SCAN_WIFI,
        _scan,
        schema=_SCAN_WIFI_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    async def _send_command(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call.data[ATTR_ENTRY_ID])
        channel = COMMAND_CHANNELS.get(coordinator.family)
        if channel is None:
            raise ServiceValidationError(
                f"{coordinator.family.value} has no command channel"
            )
        text = call.data["payload"].replace(" ", "").replace(":", "")
        try:
            payload = bytes.fromhex(text)
        except ValueError as err:
            raise ServiceValidationError(
                f"payload is not hex: {call.data['payload']}"
            ) from err
        if not payload:
            raise ServiceValidationError("payload is empty")

        cmd_uuid, rsp_uuid = channel
        with _reported("Command"):
            await coordinator.async_send_command(
                cmd_uuid, rsp_uuid, payload, probe=True
            )
        # async_send_command returns the answer, but the record says more: what
        # the two characteristics offer, and whether anything could have come
        # back at all. That distinction is the whole point of asking.
        return dict(coordinator.last_command or {})

    async_register_admin_service(
        hass, DOMAIN, SERVICE_CONFIGURE_WIFI, _configure, schema=_CONFIGURE_WIFI_SCHEMA
    )

    async def _watch(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call.data[ATTR_ENTRY_ID])
        with _reported("Watch"):
            return await coordinator.async_watch(call.data["seconds"])

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_WATCH,
        _watch,
        schema=_WATCH_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SEND_COMMAND,
        _send_command,
        schema=_SEND_COMMAND_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


@callback
def _async_remove_stale_entities(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: NespressoCoordinator
) -> None:
    """Drop registry entries left behind by entities we no longer create."""
    registry = er.async_get(hass)
    address = entry.data["address"]
    stale = list(REMOVED_ENTITIES)
    # Every Venus machine had the frother sensor up to v0.5.15. Only a known
    # model loses it, since an unknown one may still turn out to have milk.
    if platform_code(entry, coordinator) is not None and not has_milk_unit(
        entry, coordinator
    ):
        stale.append((Platform.BINARY_SENSOR, "milk_frother_running"))
    # Every Venus machine had the two brew settings up to v0.5.10, and turning
    # force_brew_button off leaves all three behind.
    if MachineFamily(entry.data["family"]) is MachineFamily.VERTUO_NEXT and not (
        supports_brewing(entry, coordinator)
    ):
        stale += [
            (Platform.BUTTON, "vertuo_brew"),
            (Platform.SELECT, "vertuo_brew_type"),
            (Platform.SELECT, "vertuo_brew_temp"),
        ]
    if coordinator.is_expert:
        # An Expert had both up to v0.5.38.
        stale += [(Platform.BINARY_SENSOR, k) for k in EXPERT_ABSENT_BINARY_SENSORS]
    if coordinator.data is not None and coordinator.data.caps_counter_off:
        # v0.5.38 offered the disabled value as a count. A failed read leaves
        # the entry alone, since the counter may be back on the next setup.
        stale.append((Platform.NUMBER, "caps_counter_setting"))
    for platform, key in stale:
        entity_id = registry.async_get_entity_id(platform, DOMAIN, f"{address}_{key}")
        if entity_id is None:
            continue
        _LOGGER.debug("Removing stale entity %s", entity_id)
        registry.async_remove(entity_id)


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
    # The name the machine advertised when it was added. The title would do
    # until someone renames the entry.
    coordinator.is_expert = "expert" in (entry.data.get("name") or "").lower()

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

    # Passive fast path. The Venus advertisement carries the same MachineStatus
    # bytes as the connected characteristic, roughly twice a second, so state
    # and flags update almost instantly instead of once per scan interval.
    # Registered with connectable=False so advertisements seen by
    # non-connectable scanners (ESPHome proxies) count too, and before the
    # first refresh: it also carries the pairing key state, which matters most
    # on a machine refusing every read, whose first refresh fails. A failed
    # setup runs the unload callbacks, so nothing is left registered.
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

    await coordinator.async_config_entry_first_refresh()

    # Register device and set device_id for trigger events
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, **machine_device_info(entry, coordinator)
    )
    coordinator.set_device_id(device_entry.id)

    # Entities hand the registry their device info only when they are added,
    # so a firmware update would not reach the device page until a reload.
    @callback
    def _async_update_device() -> None:
        known = device_versions(coordinator)
        device_registry.async_update_device(
            device_entry.id,
            serial_number=known.get("serial_number", UNDEFINED),
            sw_version=known.get("sw_version", UNDEFINED),
            hw_version=known.get("hw_version", UNDEFINED),
        )

    entry.async_on_unload(coordinator.async_add_listener(_async_update_device))

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

    @callback
    def _async_on_ble_unavailable(
        service_info: bluetooth.BluetoothServiceInfoBleak,
    ) -> None:
        coordinator.async_machine_gone()

    entry.async_on_unload(
        bluetooth.async_track_unavailable(
            hass, _async_on_ble_unavailable, address, connectable=True
        )
    )

    await _async_register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    _async_remove_stale_entities(hass, entry, coordinator)
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
