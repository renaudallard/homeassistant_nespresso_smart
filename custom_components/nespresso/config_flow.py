"""Config flow for Nespresso Smart BLE integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    DOMAIN,
    MACHINE_FAMILY_NAMES,
    SERVICE_UUID_TO_FAMILY,
    MachineFamily,
)


class NespressoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nespresso BLE machines."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._family: MachineFamily | None = None
        self._name: str = "Nespresso"

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle BLE device discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self._family = self._detect_family(discovery_info)
        family_label = (
            MACHINE_FAMILY_NAMES.get(self._family, "Unknown")
            if self._family
            else "Unknown"
        )

        self._name = discovery_info.name or f"Nespresso {family_label}"
        self.context["title_placeholders"] = {"name": self._name}

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovered device."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._name,
                data={
                    "address": self._discovery_info.address  # type: ignore[union-attr]
                    if self._discovery_info
                    else "",
                    "family": self._family.value
                    if self._family
                    else MachineFamily.VERTUO_NEXT.value,
                    "name": self._name,
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup: direct user to auto-discovery."""
        return self.async_abort(reason="bluetooth_only")

    @staticmethod
    def _detect_family(
        info: BluetoothServiceInfoBleak,
    ) -> MachineFamily | None:
        """Determine machine family from advertised service UUIDs."""
        for uuid in info.service_uuids:
            family = SERVICE_UUID_TO_FAMILY.get(uuid.lower())
            if family is not None:
                return family
        return None
