<p align="center">
  <img src="images/logo.png" alt="Nespresso Smart" width="120">
</p>

# Nespresso Smart - Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/renaudallard/homeassistant_nespresso_smart)
[![Release](https://img.shields.io/github/v/release/renaudallard/homeassistant_nespresso_smart)](https://github.com/renaudallard/homeassistant_nespresso_smart/releases)
[![Validate](https://github.com/renaudallard/homeassistant_nespresso_smart/actions/workflows/validate.yml/badge.svg)](https://github.com/renaudallard/homeassistant_nespresso_smart/actions/workflows/validate.yml)

A Home Assistant custom integration for Nespresso Smart coffee machines via Bluetooth Low Energy (BLE).

Built by reverse-engineering the Nespresso Smart Android app (v1.2.5).

---

## Supported Machines

| Family | BLE Service UUID | Machines |
|--------|-----------------|----------|
| Barista (Original) | `65241910-0253-11E7-93AE-92361F002671` | Barista |
| Vertuo Next (Venus) | `06AA1910-F22A-11E3-9DAA-0002A5D5C51B` | VertuoNext, VertuoPop, VertuoPopPlus, VertuoLattissima, VertuoCreatista, VertuoUp |
| VMini | `96600100-526E-4676-A11A-AF1EB848165B` | Vertuo Mini |

## Installation

### HACS (recommended)

1. Open HACS in your Home Assistant instance
2. Go to **Integrations**
3. Click the three dots in the top right corner and select **Custom repositories**
4. Add `https://github.com/renaudallard/homeassistant_nespresso_smart` with category **Integration**
5. Click **Add**
6. Search for "Nespresso Smart" in HACS and install it
7. Restart Home Assistant

### Manual

Copy `custom_components/nespresso/` into your Home Assistant `config/custom_components/` directory and restart Home Assistant.

### Setup

After installation, the integration will auto-discover Nespresso machines via Bluetooth. Ensure your machine is powered on and within BLE range. No manual configuration is needed.

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

Each machine is registered as a device with manufacturer, model, serial number, firmware version, and hardware version.

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
