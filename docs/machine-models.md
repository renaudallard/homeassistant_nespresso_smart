# Machine Models Documentation

The Nespresso Smart app supports multiple machine types across three hardware families, each with distinct capabilities and BLE protocols.

## Table of Contents

- [Machine Types](#machine-types)
- [Hardware Families](#hardware-families)
- [Internal Code Names](#internal-code-names)
- [Machine Capabilities](#machine-capabilities)
- [Recipe Types](#recipe-types)
- [Recipe Structure (Barista)](#recipe-structure-barista)
- [Coffee Volume Configuration](#coffee-volume-configuration)
- [Machine Care Operations](#machine-care-operations)
- [User Machine Data Model](#user-machine-data-model)

---

## Machine Types

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.domain.model.MachineType`

| Enum Value | Display Name | Internal Code |
|------------|-------------|---------------|
| VertuoNext | Vertuo Next | VERTUO_NEXT |
| VertuoPop | Vertuo Pop | VERTUO_POP |
| VertuoPopPlus | Vertuo Pop+ | VERTUO_POP_PLUS |
| VertuoLattissima | Vertuo Lattissima | VERTUO_LATTISSIMA |
| VertuoCreatista | Vertuo Creatista | VERTUO_CREATISTA |
| VertuoUp | Vertuo Up | VERTUO_UP |
| Barista | Barista | WHITE |
| Generic | Generic | (default) |

---

## Hardware Families

### Vertuo Next (Venus Line)

**SDK:** `com.sdataway.vertuonext`
**BLE Protocol:** Venus protocol with WiFi support
**Machines:** VertuoNext, VertuoPop, VertuoPopPlus, VertuoLattissima, VertuoCreatista, VertuoUp

Features:
- BLE and WiFi connectivity
- AWS IoT cloud integration
- 28 machine states
- WiFi network scanning and configuration
- Capsule barcode reading
- Firmware over-the-air (FOTA) updates
- Descaling, cleaning, rinsing, emptying cycles
- Cup volume customization
- Water hardness configuration
- General user settings

### Barista (Original Line)

**SDK:** `com.sdataway.barista`
**BLE Protocol:** White/Barista protocol
**Machines:** Barista

Features:
- BLE-only connectivity
- 8 machine states
- Motor speed and induction heating control
- Recipe phases with precise motor/temperature/time settings
- Recipe management (insert, append, replace, delete, move)
- CRC-16 recipe validation
- Milk recipe support (via MILK_RECIPE_SERVICE)
- HMI (Human-Machine Interface) control
- Language configuration

### VMini (Vertuo Mini)

**SDK:** `com.sdataway.vmini`
**BLE Protocol:** VMini protocol (different UUID family)
**Machines:** Vertuo Mini

Features:
- BLE and WiFi connectivity
- Standard BLE Device Information Service
- Machine control point (request/response)
- Device shadow synchronization
- Firmware over-the-air (FOTA)
- WiFi configuration
- Machine token authentication

---

## Internal Code Names

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.data.models.asset.MachineVideos`

| Code Name | Machine Type | MappingUtils Constant |
|-----------|-------------|----------------------|
| creatista | VertuoCreatista | VERTUO_CREATISTA |
| lattissima | VertuoLattissima | VERTUO_LATTISSIMA |
| venus | VertuoNext | VERTUO_NEXT |
| venusMoon | VertuoPopPlus | VERTUO_POP_PLUS |
| venusOne | VertuoPop | VERTUO_POP |
| venusMini | VertuoUp | VERTUO_UP |
| white | Barista | WHITE |

---

## Machine Capabilities

Source: `com.nestle.nespresso.model.machine.MachineCapability`

Capabilities are retrieved from the cloud API per machine profile:

```
MachineCapability {
    code: String     // capability identifier
    tags: List<String> // associated feature tags
}
```

### Known Capability Areas

Based on the remote function endpoints:
- Descaling
- Rinsing
- Emptying
- FOTA (firmware updates)
- Water hardness configuration
- Cup customization
- Soft reset
- Hard reset
- Capsule reading
- Keep alive

### Machine Mappings

Source: `com.nestle.nespresso.model.machine.MachineMapping`

Maps machines to compatible capsules and recipes:

```
MachineMapping {
    machineCode: String  // machine model identifier
    capsuleCode: String  // compatible capsule type
    recipeCode: String   // associated recipe (optional)
    purpose: String      // mapping purpose
    market: String       // target market
}
```

---

## Recipe Types

All three machine families support the same six base recipe types:

Source: `com.sdataway.barista.machine.machine.actions.model.BaristaRecipeType`
Source: `com.sdataway.vertuonext.machine.machine.actions.model.VertuoNextRecipeType`
Source: `com.sdataway.vmini.machine.machine.actions.model.VMiniRecipeType`

| Recipe Type | String Value |
|-------------|-------------|
| ESPRESSO | "espresso" |
| LUNGO | "lungo" |
| EXTRALUNGO | "extralungo" |
| CAPPUCCINO | "cappuccino" |
| LATTEMACCHIATO | "lattemacchiato" |
| CUSTOM | "custom" |

### Recipe Temperature

Source: `com.nestle.p060us.nespresso.iot.model.RecipeTemperature`

| Value | Description |
|-------|-------------|
| HOT | Standard hot coffee |
| COLD | Cold brew / iced coffee |

### Recipe Options (Barista)

Source: `com.sdataway.barista.machine.machine.actions.model.BaristaRecipeOptions`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| volume | Integer | 3 | Coffee volume setting |
| venusRecipe | BaristaRecipeType | LUNGO | Recipe type |
| temperature | Integer | 80 | Temperature in Celsius |
| customer | String | "anonymous" | Customer identifier |

---

## Recipe Structure (Barista)

Source: `com.sdataway.barista.sdk.models.WhiteRecipe`

The Barista machine uses a detailed recipe format:

### WhiteRecipe

```
WhiteRecipe {
    crcCode: short (2 bytes)       // CRC-16 checksum
    id: UUID                        // 16-byte recipe UUID
    name: String                    // ASCII name with length prefix
    steps: List<Step>               // Ordered brewing steps
}
```

### Step

Each step contains one or more phases:

### Phase

```
Phase {
    motorSpeed: int      // 300-4000 RPM
    acceleration: int    // 50-2000
    temperature: int     // 0-70 C
    durationSeconds: int // 0-240 seconds
}
```

Serialized as 6 bytes in MSB format.

### CRC Validation

Recipes are validated with CRC-16 using polynomial 4129 (0x1021). The CRC covers the recipe payload bytes to ensure data integrity during BLE transfer.

### Maximum Recipes

Source: `Constants.java`

```
MAX_RECIPES_STORED = 13
```

---

## Coffee Volume Configuration

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.data.models.asset.Volume`

```
Volume {
    low: ValueTitle      // minimum volume
    target: ValueTitle   // default/recommended volume
    high: ValueTitle     // maximum volume
}
```

### Cup Model

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.data.models.asset.Cup`

```
Cup {
    id: String
    index: Integer
    size: String
    hint: String
    image: String
    imageDetail: String
    volume: Volume          // low/target/high
    deltaTemp: DeltaTemp    // temperature offset
    banners: List<CupCustomizationBanner>
}
```

### Null Coffee Family ID

```
NULL_COFFEE_FAMILY_ID = 255
```

Used when no capsule family is detected or applicable.

---

## Machine Care Operations

### Event Types

Source: `com.sdataway.barista.machine.machine.actions.model.BaristaEventType`
Source: `com.sdataway.vertuonext.machine.machine.actions.model.VertuoNextEventType`

| Event | Description |
|-------|-------------|
| DESCALING | Descaling cycle event |
| WATER_HARDNESS | Water hardness configuration event |

### Machine Care Failure Codes

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.util.MachineCareFailureCodes`

| Code | Name | Description |
|------|------|-------------|
| 17509 | NO_MACHINE_CONNECTION | Cannot connect to machine |
| 17519 | MACHINE_BUSY | Machine is currently busy |

### Machine Care Configuration

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.data.models.asset.MachineCareConfiguration`

Defines the complete machine care flow with steps, loops, videos, and instructions per machine type.

### Water Hardness

Source: `com.nestle.p060us.nespresso.iot.model.IoTWaterHardnessLevel`

```
IoTWaterHardnessLevel {
    level: Int  // default: 0
}
```

---

## User Machine Data Model

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.domain.model.UserMachine`

Complete representation of a user's registered machine (24 fields):

| Field | Type | Description |
|-------|------|-------------|
| id | String | Cloud machine ID |
| type | String | Machine type code |
| productId | String | Product identifier |
| legacyProductId | String | Legacy product ID |
| serialNumber | String | Device serial number |
| machineType | MachineType | Enum type |
| purchaseMethod | String | How machine was purchased |
| pointOfSalesId | String | Purchase location ID |
| purchaseDate | String | Date of purchase |
| pairingKey | String | BLE pairing key |
| macAddress | String | BLE MAC address |
| secret | String | Device secret |
| category | String | Machine category |
| name | String | Default machine name |
| machineId | String | Internal machine ID |
| imageUrl | String | Machine image URL |
| machineStatus | UserMachineStatusResponse | Cloud status (nullable) |
| machinePresence | UserMachinePresenceResponse | Online presence (nullable) |
| machineCapabilities | List<MachineCapability> | Capability list (nullable) |
| customName | String | User-assigned name |
| wiFiMacAddress | String | WiFi MAC address |
| wiFiName | String | Connected WiFi network |
| machineSerialized | String | Serialized machine data |
| isMachinePaired | Boolean | BLE pairing status (nullable) |

### Machine Status Info

Source: `com.nestle.nespresso.model.machine.MachineStatusInfo`

| Field | JSON Key | Description |
|-------|----------|-------------|
| NM | "NM" | Machine name/model (nullable) |
| FWR | "FWR" | Firmware revision (nullable) |
| HWR | "HWR" | Hardware revision (nullable) |
