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

"""Constants for the Nespresso Smart integration."""

from enum import IntEnum, StrEnum
from typing import Final

DOMAIN: Final = "nespresso"
DEFAULT_SCAN_INTERVAL: Final = 60  # seconds


class MachineFamily(StrEnum):
    """Nespresso machine hardware families."""

    BARISTA = "barista"
    VERTUO_NEXT = "vertuo_next"
    VMINI = "vmini"


# ---------------------------------------------------------------------------
# Barista (Original Line) BLE UUIDs
# Source: com.sdataway.barista.sdk.GATTattributes.DeviceGATTAttributes
# ---------------------------------------------------------------------------

BARISTA_BASIC_SERVICE: Final = "65241910-0253-11e7-93ae-92361f002671"
BARISTA_CHAR_STATUS: Final = "65243a12-0253-11e7-93ae-92361f002671"
BARISTA_CHAR_INFO: Final = "65243a21-0253-11e7-93ae-92361f002671"
BARISTA_CHAR_LANGUAGE: Final = "65243a1a-0253-11e7-93ae-92361f002671"
BARISTA_CHAR_RECIPE_SELECTION: Final = "65243a19-0253-11e7-93ae-92361f002671"
BARISTA_CHAR_PROFILE_VERSION: Final = "65243a11-0253-11e7-93ae-92361f002671"
BARISTA_CHAR_AUTH: Final = "65243a41-0253-11e7-93ae-92361f002671"
BARISTA_CHAR_ONBOARD_STATUS: Final = "65243a51-0253-11e7-93ae-92361f002671"
BARISTA_CHAR_PAIR: Final = "65243a61-0253-11e7-93ae-92361f002671"
BARISTA_CHAR_MACHINE_PARAMS: Final = "65243a22-0253-11e7-93ae-92361f002671"
BARISTA_CHAR_SERIAL: Final = "65243a31-0253-11e7-93ae-92361f002671"

# ---------------------------------------------------------------------------
# Vertuo Next (Venus Line) BLE UUIDs
# Source: com.sdataway.vertuonext.sdk.GATTattributes.DeviceGATTAttributes
# ---------------------------------------------------------------------------

VERTUO_BASIC_SERVICE: Final = "06aa1910-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_STATUS: Final = "06aa3a12-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_INFO: Final = "06aa3a21-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_SERIAL: Final = "06aa3a31-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_PROFILE_VERSION: Final = "06aa3a11-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_AUTH: Final = "06aa3a41-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_COMMAND_REQ: Final = "06aa3a42-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_ONBOARD_STATUS: Final = "06aa3a51-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_PAIR: Final = "06aa3a61-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_CAPS_COUNTER: Final = "06aa3a15-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_COMMAND_RSP: Final = "06aa3a52-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_ERROR_INFO: Final = "06aa3a23-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_IOT_MARKET: Final = "06aa3a79-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_MACHINE_PARAMS: Final = "06aa3a22-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_USER_SETTINGS: Final = "06aa3a44-f22a-11e3-9daa-0002a5d5c51b"

# ---------------------------------------------------------------------------
# VMini (Vertuo Mini) BLE UUIDs
# Source: com.sdataway.vmini.sdk.GATTattributes.DeviceGATTAttributes
# ---------------------------------------------------------------------------

VMINI_BASIC_SERVICE: Final = "96600100-526e-4676-a11a-af1eb848165b"
VMINI_CHAR_SERIAL: Final = "96600102-526e-4676-a11a-af1eb848165b"
VMINI_CHAR_PAIRING: Final = "96600103-526e-4676-a11a-af1eb848165b"
VMINI_CHAR_MODEL: Final = "00002a24-0000-1000-8000-00805f9b34fb"
VMINI_CHAR_FW_REV: Final = "00002a26-0000-1000-8000-00805f9b34fb"
VMINI_CHAR_SW_REV: Final = "00002a28-0000-1000-8000-00805f9b34fb"
VMINI_CHAR_MANUFACTURER: Final = "00002a29-0000-1000-8000-00805f9b34fb"
VMINI_CHAR_MACHINE_TOKEN: Final = "96600105-526e-4676-a11a-af1eb848165b"
VMINI_CHAR_WIFI_MAC: Final = "e0f00205-5c88-455f-98ba-cfe7db1a7d1d"
VMINI_CHAR_WIFI_CURRENT: Final = "e0f00202-5c88-455f-98ba-cfe7db1a7d1d"
VMINI_CHAR_FOTA_STATUS: Final = "e0f00302-5c88-455f-98ba-cfe7db1a7d1d"
VMINI_CHAR_SHADOW_HEADER: Final = "e0f00501-5c88-455f-98ba-cfe7db1a7d1d"

# ---------------------------------------------------------------------------
# Service UUID to family mapping
# ---------------------------------------------------------------------------

SERVICE_UUID_TO_FAMILY: Final[dict[str, MachineFamily]] = {
    BARISTA_BASIC_SERVICE: MachineFamily.BARISTA,
    VERTUO_BASIC_SERVICE: MachineFamily.VERTUO_NEXT,
    VMINI_BASIC_SERVICE: MachineFamily.VMINI,
}

# ---------------------------------------------------------------------------
# Machine state enums
# Source: com.sdataway.barista.sdk.models.MachineStatus.MachineState
# ---------------------------------------------------------------------------


class BaristaState(IntEnum):
    """Barista machine operational states."""

    STANDBY = 0
    READY = 1
    RECIPE_EXECUTING = 2
    LOCAL_SETTINGS = 3
    ERROR = 4
    OVERHEATED = 5
    OUT_OF_BOX = 6
    RECIPE_PAUSED = 7
    UNKNOWN = 255


# Source: com.sdataway.vertuonext.sdk.models.MachineStatus.MachineState


class VertuoNextState(IntEnum):
    """Vertuo Next machine operational states."""

    FACTORY_RESET = 0
    HEATUP = 1
    READY = 2
    DESCALING_READY = 3
    BREWING = 4
    CLEANING = 5
    DESCALING = 6
    EMPTYING = 7
    DEVICE_ERROR = 8
    POWER_SAVE = 9
    COOLDOWN = 10
    SERVICE_MODE = 11
    STANDBY = 12
    UPDATING = 13
    RINSING = 14
    CAPSULE_READING = 17
    DESCALE_SEQUENCE_DECODING = 18
    TANK_EMPTY = 19
    DESCALING_PAUSED = 20
    INITIALIZATION = 21
    RINSING_READY = 22
    MAINTENANCE_MENU = 23
    CLEANING_PAUSED = 26
    EMPTYING_READY = 33
    CLEANING_READY = 34
    READY_OLD_CAPSULE = 35
    RINSING_PAUSED = 36
    UNKNOWN = 255


# Human-readable state names

BARISTA_STATE_NAMES: Final[dict[int, str]] = {
    BaristaState.STANDBY: "standby",
    BaristaState.READY: "ready",
    BaristaState.RECIPE_EXECUTING: "brewing",
    BaristaState.LOCAL_SETTINGS: "local_settings",
    BaristaState.ERROR: "error",
    BaristaState.OVERHEATED: "overheated",
    BaristaState.OUT_OF_BOX: "setup",
    BaristaState.RECIPE_PAUSED: "paused",
}

VERTUO_STATE_NAMES: Final[dict[int, str]] = {
    VertuoNextState.FACTORY_RESET: "factory_reset",
    VertuoNextState.HEATUP: "heating",
    VertuoNextState.READY: "ready",
    VertuoNextState.DESCALING_READY: "descaling_ready",
    VertuoNextState.BREWING: "brewing",
    VertuoNextState.CLEANING: "cleaning",
    VertuoNextState.DESCALING: "descaling",
    VertuoNextState.EMPTYING: "emptying",
    VertuoNextState.DEVICE_ERROR: "error",
    VertuoNextState.POWER_SAVE: "power_save",
    VertuoNextState.COOLDOWN: "cooldown",
    VertuoNextState.SERVICE_MODE: "service_mode",
    VertuoNextState.STANDBY: "standby",
    VertuoNextState.UPDATING: "updating",
    VertuoNextState.RINSING: "rinsing",
    VertuoNextState.CAPSULE_READING: "capsule_reading",
    VertuoNextState.DESCALE_SEQUENCE_DECODING: "descale_decoding",
    VertuoNextState.TANK_EMPTY: "tank_empty",
    VertuoNextState.DESCALING_PAUSED: "descaling_paused",
    VertuoNextState.INITIALIZATION: "initializing",
    VertuoNextState.RINSING_READY: "rinsing_ready",
    VertuoNextState.MAINTENANCE_MENU: "maintenance_menu",
    VertuoNextState.CLEANING_PAUSED: "cleaning_paused",
    VertuoNextState.EMPTYING_READY: "emptying_ready",
    VertuoNextState.CLEANING_READY: "cleaning_ready",
    VertuoNextState.READY_OLD_CAPSULE: "ready_old_capsule",
    VertuoNextState.RINSING_PAUSED: "rinsing_paused",
}

MACHINE_FAMILY_NAMES: Final[dict[MachineFamily, str]] = {
    MachineFamily.BARISTA: "Barista",
    MachineFamily.VERTUO_NEXT: "Vertuo Next",
    MachineFamily.VMINI: "Vertuo Mini",
}
