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

"""Diagnostics support for Nespresso Smart integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import NespressoCoordinator

# Nothing here is redacted, on purpose. The one credential the machine holds is
# the auth token, and it never enters the download: the config entry section is
# built by hand without it, and the GATT dump blanks its characteristic at the
# source. The address and the serial are what an issue needs, the serial
# because it carries the platform code that names the model, and both are in
# every debug log a reporter pastes beside the download anyway. Redacting them
# in one section while the dump and the watch record carried them in plain hex
# protected nothing and cost the reader the model.


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: NespressoCoordinator = data["coordinator"]

    diag: dict[str, Any] = {
        "config_entry": {
            "address": entry.data.get("address"),
            "family": entry.data.get("family"),
            "name": entry.data.get("name"),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None,
        },
    }

    if coordinator.data is not None:
        data_dict = asdict(coordinator.data)
        gatt_dump = data_dict.pop("gatt_dump", None)
        diag["machine_data"] = data_dict
        if gatt_dump:
            diag["gatt_characteristic_dump"] = gatt_dump

    if coordinator.last_command is not None:
        diag["last_command"] = coordinator.last_command

    if coordinator.last_watch is not None:
        diag["last_watch"] = coordinator.last_watch

    if coordinator.last_exception is not None:
        diag["last_error"] = str(coordinator.last_exception)

    diag["debug_info"] = {
        "family": coordinator.family.value,
        "pairing_key_state": coordinator.pairing_key_state,
        "persistent_mode": coordinator.persistent,
        "has_active_client": coordinator.is_connected,
    }

    return diag
