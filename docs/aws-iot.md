# AWS IoT Integration Documentation

WiFi-connected Nespresso machines communicate with the cloud via AWS IoT Core using MQTT.

## Table of Contents

- [Architecture](#architecture)
- [Endpoint Configuration](#endpoint-configuration)
- [MQTT Communication](#mqtt-communication)
- [Message Types](#message-types)
- [Connection States](#connection-states)
- [IoT Machine Model](#iot-machine-model)
- [Device Shadow](#device-shadow)
- [Error Handling](#error-handling)

---

## Architecture

```
Nespresso Machine (WiFi)
    |
    | MQTT over TLS
    v
AWS IoT Core
    |
    +-- Device Shadow (reported/desired state)
    +-- MQTT Topics (telemetry, commands)
    |
    v
Nespresso Cloud API (ECAPI)
    |
    v
Mobile App (REST API)
```

Machines with WiFi (Vertuo Next, VMini) connect directly to AWS IoT Core. The mobile app interacts with machines indirectly through the ECAPI cloud layer, which reads/writes the AWS IoT device shadow.

---

## Endpoint Configuration

Source: `com.nestle.mse.iot.commons.models.EndpointConfiguration`

### Configuration Structure

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| keyId | String | Non-empty | Configuration key identifier |
| url | String | Valid URL pattern | AWS IoT endpoint URL |
| accessKeyId | String | Max 20 chars | AWS Access Key ID |
| accessKeySecret | String | Max 40 chars | AWS Secret Access Key |

### URL Validation Pattern

```
(http(s)?:\/\/)?(www.)?[-a-zA-Z0-9\.?]*
```

### Configuration Loading

Source: `com.nestle.mse.iot.commons.models.IotSdkHubClientConfiguration`

Configuration is stored as an AES-encrypted JSON string. The factory method decrypts it at runtime:

```
1. Receive encrypted configuration strings
2. Decrypt using AES cipher (com.nestle.mse.iot.commons.Crypto)
3. Parse JSON into List<EndpointConfiguration>
4. Validate all fields (URL format, key lengths)
5. Create IotSdkHubClientConfiguration with endpoint list
```

### Credential Provider

Source: `com.nestle.mse.iot.commons.models.IotCredentialsProvider`

Wraps `EndpointConfiguration` credentials as `BasicAWSCredentials` for the AWS SDK:
- Implements `AWSCredentialsProvider` interface
- Returns `BasicAWSCredentials(accessKeyId, accessKeySecret)`

---

## MQTT Communication

Source: `com.amazonaws.iot.AWSIotMqttManager`

### Client Configuration

The app uses the AWS IoT Android SDK's MQTT manager:

| Parameter | Description |
|-----------|-------------|
| Endpoint | AWS IoT endpoint URL from configuration |
| Client ID | Unique device/machine identifier |
| Credentials | AWSCredentialsProvider from endpoint config |
| QoS | Configurable per subscription (AWSIotMqttQos) |

### Topic Management

Source: `com.nestle.mse.iot.commons.TopicHelper`

MQTT topics are constructed dynamically based on machine identifiers and message types.

### Quality of Service

| QoS Level | Description |
|-----------|-------------|
| QoS 0 | At most once (fire and forget) |
| QoS 1 | At least once (acknowledged delivery) |

---

## Message Types

Source: `com.nestle.mse.iot.commons.models.MessageType`

| Type | Value | Description |
|------|-------|-------------|
| TELEMETRY | 1 | Machine status and sensor data |
| CHECK_FOR_UPDATES | 4 | Firmware update availability check |
| ANALYTICS | 16 | Usage analytics and metrics |

### Message Construction

Source: `com.nestle.mse.iot.commons.TelemetryMessageGenerator`, `MessageBuilder`

Messages are built using structured builders and published to the appropriate MQTT topic.

---

## Connection States

Source: `com.nestle.mse.iot.commons.models.ConnectionStatus`

| State | Description |
|-------|-------------|
| CONNECTED | Active MQTT connection established |
| RECONNECTING | Connection lost, automatic reconnection in progress |
| CONNECTING | Initial connection attempt |
| DISCONNECTED | No active connection |

### MQTT Connection Lifecycle

Source: `com.amazonaws.iot.AWSIotMqttClientStatusCallback`, `MqttManagerConnectionState`

```
DISCONNECTED -> CONNECTING -> CONNECTED
                                  |
                                  v (connection lost)
                             RECONNECTING -> CONNECTED
                                  |
                                  v (give up)
                             DISCONNECTED
```

---

## IoT Machine Model

Source: `com.nestle.p060us.nespresso.iot.model`

### IoTMachine

Represents a discovered BLE machine:

| Field | Type | Description |
|-------|------|-------------|
| brandId | Int | Brand identifier |
| name | String | Machine display name |
| serialNumber | String | Device serial number |
| type | String | Machine type identifier |
| macAddress | String | BLE MAC address (nullable) |
| rssi | Integer | BLE signal strength (nullable) |
| firmwareInfo | IoTMachineFirmwareInfo | Firmware details (nullable) |

### IoTMachineStatus

Comprehensive machine status combining BLE and cloud data:

| Field | Type | Description |
|-------|------|-------------|
| bootloaderActive | Boolean | Bootloader mode active |
| pairingKeyState | IoTPairingKeyState | Current pairing state |
| errorPresent | Boolean | Error condition active |
| descalingNeeded | Boolean | Descaling alert |
| waterTankEmpty | Boolean | Water tank empty |
| machineStateVenus | IoTMachineState | Vertuo machine state (28 states) |
| errorInformation | IoTErrorInformationEnum | Error category |
| bleEnabled | Boolean | BLE active |
| machineState | MachineState | Barista machine state (9 states) |
| isMotorRunning | Boolean | Motor active |
| isInductionHeatingActive | Boolean | Heater active |
| isLastCmidValid | Boolean | Last capsule ID valid |
| isSetupComplete | Boolean | Initial setup done |
| iotReportedStatus | IoTReportedStatus | Cloud-reported status (nullable) |

### IoTReportedStatus

Status fields reported by the machine through the cloud shadow:

| Field | Type | Description |
|-------|------|-------------|
| machineStatus | String | Current operational state |
| descalingAlert | Boolean | Descaling needed |
| lastCoffeeFamilyID | Integer | Last capsule family brewed |
| volumeCustomization | String | Custom volume settings |
| temperatureCustomization | String | Custom temperature settings |
| waterHardness | Integer | Water hardness level |
| errorCode | String | Current error code |
| firstCoffee | Boolean | First coffee brewed flag |
| firstRinsing | Boolean | First rinse done flag |
| recipeTag | String | Active recipe identifier |

---

## Device Shadow

### VMini Shadow Service

The VMini uses a dedicated BLE Shadow Service to synchronize state with the cloud:

| Characteristic | UUID | Purpose |
|---------------|------|---------|
| CHAR_SHADOWHEADER | `E0F00501-5C88-455F-98BA-CFE7DB1A7D1D` | Shadow metadata |
| CHAR_SHADOWUPDATE | `E0F00502-5C88-455F-98BA-CFE7DB1A7D1D` | Shadow state updates |

The shadow provides a "reported" state (from machine) and "desired" state (from cloud/app), enabling asynchronous control even when the machine is offline.

### WiFi Configuration for IoT

Machines require WiFi to connect to AWS IoT. WiFi setup is done over BLE:

1. App writes WiFi SSID and password to WiFi configuration characteristics
2. Machine connects to WiFi network
3. Machine establishes MQTT connection to AWS IoT Core
4. Machine begins reporting status via device shadow

---

## Error Handling

### Hub Exit Codes

Source: `com.nestle.mse.iot.commons.models.HubExitCode`

| Code | Name | Description |
|------|------|-------------|
| -300 | GENERIC_DOWNLOAD_PHASE_ERROR | General download failure |
| -301 | DOWNLOAD_NETWORK_ERROR | Network error during download |
| -302 | DOWNLOAD_TIMEOUT | Download timed out |
| -303 | INVALID_DOWNLOAD_ADDRESS | Bad download URL |
| -304 | FILE_STORAGE_FAILED | Could not save downloaded file |
| -402 | DATA_DECRYPTION_FAILED | Failed to decrypt received data |

### Delivery Status

Source: `com.nestle.mse.iot.commons.models.DeliveryStatus`

| Status | Description |
|--------|-------------|
| SUCCESS | Message delivered successfully |
| FAIL | Message delivery failed |

### IoT Device Types

The DI module registers three machine type providers:

| Provider | Machine Family |
|----------|---------------|
| VMini | Vertuo Mini (WiFi-first) |
| VertuoNext | Vertuo Venus line |
| Barista | Original/Barista line |
