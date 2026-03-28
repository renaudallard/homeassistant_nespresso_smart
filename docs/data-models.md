# Data Models Documentation

Complete reference of all enums, status codes, error codes, and data structures found in the decompiled Nespresso Smart app.

## Table of Contents

- [Machine States](#machine-states)
- [Pairing States](#pairing-states)
- [Error Enums](#error-enums)
- [Failure Types](#failure-types)
- [Failure Tips](#failure-tips)
- [Failure Actions](#failure-actions)
- [Push Notification Types](#push-notification-types)
- [IoT Error Codes](#iot-error-codes)
- [SDK Error Types](#sdk-error-types)
- [Machine Error Enums](#machine-error-enums)
- [WiFi Types](#wifi-types)
- [Constants](#constants)

---

## Machine States

### Barista Machine States

Source: `com.sdataway.barista.sdk.models.MachineStatus.MachineState`

| Value | State | Description |
|-------|-------|-------------|
| 0 | STANDBY | Machine is in standby/sleep mode |
| 1 | READY | Machine is ready to brew |
| 2 | RECIPE_EXECUTING | Currently brewing a recipe |
| 3 | LOCAL_SETTINGS_MODE | User is changing settings on machine |
| 4 | ERROR | Machine has an error condition |
| 5 | OVERHEATED | Machine is overheated |
| 6 | OUT_OF_THE_BOX_SETTINGS | Initial setup mode |
| 7 | RECIPE_PAUSED | Brewing is paused |
| 255 | UNKNOWN | State could not be determined |

### Vertuo Next Machine States (Venus)

Source: `com.sdataway.vertuonext.sdk.models.MachineStatus.MachineState`

| Value | State | Description |
|-------|-------|-------------|
| 0 | FACTORY_RESET | Factory reset in progress |
| 1 | HEATUP | Heating up |
| 2 | READY | Ready to brew |
| 3 | DESCALING_READY | Ready for descaling |
| 4 | BREWING | Currently brewing |
| 5 | CLEANING | Cleaning cycle active |
| 6 | DESCALING | Descaling cycle active |
| 7 | EMPTYING | Emptying water system |
| 8 | DEVICE_ERROR | Machine error |
| 9 | POWER_SAVE | Power saving mode |
| 10 | COOLDOWN | Cooling down |
| 11 | SERVICE_MODE | Service/maintenance mode |
| 12 | STANDBY | Standby mode |
| 13 | UPDATING | Firmware update in progress |
| 14 | RINSING | Rinsing cycle active |
| 17 | CAPSULE_READING | Reading capsule barcode |
| 18 | DESCALE_SEQUENCE_DECODING | Decoding descaling sequence |
| 19 | TANK_EMPTY | Water tank is empty |
| 20 | DESCALING_PAUSED | Descaling paused |
| 21 | INITIALIZATION | Machine initializing |
| 22 | RINSING_READY | Ready for rinsing |
| 23 | MAINTENANCE_MENU | In maintenance menu |
| 26 | CLEANING_PAUSED | Cleaning paused |
| 33 | EMPTYING_READY | Ready for emptying |
| 34 | CLEANING_READY | Ready for cleaning |
| 35 | READY_OLD_CAPSULE | Ready but capsule is old/used |
| 36 | RINSING_PAUSED | Rinsing paused |
| 255 | UNKNOWN | State could not be determined |

### IoT Machine States (High-Level)

Source: `com.nestle.p060us.nespresso.iot.model.IoTMachineState`

Same as Vertuo Next states. Used as the unified state model for cloud-connected machines.

### Barista-Style States (Simplified)

Source: `com.nestle.p060us.nespresso.iot.model.MachineState`

Same as Barista machine states above. Used as the simplified state model for Original line machines.

---

## Pairing States

### Barista / Vertuo Next

Source: `com.sdataway.barista.sdk.models.MachineStatus.PairingKeyState`

| Value | State | Description |
|-------|-------|-------------|
| 0 | NONE | No pairing key present |
| 1 | TEMPORARY | Temporary pairing key (pairing in progress) |
| 2 | FINAL | Permanent pairing key established |
| 3 | UNDEFINED | Pairing state undefined |
| 255 | UNKNOWN | Could not determine pairing state |

### VMini

Source: `com.sdataway.vmini.sdk.models.PairingStatus.PairingStatusEnum`

| Value | State | Description |
|-------|-------|-------------|
| 0 | NOT_PAIRED | Machine is not paired |
| 1 | PAIRED | Machine is paired |
| 2 | PAIRING_PROCESS_ONGOING | Pairing currently in progress |
| 255 | UNKNOWN | Could not determine pairing state |

### IoT Pairing Key State

Source: `com.nestle.p060us.nespresso.iot.model.IoTPairingKeyState`

| Value | State |
|-------|-------|
| UNKNOWN | Unknown |
| NONE | No pairing key |
| TEMPORARY | Temporary key |
| FINAL | Permanent key |
| UNDEFINED | Undefined state |

---

## Error Enums

### Error Information (Barista)

Source: `com.sdataway.barista.sdk.models.ErrorInformation`

#### ErrorInformationEnum

| Value | Category | Description |
|-------|----------|-------------|
| 0 | NONE | No error |
| 1 | POWERLINE | Power supply error |
| 2 | MMI | Man-Machine Interface error |
| 3 | MAINSYSTEM | Main controller error |
| 4 | SENSOR | Sensor malfunction |
| 5 | ACTUATOR | Actuator malfunction |
| 6 | OTHER | Uncategorized error |
| 255 | UNKNOWN | Error type unknown |

#### ErrorSelectionIndexEnum

| Value | Selection | Description |
|-------|-----------|-------------|
| 0 | CURRENT_ACTIVE_ERROR | Currently active error |
| 1 | ERROR_PRESENT_IN_LIST | Error exists in error log |
| 254 | INVALID_DATA | Invalid error data |
| 255 | UNKNOWN | Unknown selection state |

### Error Information (Vertuo Next)

Source: `com.sdataway.vertuonext.sdk.models.ErrorInformation`

Same structure as Barista, with slightly different naming:

| Value | Category |
|-------|----------|
| 0 | NONE |
| 1 | POWER_LINE |
| 2 | MMI |
| 3 | MAIN_SYSTEM |
| 4 | SENSOR |
| 5 | ACTUATOR |
| 6 | OTHER |
| 255 | UNKNOWN |

### IoT Error Information

Source: `com.nestle.p060us.nespresso.iot.model.IoTErrorInformationEnum`

| Value | Category |
|-------|----------|
| UNKNOWN | Unknown |
| NONE | No error |
| POWER_LINE | Power supply |
| MMI | Interface |
| MAIN_SYSTEM | Main controller |
| SENSOR | Sensor |
| ACTUATOR | Actuator |
| OTHER | Other |

---

## Failure Types

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.p063ui.screen.home.machinecare.FailureType`

| Enum Value | Description |
|------------|-------------|
| NONE | No failure |
| NO_MACHINE_CONNECTION | Cannot connect to machine |
| FIRMWARE_UPDATE_IN_PROGRESS | Blocked by ongoing firmware update |
| MACHINE_BUSY | Machine is busy with another operation |
| SOMETHING_WENT_WRONG | Generic error |
| CONNECTION_LOST | BLE connection dropped |
| NESPRESSO_SYSTEMS_BUSY | Cloud backend busy |
| LEVER_OPEN | Machine lever is open |
| CAPSULE_DETECTED | Capsule present when not expected |
| BUTTON_PRESSED | Unexpected button press |
| WATER_EXCEED | Water overflow detected |
| COOLDOWN | Machine needs to cool down |
| WATER_TANK_EMPTY | Water tank is empty |
| MACHINE_FAILURE | Hardware failure |
| NO_WATER_FLOW | Water flow problem |
| MAINTENANCE_ABORTED | Maintenance cycle was aborted |

### Machine Failure Type

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.p063ui.screen.home.machinecare.MachineFailureType`

| Value | Description |
|-------|-------------|
| INTERRUPTED | Operation was interrupted |
| ABORTED | Operation was aborted |
| NONE | No failure |

### Machine Error (UI Level)

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.p063ui.screen.home.machinecare.MachineError`

| Value | Description |
|-------|-------------|
| MACHINE_NOT_READY | Machine not in ready state |
| MACHINE_HEAD_UNLOCKED | Brewing head is not locked |
| CAPSULE_DETECTED | Unexpected capsule present |
| MACHINE_NOT_CONNECTED | BLE not connected |
| SOMETHING_WENT_WRONG | Generic error |
| NO_INTERNET_CONNECTION | No network connectivity |

### Failure Tracking

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.p063ui.screen.home.machinecare.FailureTracking`

| Value | Description |
|-------|-------------|
| NO_CONNECTION | Connection failure tracked |
| SOMETHING_WRONG | Generic failure tracked |
| PROCESS_ABORTED | Process abort tracked |
| PROCESS_INTERRUPTED | Process interruption tracked |

---

## Failure Tips

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.p063ui.screen.home.machinecare.FailureTip`

Troubleshooting guidance shown to users during failures:

| Tip | Description |
|-----|-------------|
| HEAD_CHECK | Check the brewing head |
| WIFI_CHECK | Check WiFi connection |
| POWER_ON | Ensure machine is powered on |
| CUSTOMER_SUPPORT | Contact Nespresso support |
| FW_UPDATE | Firmware update needed |
| COFFEE_BUTTON | Press the coffee button |
| OPEN_CLOSE_LEVER | Open and close the lever |
| CLOSE_THE_LEVER | Close the lever |
| USE_VERTUO_CAPSULE | Use a compatible Vertuo capsule |
| COFFEE_BUTTON_AGAIN | Press coffee button again |
| LEVER_CHECK | Check lever position |
| CAPSULE_DETECTED | Remove detected capsule |
| WATER_EXCEED | Water overflow - empty drip tray |
| COOLDOWN | Wait for cooldown |
| WATER_TANK_EMPTY | Refill water tank |
| MACHINE_FAILURE | Hardware failure detected |
| WATER_TANK_ATTACHED | Ensure water tank is attached |
| WATER_TANK_NOT_FILLED | Fill the water tank |
| NO_WATER_FLOW | Check water flow path |
| NO_WATER_FLOW_SUPPORT | Water flow issue - contact support |
| MACHINE_RESTART | Restart the machine |
| COFFEE_BUTTON_READY | Press button when machine is ready |
| WIFI_LED | Check WiFi LED indicator |
| DESCALING_FAILURE | Descaling process failed |

---

## Failure Actions

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.p063ui.screen.home.machinecare.FailureAction`

| Action | Description |
|--------|-------------|
| TRY_AGAIN | Retry the failed operation |
| CUSTOMER_SUPPORT | Navigate to customer support |
| DISMISS | Dismiss the error |
| RESTART_PROCESS | Restart the maintenance process |
| GO_TO_PROCESS | Navigate to the process screen |
| RESUME | Resume interrupted operation |

### Interrupt Actions

Source: `InterruptAction`

| Action | Description |
|--------|-------------|
| RESUME | Resume the interrupted process |
| RESTART_PROCESS | Restart from the beginning |

### Interrupt Check Types

Source: `InterruptCheckType`

| Type | Description |
|------|-------------|
| WATER_TANK_CHECK | Water tank needs attention |
| HEAD_CHECK | Brewing head needs attention |
| LEVER_CHECK | Lever position check |
| BUTTON_PRESSED | Button was pressed during process |
| COOLDOWN | Cooling down required |
| CAPSULE_DETECTED | Remove capsule before continuing |
| CAPSULE_NOT_SUPPORTED | Incompatible capsule |
| WATER_EXCEEDED | Water overflow condition |
| MACHINE_FAILURE | Hardware failure during process |

---

## Push Notification Types

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.domain.model.PushNotificationType`

33-value enum for machine event notifications:

| Type | Description |
|------|-------------|
| DescalingAlert | Descaling required alert |
| WaterTankEmpty | Water tank is empty |
| OperationRequestedWhileHandleOpen | Operation attempted with handle open |
| BrewingStarted | Coffee brewing started |
| BrewingEnded | Coffee brewing completed |
| RinsingStarted | Rinsing cycle started |
| RinsingEnded | Rinsing cycle completed |
| EmptyingStarted | Emptying started |
| EmptyingEnded | Emptying completed |
| DescalingStarted | Descaling started |
| DescalingEnded | Descaling completed |
| CapsuleDetected | Capsule inserted |
| CapsuleReadingError | Error reading capsule barcode |
| CapsuleNotSupported | Capsule type not supported |
| TemperatureError | Temperature sensor error |
| WaterFlowError | Water flow problem |
| UserInteractionConflict | Conflicting user action |
| (+ additional alternative types for event grouping) |

---

## IoT Error Codes

Source: `com.nestle.p060us.nespresso.iot.model.IoTErrorCode`

| Code | Description |
|------|-------------|
| ERROR_1301 | Error category 1301 |
| ERROR_1303 | Error category 1303 |
| ERROR_1304 | Error category 1304 |
| ERROR_1305 | Error category 1305 |
| ERROR_1306 | Error category 1306 |
| ERROR_177010 | Error category 177010 |
| ERROR_177011 | Error category 177011 |
| ERROR_177014 | Error category 177014 |
| ERROR_177016 | Error category 177016 |
| ERROR_177019 | Error category 177019 |
| ERROR_177026 | Error category 177026 |

---

## SDK Error Types

Source: `com.sdataway.barista.sdk.models.SDKError.SDKErrorType`

24 error types for the BLE SDK:

### SDK State Errors

| Error | Description |
|-------|-------------|
| notInitialized | SDK not initialized |
| alreadyInitialized | SDK already initialized |

### Connection Errors

| Error | Description |
|-------|-------------|
| connectionFailed | BLE connection failed |
| notConnected | No active connection |
| alreadyConnected | Already connected to a device |

### Scan Errors

| Error | Description |
|-------|-------------|
| failedToStop | Scan failed to stop |
| alreadyRunning | Scan already in progress |

### BLE Characteristic Errors

| Error | Description |
|-------|-------------|
| bleTagError | BLE tag identification error |
| readError | Characteristic read failed |
| writeError | Characteristic write failed |

### BST Transaction Errors

| Error | Description |
|-------|-------------|
| ongoing | BST transfer in progress |
| failed | BST transfer failed |
| notReady | BST not ready to transfer |
| notStarted | BST transfer not started |
| notCompleted | BST transfer incomplete |

### Device State Errors

| Error | Description |
|-------|-------------|
| notPaired | Device is not paired |
| busy | Device is busy |
| inStandby | Device is in standby |

### Other Errors

| Error | Description |
|-------|-------------|
| exceptionError | Unexpected exception |

---

## Machine Error Enums

### Water Hardness Check Types

Source: `WaterHardnessCheckType`

| Type | Description |
|------|-------------|
| UNPLUG | Unplug the machine first |
| POSITION | Position check required |
| BLUETOOTH | BLE connection check |

### Water Hardness Option State

Source: `WHOptionState`

```
WHOptionState {
    levelValue: Integer  // hardness level value
    selected: Boolean    // whether this option is selected
}
```

---

## WiFi Types

Source: `com.nestle.p060us.nespresso.iot.model`

### IoTWiFiSecurity / WifiSecurityType

WiFi security type enums for network configuration during machine pairing.

### IoTWiFiDetails

WiFi network details discovered during scanning:
- SSID
- Security type
- Signal strength

### IoTIPConfiguration

Network IP configuration for the machine's WiFi connection.

---

## Constants

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.util.Constants`

| Constant | Value | Description |
|----------|-------|-------------|
| DEFAULT_IOT_IP_VALUE | "255.255.255.255" | Default/unset IP address |
| ALL_ZERO_IOT_IP_VALUE | "0.0.0.0" | Zero IP address |
| LOADING_DELAY_MILLIS | 2000 | Loading screen delay (ms) |
| LANGUAGE_BANNER_DELAY_MS | 3000 | Language banner display time (ms) |
| MAX_RECIPES_STORED | 13 | Maximum recipes on machine |
| NULL_COFFEE_FAMILY_ID | 255 | Null/no capsule family |
| STATUS_OK | "OK" | Success status string |
| STATUS_ERROR | "ERROR" | Error status string |
| FAILED_TO_LOAD_RECIPES | "Failed to load recipes" | Recipe loading error |

### Machine Care Failure Codes

Source: `MachineCareFailureCodes`

| Constant | Code | Description |
|----------|------|-------------|
| NO_MACHINE_CONNECTION | "17509" | Connection failure |
| MACHINE_BUSY | "17519" | Machine busy |
