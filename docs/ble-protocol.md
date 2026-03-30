# BLE Protocol Documentation

The Nespresso Smart app communicates with coffee machines over Bluetooth Low Energy (BLE). Three distinct protocol families exist, one per hardware generation.

## Table of Contents

- [Barista (Original Line)](#barista-original-line)
- [Vertuo Next (Venus Line)](#vertuo-next-venus-line)
- [VMini (Vertuo Mini)](#vmini-vertuo-mini)
- [Command Protocol](#command-protocol)
- [Byte Sequence Transfer (BST) Protocol](#byte-sequence-transfer-bst-protocol)
- [Machine Status Byte Format](#machine-status-byte-format)
- [Machine Info Format](#machine-info-format)
- [Encryption](#encryption)
- [Connection Management](#connection-management)

---

## Barista (Original Line)

Source: `com.sdataway.barista.sdk.GATTattributes.DeviceGATTAttributes`

### Services

| Service | UUID |
|---------|------|
| BASIC_SERVICE | `65241910-0253-11E7-93AE-92361F002671` |
| MACHINE_SERVICE | `65241920-0253-11E7-93AE-92361F002671` |
| ERROR_INFORMATION_SERVICE | `65241930-0253-11E7-93AE-92361F002671` |
| MILK_RECIPE_SERVICE | `65241990-0253-11E7-93AE-92361F002671` |
| HMI_SERVICE | `652419A0-0253-11E7-93AE-92361F002671` |

### Characteristics

| Characteristic | UUID | Access |
|---------------|------|--------|
| CHAR_PROFILE_VERSION | `65243A11-0253-11E7-93AE-92361F002671` | Read |
| CHAR_MACHINE_STATUS | `65243A12-0253-11E7-93AE-92361F002671` | Read/Notify |
| CHAR_ERROR_SELECTION | `65243A13-0253-11E7-93AE-92361F002671` | Write |
| CHAR_RECIPE_SELECTION | `65243A19-0253-11E7-93AE-92361F002671` | Write |
| CHAR_LANGUAGE | `65243A1A-0253-11E7-93AE-92361F002671` | Write |
| CHAR_MACHINE_INFO | `65243A21-0253-11E7-93AE-92361F002671` | Read |
| CHAR_MACHINE_SPECIFIC_PARAMS | `65243A22-0253-11E7-93AE-92361F002671` | Read/Write |
| CHAR_ERROR_INFORMATION | `65243A23-0253-11E7-93AE-92361F002671` | Read |
| CHAR_RECIPE_COMMAND | `65243A29-0253-11E7-93AE-92361F002671` | Write |
| CHAR_SERIAL_NUMBER | `65243A31-0253-11E7-93AE-92361F002671` | Read |
| CHAR_RECIPE_RESPONSE | `65243A39-0253-11E7-93AE-92361F002671` | Read/Notify |
| CHAR_CMID | `65243A41-0253-11E7-93AE-92361F002671` | Read/Write |
| CHAR_COMMAND_REQ | `65243A42-0253-11E7-93AE-92361F002671` | Write |
| CHAR_RECIPE_INFORMATION | `65243A49-0253-11E7-93AE-92361F002671` | Read |
| CHAR_CMID_TYPE | `65243A51-0253-11E7-93AE-92361F002671` | Read |
| CHAR_COMMAND_RSP | `65243A52-0253-11E7-93AE-92361F002671` | Read/Notify |
| CHAR_TX_LEVEL_CHANGE_REQUEST | `65243A61-0253-11E7-93AE-92361F002671` | Write |

---

## Vertuo Next (Venus Line)

Source: `com.sdataway.vertuonext.sdk.GATTattributes.DeviceGATTAttributes`

### Services

| Service | UUID |
|---------|------|
| BASIC_SERVICE | `06AA1910-F22A-11E3-9DAA-0002A5D5C51B` |
| MACHINE_SERVICE | `06AA1920-F22A-11E3-9DAA-0002A5D5C51B` |
| ERROR_INFORMATION_SERVICE | `06AA1930-F22A-11E3-9DAA-0002A5D5C51B` |
| USER_SETTINGS_SERVICE | `06AA1940-F22A-11E3-9DAA-0002A5D5C51B` |
| WIFI_CONFIGURATION_SERVICE | `06AA1990-F22A-11E3-9DAA-0002A5D5C51B` |

### Characteristics

| Characteristic | UUID | Access |
|---------------|------|--------|
| CHAR_PROFILE_VERSION | `06AA3A11-F22A-11E3-9DAA-0002A5D5C51B` | Read |
| CHAR_MACHINE_STATUS | `06AA3A12-F22A-11E3-9DAA-0002A5D5C51B` | Read/Notify |
| CHAR_ERROR_SELECTION | `06AA3A13-F22A-11E3-9DAA-0002A5D5C51B` | Write |
| CHAR_WIFI_SETUP | `06AA3A19-F22A-11E3-9DAA-0002A5D5C51B` | Write |
| CHAR_MACHINE_INFO | `06AA3A21-F22A-11E3-9DAA-0002A5D5C51B` | Read |
| CHAR_MACHINE_SPECIFIC_PARAMS | `06AA3A22-F22A-11E3-9DAA-0002A5D5C51B` | Read/Write |
| CHAR_ERROR_INFORMATION | `06AA3A23-F22A-11E3-9DAA-0002A5D5C51B` | Read |
| CHAR_WIFI_CURRENT_SETUP | `06AA3A29-F22A-11E3-9DAA-0002A5D5C51B` | Read |
| CHAR_SERIAL_NUMBER | `06AA3A31-F22A-11E3-9DAA-0002A5D5C51B` | Read |
| CHAR_WIFISCANSELECTION | `06AA3A39-F22A-11E3-9DAA-0002A5D5C51B` | Write |
| CHAR_CMID | `06AA3A41-F22A-11E3-9DAA-0002A5D5C51B` | Read/Write |
| CHAR_COMMAND_REQ | `06AA3A42-F22A-11E3-9DAA-0002A5D5C51B` | Write |
| CHAR_GENERAL_USER_SETTINGS | `06AA3A44-F22A-11E3-9DAA-0002A5D5C51B` | Read/Write |
| CHAR_WIFISCANRESULT | `06AA3A49-F22A-11E3-9DAA-0002A5D5C51B` | Read/Notify |
| CHAR_CMID_TYPE | `06AA3A51-F22A-11E3-9DAA-0002A5D5C51B` | Read |
| CHAR_COMMAND_RSP | `06AA3A52-F22A-11E3-9DAA-0002A5D5C51B` | Read/Notify |
| CHAR_TX_LEVEL_CHANGE_REQUEST | `06AA3A61-F22A-11E3-9DAA-0002A5D5C51B` | Write |
| CHAR_IOTMARKETNAME | `06AA3A79-F22A-11E3-9DAA-0002A5D5C51B` | Read |

---

## VMini (Vertuo Mini)

Source: `com.sdataway.vmini.sdk.GATTattributes.DeviceGATTAttributes`

### Services

| Service | UUID |
|---------|------|
| BASIC_SERVICE | `96600100-526E-4676-A11A-AF1EB848165B` |
| DEVICE_INFO (Standard BLE) | `0000180A-0000-1000-8000-00805F9B34FB` |
| MACHINE_CONTROL_POINT_SERVICE | `E0F00100-5C88-455F-98BA-CFE7DB1A7D1D` |
| WIFI_CONFIGURATION_SERVICE | `E0F00200-5C88-455F-98BA-CFE7DB1A7D1D` |
| FOTA_SERVICE | `E0F00300-5C88-455F-98BA-CFE7DB1A7D1D` |
| SHADOW_SERVICE | `E0F00500-5C88-455F-98BA-CFE7DB1A7D1D` |

### Characteristics - Basic Service

| Characteristic | UUID | Access |
|---------------|------|--------|
| CHAR_PROFILE_VERSION | `96600101-526E-4676-A11A-AF1EB848165B` | Read |
| CHAR_SERIAL_NUMBER | `96600102-526E-4676-A11A-AF1EB848165B` | Read |
| CHAR_PAIRING_STATUS | `96600103-526E-4676-A11A-AF1EB848165B` | Read/Notify |
| CHAR_ASSET_VERSIONS | `96600104-526E-4676-A11A-AF1EB848165B` | Read |
| CHAR_MACHINETOKEN | `96600105-526E-4676-A11A-AF1EB848165B` | Read/Write |

### Characteristics - Device Info (Standard BLE SIG)

| Characteristic | UUID | Access |
|---------------|------|--------|
| CHAR_MODEL_NUMBER | `00002A24-0000-1000-8000-00805F9B34FB` | Read |
| CHAR_FIRMWARE_REVISION | `00002A26-0000-1000-8000-00805F9B34FB` | Read |
| CHAR_SOFTWARE_REVISION | `00002A28-0000-1000-8000-00805F9B34FB` | Read |
| CHAR_MANUFACTURER_NAME | `00002A29-0000-1000-8000-00805F9B34FB` | Read |

### Characteristics - Machine Control Point

| Characteristic | UUID | Access |
|---------------|------|--------|
| CHAR_REQUEST | `E0F00101-5C88-455F-98BA-CFE7DB1A7D1D` | Write |
| CHAR_RESPONSE | `E0F00102-5C88-455F-98BA-CFE7DB1A7D1D` | Read/Notify |

### Characteristics - WiFi Configuration

| Characteristic | UUID | Access |
|---------------|------|--------|
| CHAR_WIFISETTINGSSETUP | `E0F00201-5C88-455F-98BA-CFE7DB1A7D1D` | Write |
| CHAR_WIFICURRENTSETTING | `E0F00202-5C88-455F-98BA-CFE7DB1A7D1D` | Read |
| CHAR_WIFISCANSELECTION | `E0F00203-5C88-455F-98BA-CFE7DB1A7D1D` | Write |
| CHAR_WIFISCANSSIDSELECTED | `E0F00204-5C88-455F-98BA-CFE7DB1A7D1D` | Read/Notify |
| CHAR_WIFIMACADDRESS | `E0F00205-5C88-455F-98BA-CFE7DB1A7D1D` | Read |
| CHAR_WIFIIOTMARKET | `E0F00206-5C88-455F-98BA-CFE7DB1A7D1D` | Read |

### Characteristics - FOTA (Firmware Over The Air)

| Characteristic | UUID | Access |
|---------------|------|--------|
| CHAR_FOTACOMMAND | `E0F00301-5C88-455F-98BA-CFE7DB1A7D1D` | Write |
| CHAR_FOTASTATUS | `E0F00302-5C88-455F-98BA-CFE7DB1A7D1D` | Read/Notify |

### Characteristics - Shadow (Device Twin)

| Characteristic | UUID | Access |
|---------------|------|--------|
| CHAR_SHADOWHEADER | `E0F00501-5C88-455F-98BA-CFE7DB1A7D1D` | Read/Write |
| CHAR_SHADOWUPDATE | `E0F00502-5C88-455F-98BA-CFE7DB1A7D1D` | Read/Notify |

---

## Command Protocol

Source: `com.sdataway.barista.sdk.models.CCommandReq`, `CCommandRsp`

Used by Barista and Vertuo Next machines for structured command/response communication.

### CCommandReq (Request)

Written to `CHAR_COMMAND_REQ`. Wire format (19 bytes total):

```
Offset  Size    Field
0       1       cmdID (unsigned byte)
1       1       subCmdID (unsigned byte)
2       1       dataControl (bitfield, see below)
3-18    0-16    data payload
```

Note: The CCommandReq model class uses `short` for cmdID/subCmdID, but the
characteristic handler (`CharacCommandReq.java`) writes them as single bytes
via `setByteUnsigned()` at offsets 0, 1, 2. Verified for both Barista and Vertuo Next.

### CCommandRsp (Response)

Read from `CHAR_COMMAND_RSP` (via notification). Same wire format as request:

```
Offset  Size    Field
0       1       cmdID (unsigned byte)
1       1       subCmdID (unsigned byte)
2       1       dataControl (unsigned byte)
3-18    0-16    data payload
```

### DataControl Bitfield

```
Bit 0-4  (mask 0x1F): dataLength    - payload byte count (0-31)
Bit 6    (mask 0x40): toggleFlag    - packet sequence toggle
Bit 7    (mask 0x80): hasNextPackage - more packets follow
```

### Recipe Commands

Source: `com.sdataway.barista.sdk.models.RecipeCommand`

| Command | Value | Description |
|---------|-------|-------------|
| INSERT | 0 | Insert recipe at position |
| APPEND | 1 | Append recipe to list |
| REPLACE | 2 | Replace recipe at position |
| DELETE | 3 | Delete recipe at position |
| MOVE | 4 | Move recipe to new position |
| SET_TEMPORARY | 5 | Set as temporary recipe |
| CLEAR | 6 | Clear all recipes |
| GET | 7 | Get recipe at position |
| COUNT | 8 | Get recipe count |
| GET_CRCS | 9 | Get CRC checksums |
| GET_ID | 10 | Get recipe ID |

### Recipe Phase Structure

Source: `com.sdataway.barista.sdk.models.Phase`

Each recipe phase serializes to 6 bytes (MSB format):

```
Offset  Size  Field           Range
0-1     2     motorSpeed      300-4000 RPM
2-3     2     acceleration    50-2000
4       1     temperature     0-70 C
5       1     durationSeconds 0-240 s
```

---

## Byte Sequence Transfer (BST) Protocol

Source: `com.sdataway.ble2.BSTProtocol`

Used for transferring large data payloads (recipes, firmware) that exceed the 20-byte BLE MTU.

### Constants

| Constant | Value | Description |
|----------|-------|-------------|
| PACKET_SIZE | 20 | Total BLE packet size |
| CMD_PAYLOAD_SIZE | 19 | Payload per command packet |
| SND_PAYLOAD_SIZE | 18 | Send data payload |
| RCV_PAYLOAD_SIZE | 18 | Receive data payload |
| MAX_GET_MISSING_SN | 9 | Max missing packet retries |

### Protocol Commands

| Command | Value | Description |
|---------|-------|-------------|
| PROTOCOL_CMD_INIT | 0x01 | Initialize transfer session |
| PROTOCOL_CMD_NEXT | 0x02 | Request/send next packet |
| PROTOCOL_CMD_GET | 0x04 | Request specific packet by sequence number |
| PROTOCOL_CMD_DONE | 0x05 | Transfer complete |

### Protocol Responses

| Response | Value | Description |
|----------|-------|-------------|
| PROTOCOL_RSP_INIT | 0x11 | Init acknowledged |
| PROTOCOL_RSP_NEXT | 0x12 | Next packet data |
| PROTOCOL_RSP_NONE | 0x13 | No data ready |

### Packet Flags

| Flag | Mask | Description |
|------|------|-------------|
| FLAG_MASK_END_SN | 0x01 | Last packet in sequence |
| FLAG_MASK_ALTERNATE_FLAG | 0x02 | Alternating toggle for sequencing |
| FLAG_MASK_PADDING_FLAG | 0x04 | Packet contains padding bytes |

### BST Packet Structure

```
Byte 0:      Protocol command/response byte
Byte 1:      Flags + sequence info
Bytes 2-19:  Data payload (18 bytes)
```

### Transfer Flow

1. Sender sends `PROTOCOL_CMD_INIT` with total data length
2. Receiver responds with `PROTOCOL_RSP_INIT`
3. Sender sends data packets with `PROTOCOL_CMD_NEXT`, each containing 18 bytes of payload
4. Last packet has `FLAG_MASK_END_SN` set
5. If receiver detects missing packets, it requests them with `PROTOCOL_CMD_GET`
6. Transfer completes with `PROTOCOL_CMD_DONE`

### BST Data Model

- **BSTBuffer**: Manages the full data payload, split into BSTBatch groups (max 4590 bytes per batch)
- **BSTBatch**: Contains ordered list of BSTSnData packets for one batch
- **BSTSnData**: Individual packet with sequence number, flags, and 18-byte payload
- **BSTInterval**: Represents a range of missing packet sequence numbers

---

## Machine Status Byte Format

### Barista Machine Status

Source: `com.sdataway.barista.sdk.models.MachineStatus`

Read from `CHAR_MACHINE_STATUS`. Byte layout:

```
Byte 0:
  Bit 0:     bootloaderActive
  Bit 3:     errorPresent
  Bit 4:     isMotorRunning
  Bit 5:     isInductionHeatingActive
  Bits 5-6:  pairingKeyState = (byte[0] & 0x60) >> 5
             (dual interpretation: bits 5-6 are read BOTH individually
              AND as a combined 2-bit pairingKeyState field)
  Bit 6:     isLastCmidValid
  Bit 7:     isSetupComplete

Byte 1:
  machineState = (byte[1] & 0xFC) >> 2
```

### Vertuo Next Machine Status

Source: `com.sdataway.vertuonext.sdk.models.MachineStatus`

```
Byte 0:
  Bit 0:   waterTankEmpty
  Bit 1:   cleaningNeeded
  Bit 2:   descalingNeeded
  Bit 3:   ledSignalingActive
  Bit 4:   errorPresent
  Bits 5-6: pairingKeyState (PairingKeyState enum)
  Bit 7:   bootloaderActive

Byte 1:
  Bits 0-3: machineStateVenus low nibble
  Bit 4:    milkFrotherRunning
  Bit 5:    manualProgCupLengthInProgress
  Bit 6:    capsuleContainerFull
  Bit 7:    brewingUnitClosed

Byte 2:
  Bits 4-7: machineStateVenus high nibble

machineStateVenus = (byte[1] & 0x0F) + (byte[2] & 0xF0)
```

### VMini Pairing Status

Source: `com.sdataway.vmini.sdk.models.PairingStatus`

Read from `CHAR_PAIRING_STATUS`:

| Value | State |
|-------|-------|
| 0 | NOT_PAIRED |
| 1 | PAIRED |
| 2 | PAIRING_PROCESS_ONGOING |
| 255 | UNKNOWN |

---

## Machine Info Format

Source: `com.sdataway.barista.sdk.characteristics.CharacMachineInfo`

Read from `CHAR_MACHINE_INFO`:

```
Offset  Size  Field
0-1     2     Hardware Version (MSB, parsed with getVersionV2())
2-3     2     Bootloader Version (MSB)
4-5     2     Firmware Version (MSB)
6-7     2     Bluetooth Version (MSB)
8-13    6     Device MAC Address
```

Version format (getVersionV2): `major.minor` from 2-byte MSB value.

---

## Authentication

Source: `com.sdataway.vertuonext.sdk.characteristics.CharacCMID`, `CharacCMIDType`, `CharacTXLevelChangeRequest`

Nespresso machines require **application-level authentication** after BLE pairing. Without writing a valid auth key (CMID), GATT characteristic reads are denied with `org.bluez.Error.NotPermitted`.

### Authentication Characteristics

| Characteristic | UUID | Access | Description |
|---------------|------|--------|-------------|
| CHAR_CMID (Auth Key) | `06AA3A41-F22A-11E3-9DAA-0002A5D5C51B` | Write | 8-byte auth key |
| CHAR_CMID_TYPE (Onboard Status) | `06AA3A51-F22A-11E3-9DAA-0002A5D5C51B` | Read/Notify | Pairing state enum |
| CHAR_TX_LEVEL_CHANGE_REQUEST | `06AA3A61-F22A-11E3-9DAA-0002A5D5C51B` | Write | 1-byte TX power level |

### CMID Type (Onboard Status) Values

Source: `com.sdataway.vertuonext.sdk.models.CCMIDType.CMIDTypeEnum`

| Value | State | Description |
|-------|-------|-------------|
| 0 | NONE | Not onboarded, no auth key registered |
| 1 | TEMPORARY | Temporary auth key (onboarding in progress) |
| 2 | FINAL | Permanent auth key established |
| 3 | UNDEFINED | Undefined state |
| 255 | UNKNOWN | Could not determine state |

### Auth Key Format

Source: `com.sdataway.vertuonext.sdk.models.CCMID`

- **Size:** 8 bytes (`byte[] cMID = new byte[8]`)
- **Generation:** Random 8 bytes (or 16 hex characters converted to 8 bytes)
- **Persistence:** Must be stored and reused on subsequent connections

### Onboarding Flow (First Connection)

Note: No BLE-level pairing (`createBond`/`pair()`) is needed. The APK does not
call `BluetoothDevice.createBond()`. Authentication is purely application-level.

1. **Check Status**: Read `CHAR_CMID_TYPE` - if value is `0` (NONE), machine is not onboarded
3. **Set TX Level**: Write `0x01` to `CHAR_TX_LEVEL_CHANGE_REQUEST` (set low power for pairing)
4. **Write Auth Key**: Write 8-byte random key to `CHAR_CMID`
5. **Wait**: Sleep 2-3 seconds for machine to process
6. **Verify**: Read `CHAR_CMID_TYPE` again - should be `2` (FINAL) if successful

### Subsequent Connection Flow

1. **Authenticate**: Write stored 8-byte auth key to `CHAR_CMID`
2. **Read**: All GATT characteristics are now accessible

---

## Brew Command Protocol

Source: `github.com/bulldog5046/ha_nespresso_integration`

Brew commands are written to `CHAR_COMMAND_REQ` (`06AA3A42`) as a 10-byte buffer:

```
Offset  Value   Description
0       3       Command prefix
1       5       Command prefix
2       7       Command prefix
3       4       Command prefix
4-7     0       Reserved
8       temp    Temperature (LOW=1, MEDIUM=0, HIGH=2)
9       brew    Brew type (see below)
```

### Brew Types

| Value | Type |
|-------|------|
| 0 | Ristretto |
| 1 | Espresso |
| 2 | Lungo |
| 4 | Hot Water |
| 5 | Americano |
| 7 | Custom |

### Command Response

Responses are received via notification on `CHAR_COMMAND_RSP` (`06AA3A52`).

---

## Encryption

Source: `com.sdataway.barista.machine.utils.crypto.impl.CryptoImpl`

- **Algorithm:** AES/ECB/PKCS5Padding
- **Usage:** Primarily for firmware update (FOTA) validation and IoT configuration decryption
- BLE characteristic data is protected by application-level auth (CMID), not application-layer encryption

---

## Connection Management

Source: `com.sdataway.ble2.AbstractCharacteristicHelper`, `ScanService`

### Timeouts

| Operation | Timeout |
|-----------|---------|
| Characteristic Read | 30,000 ms |
| Characteristic Write | 30,000 ms |
| BLE Scan Duration | 10,000 ms (default) |

### Full Connection Flow (APK)

The official Nespresso app follows this sequence. Note: the APK does NOT call
Android's `BluetoothDevice.createBond()` (BLE pairing). Authentication is
entirely application-level via CMID.

1. **Scan**: `ScanService` scans for devices advertising the expected service UUIDs
2. **Connect**: Establish GATT connection to selected device
3. **Discover Services**: Enumerate all GATT services and characteristics
4. **Check Onboard**: Read `CHAR_CMID_TYPE` for auth state (0=NONE, 2=FINAL)
5. **Onboard** (if CMID_TYPE is NONE):
   a. Write `0x01` (REDUCE_POWER) to `CHAR_TX_LEVEL_CHANGE_REQUEST`
   b. Write 8-byte auth key to `CHAR_CMID`
   c. Wait 2 seconds
   d. Read `CHAR_CMID_TYPE` again to verify onboarding succeeded
6. **Authenticate**: Write stored 8-byte auth key to `CHAR_CMID`
7. **Read Status**: Read `CHAR_MACHINE_STATUS` to get current state
8. **Read Info**: Read `CHAR_MACHINE_INFO` for hardware/firmware versions
9. **Read Serial**: Read `CHAR_SERIAL_NUMBER` for device identification
10. **Enable Notifications**: Subscribe to status and response characteristics
11. **Operate**: Send commands via `CHAR_COMMAND_REQ`, receive responses via `CHAR_COMMAND_RSP`

### HA Integration Connection Flow

The integration matches the APK flow. No BLE-level pairing is needed (GATT
characteristic flags show no encryption requirements). The auth key is generated
once, persisted in the config entry, and reused across restarts.

1. **Acquire BLE lock**: Prevent concurrent connections (machine supports one client)
2. **Disconnect stale client**: Clean up any persistent connection
3. **Connect**: `establish_connection()` with 3 retry attempts
4. **Authenticate**: `_authenticate()` writes CMID with response (all families require this)
5. **Verify**: Read a protected characteristic to confirm auth succeeded
6. **Retry** (on failure): Disconnect, reconnect, re-authenticate once
7. **Read all characteristics**: status, info, serial, profile, params, settings, errors
8. **Persistent mode** (optional): Subscribe to `CHAR_MACHINE_STATUS` notifications
9. **Disconnect** (or keep alive in persistent mode)
10. **Parse**: Convert raw bytes to `NespressoMachineData`
11. **Fire triggers**: Compare old/new state, fire bus events

### Write Operation Flow

All write operations (recipe, language, water hardness, APO, FOTA) use the same pattern:

1. **Acquire BLE lock**: Same lock as read, prevents concurrent access
2. **Connect**: `establish_connection()` with 2 retry attempts
3. **Authenticate**: `_authenticate()` writes CMID with response
4. **Write**: `write_gatt_char()` with `response=True`
5. **Disconnect**: Always, even on error
6. **Refresh**: `async_request_refresh()` to update sensors

### Thread Safety

All characteristic operations use `StaticBusyLocker` (APK) or `asyncio.Lock` (HA integration) to prevent concurrent reads/writes on the same characteristic.
