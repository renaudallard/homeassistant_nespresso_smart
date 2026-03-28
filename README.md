# Nespresso Smart - Home Assistant Integration

A Home Assistant custom integration for Nespresso Smart coffee machines via Bluetooth Low Energy (BLE).

Built by reverse-engineering the Nespresso Smart Android app (v1.2.5).

## Supported Machines

| Family | BLE Service UUID | Machines |
|--------|-----------------|----------|
| Barista (Original) | `65241910-0253-11E7-93AE-92361F002671` | Barista |
| Vertuo Next (Venus) | `06AA1910-F22A-11E3-9DAA-0002A5D5C51B` | VertuoNext, VertuoPop, VertuoPopPlus, VertuoLattissima, VertuoCreatista, VertuoUp |
| VMini | `96600100-526E-4676-A11A-AF1EB848165B` | Vertuo Mini |

## Installation

Copy `custom_components/nespresso/` into your Home Assistant `config/custom_components/` directory.

Restart Home Assistant. The integration will auto-discover Nespresso machines via Bluetooth.

### Requirements

- Home Assistant 2026.03 or newer
- Bluetooth adapter accessible to Home Assistant
- Nespresso machine powered on and within BLE range

## Entities

### Sensors

| Entity | Barista | Vertuo Next | VMini | Description |
|--------|---------|-------------|-------|-------------|
| State | Yes | Yes | No | Machine operational state (ready, brewing, standby, etc.) |
| Firmware version | Yes | Yes | Yes | Current firmware version (diagnostic) |
| Hardware version | Yes | Yes | No | Hardware revision (diagnostic) |
| Water hardness | No | Yes | No | Configured water hardness level |

### Binary Sensors

| Entity | Barista | Vertuo Next | VMini | Description |
|--------|---------|-------------|-------|-------------|
| Error | Yes | Yes | No | Machine has an active error |
| Water tank empty | No | Yes | No | Water tank needs refilling |
| Descaling needed | No | Yes | No | Machine needs descaling |
| Cleaning needed | No | Yes | No | Machine needs cleaning |
| Capsule container full | No | Yes | No | Used capsule container is full |

### Device Info

Each machine is registered as a device with manufacturer, model, serial number, and firmware version.

## How It Works

The integration connects to the machine via BLE every 60 seconds, reads the status characteristics, and disconnects. This avoids blocking the Nespresso mobile app from connecting.

Machine family is detected automatically from the advertised BLE service UUID during discovery.

## Reverse Engineering Documentation

Detailed protocol documentation from the APK decompilation is available under [docs/](docs/).

## Limitations

- **No brewing commands**: v1 is read-only. Sending commands to the machine requires real hardware testing for safety.
- **VMini limited**: Only device info is available. The VMini uses a separate JSON-based protocol for operational data.
- **BLE range**: The machine must be within Bluetooth range of the Home Assistant host.
- **Single client**: Only one BLE client can connect at a time. If the Nespresso app is connected, HA will retry on the next poll.
