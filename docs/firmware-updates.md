# Firmware Updates (FOTA)

Source: `com.nestle.mse.iot.fota.lib.IotSdkFotaLibDescription`,
`com.sdataway.*.machine.updateupload.impl.UploadFilesHelperImpl`,
`com.sdataway.*.machine.updatecrypto.impl.UpdateFileCryptoImpl`,
`com.sdataway.*.machine.utils.crypto.impl.CryptoImpl`

Nothing in this integration performs firmware updates, and nothing here is
needed to use it. This is written down because firmware is the only artefact
that could settle questions the protocol cannot, such as which commands a given
machine's handler table actually implements.

## Contents

- [The pipeline](#the-pipeline)
- [The manifest](#the-manifest)
- [File encryption](#file-encryption)
- [Where the plaintext exists](#where-the-plaintext-exists)
- [Routes to a firmware file](#routes-to-a-firmware-file)

---

## The pipeline

Four stages, split between the cloud SDK and the per-family BLE SDK:

1. **Check.** `FotaLibDescription.checkForUpdate(machine, nonceObject, market,
   callback)` goes out over AWS IoT MQTT through `DataHubService`, with the
   topic built by `AwsTopicHelper`. The response is an update manifest.
2. **Download.** `getFiles(filesToDownload, callback)` fetches the assets with
   OkHttp, a `HEAD` for the size followed by a `GET` for the bytes. The
   requests carry no authentication of their own; the URL is the credential.
   `awsJobPresignedUrlConfig` and `PresignedUrlConfig` in the dex say those
   URLs are minted per job and expire.
3. **Offer to the machine.** `Machine.checkManifest(manifest, callback)` hands
   the manifest over so the machine decides what it needs, tracked through
   `CheckManifestState`.
4. **Upload.** `UploadFilesHelper.validateAndSendFileBytes(fileContent, hash)`
   verifies, decrypts and sends. Progress is reported through
   `UpgradeStates`: `FILE_DOWNLOADED`, `FILE_NOT_VALIDATED`,
   `FILE_NOT_DECRYPTED`.

The cloud side also exposes `startFota`, `getFotaStatus` and `cancelFota` as
one of the seven ECAPI remote operations, see [API Endpoints](api-endpoints.md),
and the device shadow reports `fotaAssets`, a list of `FotaAsset` carrying `DT`
and `FWR`, see [AWS IoT](aws-iot.md).

## The manifest

JSON with abbreviated keys. `UpdateManifestResponse`:

| Key | Field |
|-----|-------|
| `DID` | deployId |
| `AL` | assets |
| `STR` | statusResponse |

Each entry of `AL` is an `AssetResponse`:

| Key | Field | Notes |
|-----|-------|-------|
| `DT` | deployType | |
| `MTD` | firmwareMetadata | |
| `CH` | chunks | a list, so an asset arrives in pieces |
| `SHA` | hash | whole asset |
| `CSHA` | hashes | per chunk |
| `SIG` | signature | |
| `MSIG` | manufacturerSignature | two signatures, not one |

There is no URL field anywhere in the manifest. The addresses to fetch arrive
separately, as the `filesToDownload` map handed to `getFiles`.

## File encryption

`UpdateFileCryptoImpl` delegates to `Crypto.decrypt`, which is
**AES/ECB/PKCS5Padding** with a **hardcoded 16 byte key**, so AES-128 in ECB
mode with no IV and no per-device material.

The key is built by `CryptoImpl` from a list of integer literals, in a method
that takes no arguments and reads no state. The same constant appears in all
three SDKs, `com.sdataway.vertuonext`, `com.sdataway.barista` and
`com.sdataway.vmini`, so one key covers every machine the app supports.

The key itself is deliberately not reproduced here. It is recoverable in a few
minutes by anyone who decompiles the APK and reads that method, but publishing
a working key to encrypted firmware is a different thing from documenting a
protocol, and nothing in this project needs it.

## Where the plaintext exists

`UploadFilesHelperImpl.validateAndSendFileBytes` does three things in this
order:

1. `validator.verifyFile(fileContent, hash)`, against the **encrypted** bytes
2. `fileCrypto.decryptFile(fileContent)`
3. sends the **decrypted** buffer onward to the machine

So the phone decrypts and the machine receives plaintext. Whatever transport
carries stage 4 carries firmware in the clear.

**Which transport that is, is not established.** `UploadFilesHelper` exists in
the `vertuonext` SDK, so the app is capable of pushing to a Vertuo, but a Vertuo
has wifi of its own and reports `updating_combo_firmware` and
`updating_firmware` WiFi states, which is what a machine fetching its own
firmware would look like. The VMini has an explicit BLE channel for it,
`CHAR_FOTACOMMAND` and `CHAR_FOTASTATUS`. The Vertuo GATT table in the app has
no FOTA characteristic at all.

Worth noting against that: a Vertuo Creatista exposes three write-only
characteristics the app never mentions, `06AA3A1B`, `06AA3A34` and `06AA3A59`.
A firmware upload channel would be write-only and absent from the app's table,
so they are candidates and nothing more.

## Routes to a firmware file

In order of cost, for anyone who wants to try:

1. **Capture the Bluetooth traffic during an update.** If the machine takes its
   firmware over BLE, this yields plaintext with no key, no cloud access and no
   certificates. Same procedure as the auth token capture in the README.
2. **Intercept the download.** mitmproxy with a user CA on the phone, assuming
   OkHttp is not pinned, yields the encrypted asset, which the key above
   decrypts.
3. **Speak MQTT as the machine.** Gets the manifest and the URLs on demand
   rather than waiting for an update, and needs the machine's IoT certificates,
   which are in the machine.
4. **Read the flash.** SWD or JTAG on the board, independent of Nespresso
   entirely, and the only route that does not depend on an update being offered.

Routes 1 and 2 share one binding constraint: an update has to be genuinely
pending for the machine in question, and that cannot be summoned. A machine on
current firmware gives you nothing to capture.
