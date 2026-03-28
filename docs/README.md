# Nespresso Smart Machines - Reverse Engineering Documentation

Documentation produced by decompiling the **Nespresso Smart** Android app (v1.2.5, package `com.nestle.us.nespresso.nespressosmartmachines`).

## Contents

| Document | Description |
|----------|-------------|
| [BLE Protocol](ble-protocol.md) | Bluetooth Low Energy services, characteristics, UUIDs, and command protocol |
| [API Endpoints](api-endpoints.md) | REST API endpoints, environment URLs, and cloud service integration |
| [Authentication](authentication.md) | OAuth2/PKCE authentication flow and token management |
| [AWS IoT](aws-iot.md) | AWS IoT MQTT integration, telemetry, and device shadow |
| [Machine Models](machine-models.md) | Supported machine types, capabilities, and hardware families |
| [Data Models](data-models.md) | Enums, status codes, error codes, and data structures |
| [Architecture](architecture.md) | App architecture, dependency injection, and third-party SDKs |

## App Overview

- **Package:** `com.nestle.us.nespresso.nespressosmartmachines`
- **Version:** 1.2.5 (version code 1938)
- **Min SDK:** 26 (Android 8.0)
- **Target SDK:** 36
- **BLE SDK vendor:** SDataway (packages `com.sdataway.*`)

## Supported Machine Families

The app communicates with three distinct hardware families, each with its own BLE protocol:

| Family | SDK Package | BLE UUID Prefix | Machines |
|--------|------------|-----------------|----------|
| Barista (Original) | `com.sdataway.barista` | `6524xxxx-0253-11E7-...` | Barista |
| Vertuo Next (Venus) | `com.sdataway.vertuonext` | `06AAxxxx-F22A-11E3-...` | VertuoNext, VertuoPop, VertuoPopPlus, VertuoLattissima, VertuoCreatista, VertuoUp |
| VMini | `com.sdataway.vmini` | `966001xx-526E-4676-...` / `E0F00xxx-5C88-455F-...` | Vertuo Mini (WiFi-enabled) |

## Permissions

The app requests the following Android permissions:

- `BLUETOOTH`, `BLUETOOTH_ADMIN`, `BLUETOOTH_SCAN`, `BLUETOOTH_CONNECT` - BLE communication
- `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION` - BLE scanning (Android requirement)
- `ACCESS_WIFI_STATE`, `ACCESS_NETWORK_STATE` - WiFi configuration
- `INTERNET` - Cloud API communication
- `CAMERA` - QR code scanning for pairing
- `POST_NOTIFICATIONS` - Push notifications
- `USE_BIOMETRIC`, `USE_FINGERPRINT` - Biometric authentication
- `WAKE_LOCK` - Background operations
- `RECEIVE_BOOT_COMPLETED` - Boot receiver for push notifications
- `FOREGROUND_SERVICE` - Long-running BLE operations
