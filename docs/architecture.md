# App Architecture Documentation

Overview of the Nespresso Smart app's internal architecture, dependency injection, and third-party integrations.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Package Structure](#package-structure)
- [Dependency Injection](#dependency-injection)
- [Session Management](#session-management)
- [Repositories](#repositories)
- [Use Cases](#use-cases)
- [BLE SDK Layers](#ble-sdk-layers)
- [Third-Party SDKs](#third-party-sdks)
- [Data Persistence](#data-persistence)

---

## Architecture Overview

The app follows a **clean architecture** pattern with four layers:

```
UI Layer (Compose/ViewModel)
    |
Domain Layer (Use Cases, Entities, Repository Interfaces)
    |
Data Layer (Repository Implementations, Data Sources)
    |
Framework Layer (BLE SDK, Retrofit, AWS IoT, DI)
```

### Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Kotlin |
| UI Framework | Jetpack Compose |
| DI Framework | Hilt (Dagger 2) |
| Async | Kotlin Coroutines + Flow |
| Navigation | Jetpack Navigation Compose |
| Networking | Retrofit 2 + OkHttp 3 |
| JSON | Gson |
| BLE | SDataway custom SDK |
| IoT | AWS IoT Android SDK (MQTT) |
| Local Storage | DataStore / SharedPreferences |
| Analytics | Firebase Analytics, Adobe Experience Platform |
| Push | FCM, Salesforce Marketing Cloud, Adobe |

---

## Package Structure

### Main Application

```
com.nestle.us.nespresso.nespressosmartmachines/
    data/
        models/
            asset/          # Configuration assets (cups, volumes, videos)
            environment/    # Server environment definitions
        source/
            local/
                persistent/ # DataStore-based local data sources
    domain/
        entity/
            clock/          # Time-related entities
        model/              # Domain models (MachineType, User, UserMachine)
        repository/         # Repository interfaces
            resources/      # Resource repositories
        session/            # Session management
        usecase/            # Business logic use cases
            account/        # Account-related use cases
    navigation/             # Navigation graph definitions
    di/                     # Hilt DI modules
    ui/
        main/               # Main activity and composables
        screen/
            account/        # Account management screens
            auth/           # Authentication screens (login, splash, register)
            home/           # Home screen and sub-features
                bottombar/      # Bottom navigation
                coffeevolume/   # Coffee volume customization
                machinecare/    # Descaling, cleaning, rinsing
                recipes/        # Recipe management
                settings/       # Machine settings
            notification/   # Notification center
            pairing/        # Machine pairing flow
                addmachine/     # Add new machine
                instruction/    # Pairing instructions
                machinepairing/ # BLE pairing process
                permission/     # Permission requests
                plugin/         # Plugin machine support
                privacyinfo/    # Privacy information
                scanning/       # BLE scanning
                scanqr/         # QR code scanning
                turnonbt/       # Bluetooth enable prompt
                wifinetwork/    # WiFi network selection
            qrcode/         # QR code display
            support/        # Customer support
    util/                   # Utility classes and constants
        push/               # Push notification utilities
```

### BLE SDKs (SDataway)

```
com.sdataway/
    ble2/               # Core BLE protocol layer
        AbstractCharacteristicHelper   # Base characteristic wrapper
        BasicCharacteristic            # Simple byte wrapper
        BSTProtocol                    # Byte Sequence Transfer protocol
        BSTBuffer, BSTBatch, BSTSnData # BST data structures
        ByteBufferManager              # Bit/byte manipulation
        Converter                      # Data format conversions
        ScanService                    # BLE device scanning
    barista/
        sdk/
            GATTattributes/    # Barista BLE UUIDs
            characteristics/   # GATT characteristic helpers
            models/            # Data models (commands, recipes, status)
            Utils              # Barista utilities
        machine/
            machine/
                actions/
                    model/     # Action option models
    vertuonext/
        sdk/
            GATTattributes/    # Vertuo Next BLE UUIDs
            characteristics/   # GATT characteristic helpers
            models/            # Data models
            Utils              # Vertuo Next utilities
        machine/
            machine/
                actions/
                    model/     # Action option models
    vmini/
        sdk/
            GATTattributes/    # VMini BLE UUIDs
            characteristics/   # GATT characteristic helpers
            models/            # Data models
            Utils              # VMini utilities
        machine/
            machine/
                actions/
                    model/     # Action option models
```

### Cloud Services

```
com.nestle.nespresso/
    idp/                    # Identity Provider
        interceptor/        # HTTP interceptors
        model/auth/         # Auth data models
        register/           # Registration flows
        service/auth/       # Auth service (PKCE, cookies)
        util/               # IDP utilities
    model/
        customers/          # Customer models
        machine/            # Machine cloud models
        recipes/            # Recipe models
        store/              # Store models
    service/                # Retrofit service interfaces
    token/                  # Token management
    provider/               # Data providers
    push/                   # Push notification handling

com.nestle.mse.iot.commons/
    models/                 # AWS IoT configuration models
    Crypto                  # AES encryption
    TelemetryMessageGenerator
    MessageBuilder
    TopicHelper

com.nestle.us.nespresso.iot/
    model/                  # IoT machine models
    di/                     # IoT DI modules
    provider/               # IoT data providers
```

---

## Dependency Injection

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.di`

### Hilt Configuration

The app uses **Hilt** (built on Dagger 2) with `SingletonComponent` scope.

### Coroutine Dispatchers

Source: `AppDispatcher`, `CoroutineScopeModule`

Three dispatcher qualifiers:

| Qualifier | Dispatcher | Usage |
|-----------|-----------|-------|
| @Default | Dispatchers.Default | CPU-intensive work |
| @IO | Dispatchers.IO | Network/disk I/O |
| @UI | Dispatchers.Main | UI thread updates |

### Initialization Phases

**Phase 1: Unauthenticated Initializers** (run at app startup)
- `FirebaseRemoteConfigInitializer` - Remote configuration
- `OneTrustInitializer` - Privacy/consent management
- `StoreDataInitializer` - Store/location data

**Phase 2: Authenticated Initializers** (run after login)
- `TranslationInitializer` - Language/localization
- `UserDataInitializer` - User profile data

---

## Session Management

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.domain.session`

### SessionManager Interface

Provides reactive state management via Kotlin Flow:

| Property/Method | Type | Description |
|----------------|------|-------------|
| sessionState | StateFlow | Current session state |
| sessionEvent | SharedFlow | Session lifecycle events |
| configuration | SessionConfiguration | Language and location settings |
| initialize() | suspend | Run all initializers |

### SessionConfiguration

| Field | Description |
|-------|-------------|
| language | Current app language |
| location | Current market/region |

---

## Repositories

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.domain.repository`

24 repository interfaces defining the data access contracts:

### Core Repositories

| Repository | Description |
|------------|-------------|
| AccountDataRepository | Auth operations, login, register, tokens |
| UserDataRepository | User profile, preferences |
| MachineRepository | Machine CRUD, remote operations (~95 methods) |
| PairingRepository | BLE/WiFi pairing flow |
| CachedMachineRepository | Local machine cache |

### Feature Repositories

| Repository | Description |
|------------|-------------|
| NotificationRepository | Push notification handling |
| PushProviderRepository | Multi-provider push management |
| RecipeRepository | Coffee recipe data |
| PersistentDataStoreRepository | Local persistent storage |
| FirebaseRepository | Firebase Remote Config |

### Resource Repositories

Located in `domain/repository/resources/`:
- Configuration assets
- Machine care instructions
- Video content
- Localized strings

---

## Use Cases

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.domain.usecase`

Approximately 195 use cases organized by feature:

### Account Use Cases

- LoginUseCaseState
- LogoutUseCaseState
- RegisterUseCaseState
- UpdatePasswordUseCaseState
- UpdateEmailUseCaseState
- DeleteAccountUseCaseState
- PasswordRecoveryUseCaseState

### Machine Operation Use Cases

- StartDescalingUseCaseState / GetDescalingStatusUseCaseState
- StartRinsingUseCaseState / GetRinsingStatusUseCaseState
- StartEmptyingUseCaseState / GetEmptyingStatusUseCaseState
- StartFotaUseCaseState / GetFotaStatusUseCaseState
- StartWaterHardnessUseCaseState / GetWaterHardnessStatusUseCaseState
- StartCupCustomizationUseCaseState / GetCupCustomizationStatusUseCaseState
- StartSoftResetUseCaseState / GetSoftResetStatusUseCaseState
- StartHardResetUseCaseState / GetHardResetStatusUseCaseState
- StartReadCapsuleUseCaseState / GetReadCapsuleStatusUseCaseState
- StartKeepAliveUseCaseState / GetKeepAliveStatusUseCaseState

### Pairing Use Cases

- BLE scanning and device discovery
- WiFi network scanning and configuration
- QR code parsing
- Machine registration

### Analytics Use Cases

- TrackEventUseCase
- TrackScreenDisplayUseCase
- Performance tracing use cases

---

## BLE SDK Layers

The BLE communication follows a layered architecture:

```
Machine Action Layer (Barista/VertuoNext/VMini machine actions)
    |
Characteristic Helper Layer (typed read/write for each characteristic)
    |
Abstract Characteristic Layer (generic read/write/notify with timeouts)
    |
BST Protocol Layer (large data transfer protocol)
    |
Android BLE API (BluetoothGatt, BluetoothGattCharacteristic)
```

### Key Classes Per Layer

**Action Layer:**
- `BaristaRecipeOptions`, `VertuoNextRecipeOptions`, `VMiniRecipeOptions`
- `BaristaEventType`, `VertuoNextEventType`, `VMiniEventType`
- FOTA, DHCP, Machine Name options per family

**Characteristic Layer:**
- `CharacCommandReq` / `CharacCommandRsp` - Command protocol
- `CharacCMID` - Capsule Machine ID
- `CharacMachineStatus` - Status reading
- `CharacMachineInfo` - Hardware info
- `CharacSerialNumber` - Serial number

**Abstract Layer:**
- `AbstractCharacteristicHelper` - 30s timeouts, thread-safe via StaticBusyLocker
- `BasicCharacteristic` - Raw byte storage

**Protocol Layer:**
- `BSTProtocol` - Packet sequencing (20-byte packets, 18-byte payload)
- `BSTBuffer` / `BSTBatch` / `BSTSnData` - Data buffering with missing packet detection

---

## Third-Party SDKs

### Firebase

| Service | Purpose |
|---------|---------|
| Firebase Cloud Messaging | Push notification delivery |
| Firebase Analytics | Usage analytics |
| Firebase Crashlytics | Crash reporting |
| Firebase Remote Config | Feature flags, dynamic configuration |
| Firebase ML Kit | Machine learning features |

### Salesforce Marketing Cloud

| Feature | Purpose |
|---------|---------|
| Push Notifications | Marketing push campaigns |
| In-App Messaging | In-app marketing messages |
| Campaign Management | Campaign orchestration |
| Journey Orchestration | User journey flows |

### Adobe Experience Platform

| Feature | Purpose |
|---------|---------|
| Experience Platform SDK | Data collection |
| Identity Management | Cross-platform user identity |
| Real-Time CDP | Customer data platform |

### Other SDKs

| SDK | Purpose |
|-----|---------|
| OneTrust | Privacy consent management (GDPR/CCPA) |
| Adjust | Install attribution and tracking |
| AWS IoT Android SDK | MQTT communication with IoT Core |
| Lottie | Animated UI elements |
| CaveRock AndroidSVG | SVG rendering |

---

## Data Persistence

### Local Storage

| Store | Technology | Content |
|-------|-----------|---------|
| Account Data | DataStore | Tokens, credentials |
| Machine Data | DataStore | Machine registry, pairing state |
| Environment | DataStore | Server environment selection |
| Permissions | DataStore | Permission grants |
| Push State | DataStore | Push registration tokens |
| Pairing | DataStore | BLE pairing keys |

### Cache Strategy

- `CachedMachineRepository` provides an in-memory cache layer over persistent storage
- Machine status is refreshed from cloud on each app launch
- Recipe data is cached locally (max 13 recipes per machine)

### Activities

| Activity | Launch Mode | Orientation |
|----------|-------------|-------------|
| MainActivity | singleTask | Portrait |
| Registration Activities | Standard | Portrait |
