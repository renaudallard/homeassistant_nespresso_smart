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

# Brew counting and descaling schedule.
#
# 06aa3a15 is the Vertuo capsule counter and it is optional: the protocol
# reads it when the machine answers, and the Vertuo Pop does not. Brews are
# counted here instead by watching the machine state enter BREWING. That state
# is distinct from CAPSULE_READING, so a failed read with no capsule is not
# counted.
#
# Nespresso quotes "300 capsules or 3 months, whichever comes first" for the
# Vertuo range. Both limits are configurable because hard water needs more
# frequent descaling.
CONF_DESCALING_CAPSULES = "descaling_capsules"
DEFAULT_DESCALING_CAPSULES = 300

CONF_DESCALING_DAYS = "descaling_days"
DEFAULT_DESCALING_DAYS = 90

# Offer brewing on a model that is not believed to brew. The belief comes from
# a handful of machines, and this is how someone gets to test theirs rather
# than take our word for it.
CONF_FORCE_BREW_BUTTON = "force_brew_button"

COUNTER_STORAGE_VERSION = 1
COUNTER_SAVE_DELAY = 15


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
BARISTA_CHAR_RECIPE_COMMAND: Final = "65243a29-0253-11e7-93ae-92361f002671"
BARISTA_CHAR_RECIPE_RESPONSE: Final = "65243a39-0253-11e7-93ae-92361f002671"
BARISTA_CHAR_RECIPE_INFO: Final = "65243a49-0253-11e7-93ae-92361f002671"
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
VERTUO_CHAR_ERROR_SELECTION: Final = "06aa3a13-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_IOT_MARKET: Final = "06aa3a79-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_MACHINE_PARAMS: Final = "06aa3a22-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_USER_SETTINGS: Final = "06aa3a44-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_WIFI_CURRENT: Final = "06aa3a29-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_WIFI_SETUP: Final = "06aa3a19-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_WIFI_SCAN_SELECT: Final = "06aa3a39-f22a-11e3-9daa-0002a5d5c51b"
VERTUO_CHAR_WIFI_SCAN_RESULT: Final = "06aa3a49-f22a-11e3-9daa-0002a5d5c51b"

# ---------------------------------------------------------------------------
# CCommandReq / CCommandRsp frame width
# Source: CharacCommandReq.setValue allocates 0x13 bytes, and a Creatista
# answers on CHAR_COMMAND_RSP with the same 19.
#
#   0      cmdID
#   1      subCmdID
#   2      dataControl: length in bits 0-4, 0x40 toggle, 0x80 more packets
#   3..18  data, a fixed 16-byte array whatever the length byte says
# ---------------------------------------------------------------------------

COMMAND_FRAME_LEN: Final = 19

# ---------------------------------------------------------------------------
# WiFi security types accepted by CHAR_WIFI_SETUP
# Source: CWifiSetup.WifiSecurityTypeEnum. Note there is no value 4.
# ---------------------------------------------------------------------------

WIFI_SECURITY_TYPES: Final[dict[str, int]] = {
    "open": 0,
    "wep": 1,
    "wpa": 2,
    "wpa2": 3,
    "wpa_enterprise": 5,
    "wpa3": 6,
    "wpa2_wpa3": 7,
}

WIFI_SECURITY_NAMES: Final[dict[int, str]] = {
    value: name for name, value in WIFI_SECURITY_TYPES.items()
}

# ---------------------------------------------------------------------------
# WiFi status reported by CHAR_WIFI_CURRENT_SETUP
# Source: com.sdataway.vertuonext.sdk.models.WifiCurrentSetup.WifiStatusEnum
#
# Only worth reading on a machine you might want to reach through Nespresso's
# cloud, since the remote maintenance functions go through AWS IoT and only
# arrive if the machine itself is online. A machine driven over Bluetooth alone
# will sit at not_configured, which is not a fault.
# ---------------------------------------------------------------------------

WIFI_STATUS_NAMES: Final[dict[int, str]] = {
    0: "not_connected",
    1: "connecting",
    2: "connected",
    8: "updating_combo_firmware",
    9: "updating_firmware",
    10: "updating_recipes",
    11: "cloud_onboarding",
    16: "connection_failed",
    17: "server_unreachable",
    18: "not_configured",
    20: "mqtt_init_error",
    21: "combo_firmware_update_failed",
    22: "firmware_update_failed",
    23: "recipe_update_failed",
    24: "market_not_set",
    25: "no_internet",
    26: "wrong_password",
    255: "unknown",
}

# ---------------------------------------------------------------------------
# Pairing key state
# Source: com.sdataway.vertuonext.sdk.models.CCMIDType.CMIDTypeEnum, which
# also appears as MachineStatus.PairingKeyState in both the Vertuo and the
# Barista SDK. The machine reports it in byte 0 of the onboard status
# characteristic and in bits 5-6 of the first status byte.
# ---------------------------------------------------------------------------

CMID_TYPE_NONE: Final = 0
CMID_TYPE_TEMPORARY: Final = 1
CMID_TYPE_FINAL: Final = 2
CMID_TYPE_UNDEFINED: Final = 3
CMID_TYPE_UNKNOWN: Final = 255

CMID_TYPE_NAMES: Final[dict[int, str]] = {
    CMID_TYPE_NONE: "none",
    CMID_TYPE_TEMPORARY: "temporary",
    CMID_TYPE_FINAL: "final",
    CMID_TYPE_UNDEFINED: "undefined",
    CMID_TYPE_UNKNOWN: "unknown",
}

# The two states in which the machine holds no usable token. The app puts them
# in the same bucket: after writing a token it reads this value back once a
# second until it leaves the pair, and gives up only after several attempts.
# So a machine sitting on UNDEFINED has not accepted a token, which is a very
# different thing from holding somebody else's.
CMID_TYPE_UNPAIRED: Final = frozenset({CMID_TYPE_NONE, CMID_TYPE_UNDEFINED})

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
VMINI_CHAR_FOTA_COMMAND: Final = "e0f00301-5c88-455f-98ba-cfe7db1a7d1d"
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

# Every machine on the Venus profile answers to the Vertuo Next family, so the
# family alone cannot tell a Pop from a Creatista. The platform code can: it
# appears in the serial number ("23222CV2f2001582072") and in the BLE name
# ("CV2_5443B29C51B2", "Vertuo_CV5_78421CC0B0EE").
#
# Source: MachineTypeKt.a in the APK. It also carries codes for the other two
# families, W10 and W11 for the Barista and MC1, MD1, MC2, MD2 for the machine
# it calls Vertuo Up, but those name the family we already have. The VENUS*
# and WHITE aliases beside them are cloud-side names that never reach us.
VERTUO_PLATFORM_NAMES: Final[dict[str, str]] = {
    "CV1": "Vertuo Next",
    "DV1": "Vertuo Next",
    "CV3": "Vertuo Next",
    "DV3": "Vertuo Next",
    "CV2": "Vertuo Pop",
    "DV2": "Vertuo Pop",
    "CV6": "Vertuo Pop+",
    "DV6": "Vertuo Pop+",
    "DV5": "Vertuo Lattissima",
    "CV5": "Vertuo Creatista",
}

# Vertuo platform codes with no BLE brew support. The Nespresso app itself
# offers no brew button for these models and the machine ignores every known
# brew command, so exposing a button that silently does nothing is worse than
# not exposing one. CV2 and DV2 are the Vertuo Pop, CV5 the Vertuo Creatista,
# which took every frame we have and stayed idle through all of them.
NO_BREW_PLATFORM_CODES: Final[tuple[str, ...]] = ("CV2", "DV2", "CV5")

# Characteristics holding the auth token, redacted out of the GATT dump. A
# diagnostics download is meant to be pasted into an issue, and this is the one
# value on the machine that is a credential rather than a fact about it.
AUTH_CHARS: Final[frozenset[str]] = frozenset(
    {
        BARISTA_CHAR_AUTH,
        VERTUO_CHAR_AUTH,
        VMINI_CHAR_PAIRING,
        VMINI_CHAR_MACHINE_TOKEN,
    }
)

# The command channel of each family: what a request is written to, and what
# the machine answers on.
COMMAND_CHANNELS: Final[dict[MachineFamily, tuple[str, str]]] = {
    MachineFamily.BARISTA: (BARISTA_CHAR_RECIPE_COMMAND, BARISTA_CHAR_RECIPE_RESPONSE),
    MachineFamily.VERTUO_NEXT: (VERTUO_CHAR_COMMAND_REQ, VERTUO_CHAR_COMMAND_RSP),
    MachineFamily.VMINI: (VMINI_CHAR_FOTA_COMMAND, VMINI_CHAR_FOTA_STATUS),
}
