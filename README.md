<p align="center">
  <img src="images/logo.png" alt="Nespresso Smart" width="120">
</p>

# Nespresso Smart - Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/renaudallard/homeassistant_nespresso_smart)
[![Release](https://img.shields.io/github/v/release/renaudallard/homeassistant_nespresso_smart)](https://github.com/renaudallard/homeassistant_nespresso_smart/releases)
[![Validate](https://github.com/renaudallard/homeassistant_nespresso_smart/actions/workflows/validate.yml/badge.svg)](https://github.com/renaudallard/homeassistant_nespresso_smart/actions/workflows/validate.yml)

A Home Assistant custom integration for Nespresso Smart coffee machines via Bluetooth Low Energy (BLE).

Built by reverse-engineering the Nespresso Smart Android app (v1.2.5).

> **Screenshot wanted:** If you have a Nespresso machine paired with this integration, please submit a screenshot of the HA device page via a [GitHub issue](https://github.com/renaudallard/homeassistant_nespresso_smart/issues).

---

## Supported Machines

| Family | BLE Service UUID | Machines |
|--------|-----------------|----------|
| Barista (Original) | `65241910-0253-11E7-93AE-92361F002671` | Barista |
| Vertuo Next (Venus) | `06AA1910-F22A-11E3-9DAA-0002A5D5C51B` | VertuoNext, VertuoPop, VertuoPopPlus, VertuoLattissima, VertuoCreatista, VertuoUp |
| VMini | `96600100-526E-4676-A11A-AF1EB848165B` | Vertuo Mini |

Every machine in the Venus family advertises that one service UUID, so the model
shown on the device page comes from the platform code instead, which appears in
the serial number and in the BLE name:

| Code | Model |
|------|-------|
| CV1, DV1, CV3, DV3 | Vertuo Next |
| CV2, DV2 | Vertuo Pop |
| CV6, DV6 | Vertuo Pop+ |
| DV5 | Vertuo Lattissima |
| CV5 | Vertuo Creatista |

A machine that has not told us its name or serial yet is shown as Vertuo Next
until the first successful read.

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=renaudallard&repository=homeassistant_nespresso_smart&category=integration)

Click the button above to open the repository directly in HACS, or add it manually:

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

After installation, the integration will auto-discover Nespresso machines via Bluetooth. Ensure your machine is powered on and within BLE range.

During setup the **auth token** field is optional. Leave it empty on a machine
that has never been paired and the integration generates its own token. On a
machine the Nespresso app already claimed, fill it in rather than reset the
machine: either the 32 character pairing key from your Nespresso account, which
the integration converts to the token itself, or the 16 character token read
off a Bluetooth capture. See below for both.

### Machine already paired with the Nespresso app

Each machine stores one auth token (CMID), and only accepts one while it holds none. `CMID_TYPE` says which of the four states it is in:

| Value | Name | Meaning |
| --- | --- | --- |
| `0x00` | `NONE` | No token stored, ready to accept one |
| `0x01` | `TEMPORARY` | A token is stored |
| `0x02` | `FINAL` | A token is stored |
| `0x03` | `UNDEFINED` | A token was written and the machine could not classify it |

`NONE` and `UNDEFINED` both mean the machine holds no usable token, and the integration keeps trying against either. Once the type is `TEMPORARY` or `FINAL` the machine acknowledges a new token, quietly keeps the one it has, and refuses every protected read with ATT `0x02`, seen as GATT error 2 through a proxy and `NotPermitted` on a local adapter. The integration then needs either the same token or a factory reset. Three options:

**Option A: Recover the pairing key from your Nespresso account (no reset)**

The app does not invent the key on the machine, it registers it against your
account, so it is still there to be read. This is the only route that leaves the
phone app working, because the machine keeps the token it already has.

Log in at [nespresso.com](https://www.nespresso.com/) in a browser, open the
developer console on that page (F12, or Ctrl+Shift+J) and run:

```js
const market = location.pathname.split('/')[1];  // fr on www.nespresso.com/fr/fr/
const get = async p => (await fetch(p, {credentials: 'include'})).json();
const me = await get(`/ecapi/customers/v7/${market}/b2c/me/personal-info`);
const res = await get(`/ecapi/machines/v1/${market}/b2c/${me.memberNumber}`);
console.table((Array.isArray(res) ? res : res.machines ?? []).map(m =>
    ({serial: m.serialNumber, mac: m.macAddress, pairingKey: m.pairingKey})));
```

Copy the `pairingKey` of the machine you are adding, 32 hex characters, and
paste it into the auth token field during setup. The integration derives the
token from it exactly as the app does.

Both paths carry your market as their first segment, which is where the country
code in the page URL comes from. If the calls fail, check that segment: it is
your two letter country code, in lower case.

It has to be a browser. The account endpoints sit behind Akamai Bot Manager,
which the app satisfies with an `X-acf-sensor-data` header it builds on the
device, so `curl` gets `403 NOT_ALLOWED`. A logged-in browser already holds the
cookies that pass the check.

**Option B: Factory reset the machine**

A factory reset clears the stored auth token and all settings. The Bluetooth pairing button alone is not sufficient; a full factory reset is required.

- **Vertuo Next / Vertuo Pop**: Close the head, press the button 3 times within 2 seconds. The light blinks orange to confirm.
- **Barista**: Consult the Nespresso support page for your model's reset procedure.

After reset, clear the stale Bluetooth bond on the HA host and restart HA:

```bash
bluetoothctl remove <MACHINE_MAC_ADDRESS>
```

Then remove and re-add the integration in HA. The Nespresso app will also need to re-pair.

**Option C: Extract the existing token from a Bluetooth capture (Android only)**

Capture the auth token from the Nespresso app using Android's BLE logging:

1. On your Android phone, enable **Developer Options** (Settings > About > tap Build Number 7 times)
2. In Developer Options, enable **Bluetooth HCI snoop log**
3. Open the Nespresso app and let it connect to the machine
4. Disable Bluetooth HCI snoop log
5. Pull the log: `adb pull /data/misc/bluetooth/logs/btsnoop_hci.log` (or find it at the path shown in Developer Options)
6. Open in **Wireshark**, filter: `btatt.handle` and look for a Write Request to the auth characteristic (UUID `06aa3a41` for Vertuo Next, `65243a41` for Barista)
7. The 8-byte value written is the auth token. Convert to 16 hex characters and enter it during setup. It will start with `8`, which is the marker the app puts on every token it writes.

This method is not available on iOS.

### Requirements

- Home Assistant 2026.03 or newer
- A Bluetooth adapter attached to Home Assistant, or an ESPHome Bluetooth
  proxy with `active: true`
- Nespresso machine powered on and within BLE range

## Link encryption

Most machines need none of this. On some, GATT operations only answer over an
encrypted BLE link. The Nespresso Android app never hits it, because Android
negotiates link encryption on its own. Neither transport Home Assistant uses
does that unprompted, and the two fail differently.

### Through an ESPHome Bluetooth proxy

The machine answers with GATT error 5, `Insufficient authentication`, or 15,
`Insufficient encryption`, and the log fills with lines like:

```
Error reading char/descriptor for handle 0x32, status=5
Could not encrypt the link to AA:BB:CC:DD:EE:FF
```

The two codes are the same problem at different stages. A machine that holds no
key for the proxy sends 5. Once the two have paired it sends 15 instead, meaning
it knows the proxy and only wants the link turned on. Both are answered by the
same request.

The integration handles this on its own: it asks the proxy to pair, then
retries the operation. The bond is negotiated and stored by the proxy, not by
the Home Assistant host, so a host with no Bluetooth adapter of its own is
fine, and `bluetoothctl` on the host has no effect on a proxied connection.

Two things are needed on the proxy:

- `active: true` under `bluetooth_proxy`. This is the same setting active
  connections need, so a proxy that reaches the machine at all already has it
- ESPHome 2023.6.0 or newer, which is when the proxy started telling Home
  Assistant that it can pair

If pairing is unavailable, the log says so:

```
The Bluetooth proxy serving AA:BB:CC:DD:EE:FF cannot pair.
```

The bond lives in that one proxy's flash. It survives reboots and OTA updates,
a factory reset of the proxy erases it, and a second proxy pairs on its own the
first time it is used. Only passkey-free pairing can complete over a proxy,
which is what these machines use.

A factory reset of the machine does not necessarily cost the proxy its bond.
The one time that was actually tested, on a Vertuo Creatista, the reset cleared
the pairing token and left the link key alone: the next connection answered with
GATT error 15, encrypted, and onboarded from `NONE` as it should.

A machine can also lose its key without being reset, and when it does the proxy
sorts itself out in one connection.

The failure comes first, because of which security action ESPHome asks for.
It pairs with `esp_ble_set_encryption(bda, ESP_BLE_SEC_ENCRYPT)`, and of the
three actions only the `NO_MITM` and `MITM` variants carry an "else re-pair with
the remote device" clause. So the proxy starts encryption from the key it
stored, the machine refuses it, and that arrives as error 97 with no fallback to
a fresh exchange inside that attempt.

The recovery comes from ESP-IDF, on the same event. The auth-complete that
carries the 97 runs `btc_dm_ble_auth_cmpl_evt`, where any reason other than 80,
81 or 82 falls to a default branch that logs `remove bond in flash` and calls
`btc_dm_remove_ble_bonding_keys()`. With no stored key left, the next connection
cannot take the reuse branch and runs a full pairing exchange instead. One
reporter's log shows the whole cycle: 252 ms to fail with 97, then 776 ms to
pair successfully on the following connection, with nothing done in between.

So there is normally nothing to clear by hand, and clearing it at that point
only throws away a key the proxy has already deleted.

Because the recovery is the next connection, the integration gets out of the way
of a failed one as fast as it can. A pairing request that comes back with a
failure means the link is plain and the machine will not answer, so the poll
gives up there instead of spending a ten second timeout on the onboard status
read and another on the token write. That turns a failing cycle from about
twenty eight seconds into under one, and the recovery lands on the next poll
rather than a poll and a half later.

The poll stops there rather than reading anyway. Two pairing requests have
failed by that point and nothing left in the cycle can ask for a third, so the
read would be refused with a GATT error describing none of it. One line says
what happened instead, and Home Assistant prints it once per outage rather than
once per poll.

Do not reboot the proxy either. A reboot clears strictly less than the failure
has already cleared, since `btm_sec.c` drops the in-memory key on the same
failure that erases the flash copy.

Only one shape genuinely gets stuck: a machine that answers by dropping the link
rather than refusing it, because then no auth-complete arrives, the erase above
never runs, and the same dead key is presented on every connection. That reads
as a bare `TimeoutError` with no error number, on every poll. A proxy that
crashes partway through the exchange lands in the same place. If you see that,
erasing the proxy's bond is the fix, and it is a last resort: a factory reset of
the proxy drops the bonds for every device it serves, and reflashing it over
serial takes its WiFi credentials too.

### Through a local Bluetooth adapter

BlueZ raises the link security itself and then waits for a pairing agent that
nothing in Home Assistant registers, so the operation hangs instead of
failing: the config entry stays stuck in "initializing" and nothing says why.
The symptom in the log is:

```
Reading onboard status from AA:BB:CC:DD:EE:FF timed out, so the link is not
encrypted.
```

If you see it, pair the machine once from a terminal on the Home Assistant
host:

```
bluetoothctl
agent NoInputNoOutput
default-agent
scan on
```

Wait for the machine to appear, then:

```
trust AA:BB:CC:DD:EE:FF
pair AA:BB:CC:DD:EE:FF
scan off
exit
```

Expected result: `Pairing successful`.

**Use `agent NoInputNoOutput`, not `agent on`.** The default agent is
`KeyboardDisplay`, which requests MITM protection with a passkey. A coffee
machine has neither a display nor a keypad, so it rejects the pairing with
`org.bluez.Error.ConnectionAttemptFailed`.

**The bond is yours to manage.** The integration never removes one, on a local
adapter or a proxy. A pairing on the host is one you set up by hand and may
share with other tools, and a proxy erases its own. A stale bond left over from
a factory-reset machine blocks
reconnection and shows up as `Software caused connection abort`, and clearing it
is a manual step, see [Troubleshooting](#software-caused-connection-abort).

### Ordering that avoids trouble

1. If the app has paired the machine, recover its pairing key or factory reset
   it (see [Machine already paired with the Nespresso app](#machine-already-paired-with-the-nespresso-app))
2. On a host with its own Bluetooth adapter, pair from `bluetoothctl` as
   above. Through a proxy there is nothing to do by hand
3. Add the integration, either pasting that pairing key or leaving the auth
   token field **empty** so it generates and stores its own
4. Keep the phone's Bluetooth off until setup finishes, or the app may claim
   the machine first

If a previous attempt left a stale bond, `bluetoothctl remove AA:BB:CC:DD:EE:FF`
clears both the bond and the cached GATT database. A stale GATT cache shows up
as `Service Discovery has not been performed yet`.

## Entities

Entity names, the machine state values and the dropdown options are translated
into English, French, German, Spanish, Italian, Dutch and Polish, and follow
the language set in your Home Assistant profile. The names below are the
English ones.

### Sensors

| Entity | Barista | Vertuo Next | VMini | Description |
|--------|---------|-------------|-------|-------------|
| State | Yes | Yes | No | Machine operational state (enum with 32 translated states) |
| Firmware version | Yes | Yes | Yes | Current firmware version (diagnostic) |
| Hardware version | Yes | Yes | No | Hardware revision (diagnostic) |
| Bootloader version | Yes | Yes | No | Bootloader version (diagnostic) |
| Profile version | Yes | Yes | No | BLE profile version (diagnostic) |
| Bluetooth version | Yes | No | No | Bluetooth module version (diagnostic) |
| Recipe DB version | No | Yes | No | Recipe database version (diagnostic) |
| Connectivity FW | No | Yes | No | WiFi/connectivity firmware version (diagnostic) |
| Error code | No | Yes | No | Current active error code (diagnostic) |
| Error log code | No | Yes | No | Error from error log (diagnostic) |
| Capsule counter | No | Yes | No | Capsule counter |
| IoT market | No | Yes | No | IoT market name (diagnostic) |
| Recipe slots | Yes | No | No | Maximum recipe slots (diagnostic) |
| Brewing duration | Yes | Yes | No | Time elapsed since brewing started (seconds) |
| Total brews | No | Yes | No | Brews counted since the integration was installed |
| Brews since descaling | No | Yes | No | Brews counted since the descaling counter was last reset, with days since the reset as an attribute |
| Brews until descaling | No | Yes | No | Brews left before the capsule limit is reached |
| Days until descaling | No | Yes | No | Days left before the time limit is reached |
| Device shadow | No | No | Yes | Device shadow JSON data (diagnostic) |
| FOTA status | No | No | Yes | Firmware update status (diagnostic) |
| FOTA progress | No | No | Yes | Firmware update progress (diagnostic) |

### Binary Sensors

| Entity | Barista | Vertuo Next | VMini | Description |
|--------|---------|-------------|-------|-------------|
| Error | Yes | Yes | No | Machine has an active error |
| Induction heater | Yes | No | No | Induction heater is active |
| Water tank empty | No | Yes | No | Water tank needs refilling |
| Descaling needed | No | Yes | No | Machine needs descaling |
| Cleaning needed | No | Yes | No | Machine needs cleaning |
| Capsule container full | No | Yes | No | Used capsule container is full |
| Brewing unit | No | Yes | No | Brewing unit head is open |
| Milk frother | No | Yes | No | Milk frother is running |
| LED signaling | No | Yes | No | LED signaling is active |

### Controls

| Entity | Barista | Vertuo Next | VMini | Description |
|--------|---------|-------------|-------|-------------|
| Recipe | Yes | No | No | Select recipe (espresso, lungo, etc.) |
| Language | Yes | No | No | Set machine display language |
| Brew type | No | Yes | No | Select brew type (ristretto, espresso, lungo, hot water, americano) |
| Brew temperature | No | Yes | No | Select brew temperature (low, medium, high) |
| Brew | No | Yes | No | Start brewing (see brewing flow below) |
| Water hardness | No | Yes | No | Set water hardness level (0-6 slider) |
| Auto power off | No | Yes | No | Set auto power off time (minutes) |
| Reset descaling counter | No | Yes | No | Clear the descaling counter after descaling the machine |
| Check firmware update | No | No | Yes | Trigger firmware update check |

### Brewing

The machine cannot be woken up over BLE. To brew from Home Assistant:

1. Select a **brew type** (ristretto, espresso, lungo, hot water, americano) and **temperature** (low, medium, high)
2. Press **Brew** in HA
3. If the machine is asleep, a notification appears asking you to press the physical button on the machine
4. Press the button on the machine to wake it up
5. Insert a capsule and close the head
6. The integration automatically waits for heating to finish and brews when the machine is ready

If there is a used capsule in the machine, a notification asks you to replace it. Brewing starts automatically once a fresh capsule is inserted and the head is closed.

Multiple presses of the Brew button are debounced. Only one brew command is sent.

The brew command is sent on the same BLE connection used for status polling (required by the machine). It is known to work on a Vertuo Next only. A Vertuo Pop and a Vertuo Creatista both accept the write and do nothing, and the official app has no Bluetooth brew command for any model, so there is nothing else to send.

**Note:** BLE brewing is experimental. It was reverse-engineered from BLE captures on Vertuo Next models and may not work on all machines.

**Vertuo Pop and Vertuo Creatista:** Remote brewing over BLE is not supported by these machines. The Nespresso app itself does not offer a brew button for any model, and neither machine responds to a known BLE brew command: both acknowledge the write and stay idle. Only status monitoring and settings like water hardness work over BLE. The brew button and its two settings are therefore not created on a machine whose platform code is `CV2` or `DV2`, which are the Pop, or `CV5`, which is the Creatista.

That verdict rests on a handful of machines, so it is not final. **Offer brewing on a model that is not known to brew** in the options brings the button and both selects back, for anyone who wants to try theirs. `nespresso.send_command` tests the same thing without the option and says more about the result.

### Events and Triggers

Event entity fires on machine state changes (Barista and Vertuo Next).

Device triggers for automations:
- **brewing_started** / **brewing_finished**
- **error_occurred**
- **ready** / **standby**
- **descaling_needed** / **water_tank_empty**

### Device Info

Each machine is registered as a device with manufacturer, model, serial number, firmware version, and hardware version.

## How It Works

The integration connects to the machine via BLE at a configurable interval (default 60 seconds), reads the status characteristics, and disconnects. This avoids blocking the Nespresso mobile app from connecting.

Machine family is detected automatically from the advertised BLE service UUID during discovery. When the machine becomes available after being off or out of range, a BLE advertisement callback triggers an immediate refresh.

On the Vertuo Next family the advertisement itself carries the machine status bytes, so state and alarm flags follow the machine within about a second instead of waiting for the next poll. Values that only a connection can read, such as error codes and the capsule counter, still come from the poll.

Authentication is application-level only (CMID write with response), matching the official Nespresso Android app, which does not call `createBond` either. That is separate from link-layer encryption: some characteristics only answer over an encrypted link, and Android negotiates that transparently while neither BlueZ nor a Bluetooth proxy does it unprompted. See [Link encryption](#link-encryption). The auth key is generated once and persisted in the config entry so the same key is reused across restarts. If the machine was previously paired with the Nespresso app, a factory reset is required before the integration can onboard.

## Reverse Engineering Documentation

Detailed protocol documentation from the APK decompilation is available under [docs/](docs/).

## Configuration

After adding the machine, go to **Settings > Devices & Services > Nespresso > Configure** to set:

- **Poll interval** (10-600 seconds, default 60): how often to read machine status
- **Persistent connection** (off by default): keeps the BLE connection open for real-time GATT notifications. Gives instant status updates but blocks the Nespresso mobile app.
- **Send the TX level request when onboarding** (on by default): the official app asks the machine to drop its transmit power just before handing over the auth token, and the integration does the same. Leave it on unless you are diagnosing a dropped connection. See [Onboarding drops the connection](#onboarding-drops-the-connection-gatt-error-133).
The Vertuo family also gets a **WiFi status** and **WiFi network** sensor, both diagnostic. Most machines driven over Bluetooth report `not_configured`, which is normal and not a fault: it means the machine has never been put on WiFi. They matter because Nespresso's own maintenance functions, descaling among them, are cloud calls that reach the machine through AWS IoT, so a machine that is not online cannot receive them at all.

- **Descaling interval (capsules)** (1-10000, default 300): how many brews before descaling is due. Vertuo Next family only.
- **Descaling interval (days)** (1-3650, default 90): how many days before descaling is due. Vertuo Next family only.
- **Offer brewing on a model that is not known to brew** (off by default): brings back the brew button and its two selects on a Vertuo Pop or Creatista, which are believed not to brew over Bluetooth. See [Brewing](#brewing).

Nespresso quotes 300 capsules or 3 months for the Vertuo range, whichever comes first. Both limits are configurable because hard water needs more frequent descaling. Brews are counted from machine state transitions, so they are only counted while Home Assistant is running.

## WiFi setup

Vertuo machines can be put on WiFi over Bluetooth, which is what the official app
does during onboarding. Two actions do it:

- `nespresso.scan_wifi` returns the networks the machine can see. The machine
  does the scanning, so the list is what the machine can reach, not what Home
  Assistant can
- `nespresso.configure_wifi` joins one of them

```yaml
action: nespresso.configure_wifi
data:
  config_entry_id: <your entry>
  market: GB
  ssid: MyNetwork
  password: hunter2
  security: wpa2
```

`market` is a two-letter country code and is not optional in practice. The
machine reports `market_not_set` and never reaches Nespresso's servers without
it, so it is written before the credentials, in the order the app uses.

Watch the **WiFi status** sensor for the outcome. `connecting` becomes
`connected` on success, and the failure states are specific: `wrong_password`,
`no_internet`, `connection_failed`, `server_unreachable`.

Two things worth knowing before using this:

- **The passphrase is sent to the machine in clear.** That is how the official
  app sends it, and the characteristic has no encrypted alternative. It goes over
  an encrypted BLE link when the machine asks for one, which the Vertuo family
  does, but it is stored and transmitted as plain text either way
- Only DHCP is supported. The static address fields exist in the protocol and are
  written with their octets reversed, which is not a detail worth risking
  somebody's network configuration on until someone needs it

Putting a machine on WiFi does not give Home Assistant anything new by itself.
Nespresso's cloud maintenance functions, descaling among them, need the machine
registered to a Nespresso account through their app as well. See
[Limitations](#limitations).

## Limitations

- **Vertuo brewing**: Experimental. The brew command was captured from Vertuo Next models and may not work on all machines. The Vertuo Pop and the Vertuo Creatista do not support BLE brewing at all (the Nespresso app itself offers no brew button for any model), so no brew button is created for either. Custom recipes with exact ml volumes are not yet supported.
- **Maintenance commands**: Descaling, rinsing, emptying command IDs are not in the decompiled code. Needs real hardware testing.
- **VMini WiFi**: WiFi current settings characteristic has no handler in the decompiled SDK. Byte layout unknown.
- **Power save**: The machine cannot be woken up over BLE. It must be physically awake (press the button, light steady green) before brewing or certain commands work. The Nespresso app can wake WiFi-connected machines through the cloud, but BLE has no wake command.
- **BLE range**: The machine must be within Bluetooth range of the Home Assistant host.
- **Single client**: Only one BLE client can connect at a time. If the Nespresso app is connected, HA will retry on the next poll.

## Troubleshooting

### "Software caused connection abort"

BlueZ has a stale bond from a previous pairing. Clear it:

```bash
bluetoothctl remove <MACHINE_MAC_ADDRESS>
```

Then restart HA. This is needed after a factory reset of the machine.

### All entities show "unavailable"

The machine is temporarily unreachable via BLE. Ensure it is powered on, within range, and not connected to the Nespresso app. Entities recover automatically on the next successful poll.

### "is onboarded with a different auth token"

Also seen as `NotPermitted` on a local adapter, or GATT error 2 through a proxy.

The machine stores one auth token and only accepts a new one while it holds none
at all. Something else onboarded it first, usually the Nespresso app, and it will
now refuse every read. Nothing can be done about that over Bluetooth, but the key
the app used is registered against your Nespresso account and can be recovered
and pasted in, which is Option A of [Machine already paired with the Nespresso
app](#machine-already-paired-with-the-nespresso-app). Failing that, factory reset
the machine and add the integration again leaving the auth token field empty.

The token the integration generates is stored in the config entry, so deleting
the entry throws it away. If you have the token, put it in the auth token field
when adding the machine back and nothing else is needed.

### Onboarding drops the connection (GATT error 133)

The log shows the CMID write failing with `error=133`, and the machine gone
immediately afterwards. If the line before it says the TX level request was
acknowledged, this is almost certainly a range problem rather than a fault.

That request tells the machine to reduce its radio power for the rest of the
exchange. The official app relies on it too, which is why its pairing screen
says to stay within about a metre of the machine: a phone in your hand keeps
the link when the machine goes quiet, and a Bluetooth proxy across the room
does not.

**Move the proxy next to the machine, within a metre, and reload.** It can go
back where it was once the machine is onboarded, because the machine only
lowers its power while it is being paired.

Turning off **Send the TX level request when onboarding** is a diagnostic, not
a cure. It stops the disconnect, and that is all it does. If the machine then
sits at `CMID_TYPE=0x03 UNDEFINED`, see below.

### "recorded an auth token it could not make sense of"

The machine is at `CMID_TYPE=0x03 UNDEFINED`. It took the write, could not
classify what it was given, and now refuses every protected read.

Every token the official app writes starts with the nibble `8`. That comes from
`PairingUtils.getBufferFromByteArray` in the app, which shifts the pairing key
right by one nibble and puts `0x8` in the space that frees, so the value handed
to the machine always begins `0x8`. Tokens this integration generated before
v0.3.8 were random across all 16 bits of that nibble, so fifteen times out of
sixteen they carried the wrong marker. Older machines accept them anyway. At
least one Vertuo Creatista does not.

Recovering needs a machine with no token and a token of the right shape:

1. Factory reset the machine
2. Delete the config entry and add the machine again, leaving the auth token
   field empty so a new token is generated

Do not paste the old token back in. That is the value the machine rejected.

Reduced power is not a precondition for pairing, despite an earlier version of
this section saying so. On the one Vertuo Creatista this has been tested on,
moving the proxy close enough to keep the link through the power drop removed
the disconnect completely, and the machine still acknowledged the auth token
and ignored it, staying at `CMID_TYPE=0x03 UNDEFINED`. Whatever that machine
wants, the transmit power is not it.

### "never accepted an auth token"

A different problem with the same ATT `0x02` symptom, and the remedy is the
opposite one. The machine took the write but did not commit the token, and
reports `CMID_TYPE=0x03 UNDEFINED`. It holds nobody's token, so a factory reset
changes nothing.

The machine settles on its answer a few seconds after the write, so the
integration writes the token and then reads the state back once a second for
ten seconds before deciding. Leave the machine powered on and in range and let
the poll cycle keep retrying. If it never gets past this, open an issue with a
debug log.

### Proxy logs "status=15" on every poll

A Bluetooth proxy clears its paired flag on each new connection and only
encrypts the link when asked, so the link has to be raised again every time.
Learning that from a refused read makes the ESPHome integration log a warning
once per poll.

The integration remembers which machines have asked for an encrypted link and
raises it before the first read on the next connection, so the warning stops
after the first poll. It starts again once after a Home Assistant restart,
because that memory is not persisted.

### "Could not encrypt the link"

The proxy was asked to pair and could not. The machine goes on refusing every
protected read until the link is encrypted, so the entities stay unavailable.

```
Could not encrypt the link to AA:BB:CC:DD:EE:FF: Pairing failed due to error: 97,
the proxy could not start encryption on the link.
```

The number comes from the ESP32, and it is worth reading literally rather than
guessing. The values are `esp_ble_auth_fail_rsn_t` from ESP-IDF, which starts at
78, so they are not the failure codes from the Bluetooth specification and do
not mean the same things:

| Code | Meaning |
| --- | --- |
| 78 | The machine asked for a passkey. A proxy cannot provide one |
| 80 | The machine wants an authenticated link, which a proxy cannot provide |
| 82 | The machine says it does not support pairing |
| 86 | The machine is refusing repeated attempts |
| 93 | The proxy could not decide how to pair. Check `io_capability` on it |
| 96 | Another security procedure was already running |
| 97 | The proxy could not start encryption on the link |
| 99 | The machine never answered the pairing request |
| 102 | The link dropped during the exchange |

A bare `TimeoutError` instead of a code means nothing came back at all within
35 seconds.

Sometimes the link goes away before the proxy has answered at all, and then the
warning quotes a different message:

```
Could not encrypt the link to AA:BB:CC:DD:EE:FF: Peripheral AA:BB:CC:DD:EE:FF
changed connection status while waiting for BluetoothDevicePairingResponse:
Insufficient authorization (8), the link dropped during the exchange, the
machine stopped answering.
```

Ignore the words the proxy puts in front of the number. They come from
`esp_gatt_status_t`, and the number does not: it is a disconnect reason,
`esp_gatt_conn_reason_t`, so 8 is a supervision timeout rather than the
authorization failure the text claims. Nothing was refused. The clause the
integration adds after it is the one to read:

| Code | Meaning |
| --- | --- |
| 8 | The machine stopped answering. Usually distance |
| 19 | The machine hung up |
| 22 | The proxy hung up |
| 34 | The machine stopped answering a link-layer request |
| 62 | The connection was never established |

This is the same condition as pairing error 102 above, seen from the other
side, and it clears itself the same way on the next connection.

The integration keeps asking, because a machine can be factory reset and
re-onboarded at any time and the next poll has to notice. It does not keep
asking at full rate: after four consecutive failures for one machine it drops
to roughly one attempt every ten minutes, and the warning becomes a debug line
in between. A request that succeeds resets that immediately.

One consequence worth knowing: once it has backed off, a machine that starts
working again is not picked up until the next attempt comes round, so allow up
to ten minutes after a factory reset. Restarting Home Assistant clears the
count, reloading the integration does not.

A failing poll writes this warning and Home Assistant's own `Error fetching
Nespresso ... data`, and nothing else. Both are printed when the machine stops
answering rather than on every poll after that. What each characteristic did is
at debug, under `custom_components.nespresso.ble.protocol`.

### Reading the pairing state without connecting

The advertisement carries the pairing state in bits 5-6 of its first byte, so it
stays readable even while the machine refuses every connected read. Turn on
debug logging and look for `Pairing key state for ... is now`, or download the
integration's diagnostics and read `debug_info.pairing_key_state`.

### Sending a raw command

The `nespresso.send_command` action writes a frame of your choosing to the
machine's command characteristic and returns what happened. It works on every
machine, including the models that get no brew button, which is the point: it
is how a machine gets tested rather than assumed about.

From **Developer tools > Actions**, pick the machine and give it a payload in
hex, for example `03050704000000000002`, a Vertuo lungo at medium temperature.
The response looks like this:

```yaml
request: "03050704000000000002"
command_characteristic: 06aa3a42-f22a-11e3-9daa-0002a5d5c51b
command_properties: [write]
response_characteristic: 06aa3a52-f22a-11e3-9daa-0002a5d5c51b
response_properties: [notify, read]
subscribed: true
listening: [06aa3a12-..., 06aa3a52-...]
write: accepted
attempts: 3
waited_seconds: 18.0
notifications: {}
response: null
status_before: "89020c"
status_after: "89020c"
status_changed: false
```

Every line is there to tell one kind of nothing from another.

- `write` says whether the machine took the frame. A refusal names the GATT
  error, which is the machine rejecting the command rather than ignoring it
- `subscribed` says whether an answer could have arrived at all. A null
  `response` means a refusal only when this is true: that is the machine
  offering `notify` and staying silent anyway. When it is false, or
  `response_properties` is null, the silence says nothing
- `listening` and `notifications` cover the answer arriving somewhere else.
  The action subscribes to every characteristic that can notify, so an empty
  `notifications` means the machine said nothing anywhere, not merely nothing
  where it was expected
- `status_before`, `status_after` and `status_changed` cover the machine acting
  without saying so. A machine that starts brewing changes its status byte
  whether or not it ever answers

The same record lands in the diagnostics download as `last_command`, so a brew
button press reads the same way, minus the extra subscriptions.

### Watching the machine

`nespresso.watch` holds the connection open and records everything that moves:
every characteristic whose value changes, every notification, each with the
number of seconds since the watch started. Start it, then walk over and use the
machine by hand.

It exists because the poll runs once a minute and a brew or a frothing cycle is
over before the next one. It is also the only way to identify a characteristic
the official app never mentions, since those all read as zeros while the
machine is idle and only mean something while it works.

```yaml
action: nespresso.watch
data:
  config_entry_id: <your entry>
  seconds: 90
```

The result lists every characteristic with its service and GATT properties, the
first value seen for each, then the changes and notifications in order:

```yaml
samples: 28
changes:
  - at: 12.4
    uuid: 06aa3a12-f22a-11e3-9daa-0002a5d5c51b
    was: "4082010001003f00"
    now: "4082010004003f00"
notifications:
  - at: 12.6
    uuid: 06aa3a52-f22a-11e3-9daa-0002a5d5c51b
    value: "0305..."
```

The auth characteristic is never read. Events are capped, and `truncated` says
so if the cap was hit. The record is also in the diagnostics download as
`last_watch`.

### Collecting diagnostics for an issue

Add this to `configuration.yaml` and restart:

```yaml
logger:
  logs:
    custom_components.nespresso: debug
```

Then let one poll go by, and download the diagnostics from the device page,
three dot menu, **Download diagnostics**.

Debug logging is what produces `gatt_characteristic_dump`, a list of every
service and characteristic the machine exposes, each with its GATT properties
and its value. It is the most useful single artefact for anything protocol
related, because it says what the machine actually offers rather than what the
app expects. The auth token is redacted from it. The serial number is not: it
is printed on the machine, and its platform code is what names the model.

## Support

If you find this integration useful, you can support its development:

[![PayPal](https://img.shields.io/badge/PayPal-Donate-blue.svg?logo=paypal)](https://www.paypal.me/RenaudAllard)

## Contributing

To submit this integration to the HACS default repository:

1. Ensure it meets the [HACS requirements](https://hacs.xyz/docs/publish/integration)
2. Fork [hacs/default](https://github.com/hacs/default)
3. Add the repository URL to the `integration` file
4. Submit a pull request
