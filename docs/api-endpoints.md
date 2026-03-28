# API Endpoints Documentation

The Nespresso Smart app communicates with several backend services for machine management, user account operations, and IoT device control.

## Table of Contents

- [Environment URLs](#environment-urls)
- [Machine Management (ECAPI)](#machine-management-ecapi)
- [User Account (IDP)](#user-account-idp)
- [Registration](#registration)
- [Other ECAPI Services](#other-ecapi-services)
- [Push Notification Services (NCS)](#push-notification-services-ncs)
- [HTTP Client Configuration](#http-client-configuration)

---

## Environment URLs

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.data.models.environment.ServerEnvironment`

The app supports four server environments. Default is PRODUCTION.

### ECAPI (E-Commerce API)

| Environment | Base URL |
|-------------|----------|
| PRODUCTION | `https://www.nespresso.com/` |
| VST (Staging) | `https://www-staging.nespresso.com/` |
| ROLLOUT | `https://nc2-env-rollout.nespresso.com/` |
| NESINT2 | `https://nc2-env-int2.nespresso.com/` |

### NCS (Nespresso Cloud Services / Mobile API)

| Environment | Base URL |
|-------------|----------|
| PRODUCTION | `https://api.nespresso.com/prd/mobile-1.0/` |
| VST (Staging) | `https://api-stg.nespresso.com/vst/mobile-1.0/` |
| ROLLOUT | `https://mobile-env-rol.nespresso.com/rol/mobile-1.0/` |
| NESINT2 | `https://mobile-env-int2.nespresso.com/int/mobile-1.0/` |

---

## Machine Management (ECAPI)

Source: `com.nestle.nespresso.service.RetrofitEcapiServiceMachines`

All endpoints use dynamic path variables (`{path}`) with `@HeaderMap` and `@QueryMap` parameters.

### User Machine CRUD

| Method | Operation | Description |
|--------|-----------|-------------|
| POST | createUserMachine | Register a machine to user account |
| PUT | updateUserMachine | Update machine configuration |
| GET | getUserMachines | List all user's registered machines |
| DELETE | deleteUserMachine | Remove machine from account |

### Machine Status and Info

| Method | Operation | Description |
|--------|-----------|-------------|
| GET | getUserMachineStatus | Current machine operational status |
| GET | getUserMachinePresence | Machine online/offline presence |
| GET | getUserMachineInfo | Hardware and firmware information |
| GET | getUserMachineProfile | Machine profile data |
| GET | getUserMachineProfileCapabilities | List of machine capabilities |
| GET | getUserMachineProfileCapabilitiesForVenus | Capabilities for Venus (Vertuo) machines |
| GET | getUserMachineProfileMappings | Profile-to-capsule mappings |
| GET | getLastValidConfiguration | Last known good configuration |

### Remote Operations

Each remote operation follows a three-endpoint pattern: start, status, cancel.

#### Descaling

| Method | Operation | Description |
|--------|-----------|-------------|
| POST | startDescaling | Initiate descaling cycle |
| GET | getDescalingStatus | Poll descaling progress |
| DELETE | cancelDescaling | Abort descaling |

#### Rinsing

| Method | Operation | Description |
|--------|-----------|-------------|
| POST | startRinsing | Initiate rinsing cycle |
| GET | getRinsingStatus | Poll rinsing progress |
| DELETE | cancelRinsing | Abort rinsing |

#### Emptying

| Method | Operation | Description |
|--------|-----------|-------------|
| POST | startEmptying | Initiate water emptying |
| GET | getEmptyingStatus | Poll emptying progress |
| DELETE | cancelEmptying | Abort emptying |

#### Firmware Update (FOTA)

| Method | Operation | Description |
|--------|-----------|-------------|
| POST | startFota | Initiate firmware update |
| GET | getFotaStatus | Poll update progress |
| DELETE | cancelFota | Abort firmware update |

#### Water Hardness

| Method | Operation | Description |
|--------|-----------|-------------|
| POST | startWaterHardness | Set water hardness level |
| GET | getWaterHardnessStatus | Poll configuration progress |
| DELETE | cancelWaterHardness | Abort configuration |

#### Keep Alive

| Method | Operation | Description |
|--------|-----------|-------------|
| POST | startKeepAlive | Send keep-alive ping |
| GET | getKeepAliveStatus | Poll keep-alive status |
| DELETE | cancelKeepAlive | Cancel keep-alive |

#### Cup Customization

| Method | Operation | Description |
|--------|-----------|-------------|
| POST | startCupCustomization | Set custom cup volume |
| GET | getCupCustomizationStatus | Poll customization progress |
| DELETE | cancelCupCustomization | Abort customization |

#### Soft Reset

| Method | Operation | Description |
|--------|-----------|-------------|
| POST | startSoftReset | Initiate soft reset |
| GET | getSoftResetStatus | Poll reset progress |
| DELETE | cancelSoftReset | Abort soft reset |

#### Hard Reset

| Method | Operation | Description |
|--------|-----------|-------------|
| POST | startHardReset | Initiate factory reset |
| GET | getHardResetStatus | Poll reset progress |
| DELETE | cancelHardReset | Abort hard reset |

#### Read Capsule

| Method | Operation | Description |
|--------|-----------|-------------|
| POST | startReadCapsule | Initiate capsule reading |
| GET | getReadCapsuleStatus | Poll read progress |
| DELETE | cancelReadCapsule | Abort capsule read |

### Response Models

| Model | Fields |
|-------|--------|
| UserMachineResponse | id, type, productId, serialNumber, name, machineId, imageUrl, macAddress, etc. |
| UserMachineStatusResponse | machineStatus, errorCode, descalingAlert, etc. |
| UserMachinePresenceResponse | online/offline presence state |
| UserMachineInfoResponse | hardware info, firmware versions |
| UserMachineProfileResponse | profile data, capsule mappings |
| RemoteFunctionResponse | operation status for all remote functions |
| MachineCapability | code (String), tags (List<String>) |
| MachineMapping | machineCode, capsuleCode, recipeCode, purpose, market |

### ReportedStatus (Cloud Shadow)

Source: `com.nestle.nespresso.model.machine.ReportedStatus`

Machine status as reported via cloud (15 fields):

| Field | Type | Description |
|-------|------|-------------|
| machineStatus | String | Current state |
| errorCode | String | Active error code |
| errorOrigin | String | Error source |
| descalingAlert | Boolean | Descaling needed flag |
| machineInfo | MachineStatusInfo | HW/FW revision info |
| fotaStatus | String | Firmware update status |
| fotaAssets | List<FotaAsset> | Available firmware files |
| milkUnitStatus | String | Milk frother status |
| volumeCustomization | String | Custom volume settings |
| temperatureCustomization | String | Custom temp settings |
| lastCoffeeFamilyID | Integer | Last brewed capsule family |
| firstCoffee | Boolean | First coffee flag |
| firstRinsing | Boolean | First rinse flag |
| recipeTag | String | Current recipe identifier |
| waterHardness | Integer | Water hardness level |

---

## User Account (IDP)

Source: `com.nestle.nespresso.idp.service.auth.RetrofitIdpServiceAuth`

### Authentication Endpoints

| Method | Operation | Description |
|--------|-----------|-------------|
| POST | requestAuthToken | Email/password login, returns auth token |
| POST | requestAuthorizationCode | PKCE authorization code request |
| POST | requestAccessToken | Exchange auth code for access + refresh tokens |
| POST | refreshAccessToken | Refresh expired access token |
| DELETE | revokeRefreshToken | Invalidate refresh token |

### Account Management

| Method | Operation | Description |
|--------|-----------|-------------|
| PUT | updateEmailAddress | Change account email |
| POST | updatePassword | Change account password |
| PATCH | updateUsername | Change display name |
| POST | deleteUserAccount | Request account deletion |

### Authentication Models

| Model | Fields |
|-------|--------|
| AuthToken | token (String) |
| AccessToken | access_token (String), refresh_token (String) |
| AuthorizationCode | authorization_code (String) |

### IDP Configuration

| Field | Description |
|-------|-------------|
| baseUrl | IDP service base URL |
| baseUrlNcs | NCS base URL |
| channel | B2C or B2B |
| country | User's country code |
| language | User's language code |
| deviceInfo | Device identification data |

---

## Registration

Source: `com.nestle.nespresso.idp.register.RetrofitIdpServiceRegister`

### Registration Endpoints

| Method | Operation | Description |
|--------|-----------|-------------|
| GET | getCustomerFields | Get required registration fields (standard) |
| GET | getCustomerFieldsProgressive | Get fields for progressive registration |
| GET | getMembershipFieldsProgressive | Get membership fields |
| POST | validateRegistrationAccount | Validate account data |
| PUT | getAccessTokenProgressive | Get token after progressive registration |
| POST | registerProgressive | Create account (progressive flow) |
| POST | linkAccount | Link to existing member account |

### Password Recovery

Source: `com.nestle.nespresso.idp.service.IdpServiceUser`

| Method | Operation | Description |
|--------|-----------|-------------|
| POST | requestPasswordRecovery | Send password reset email |

---

## Other ECAPI Services

Additional Retrofit service interfaces found in the codebase:

| Service | Description |
|---------|-------------|
| RetrofitEcapiServiceStores | Nespresso store/boutique information |
| RetrofitEcapiServiceRecipes | Coffee recipe data |
| RetrofitEcapiServiceCms | Content management system content |
| RetrofitEcapiServicePromotions | Promotional offers |
| RetrofitEcapiServiceCustomers | Customer profile data |
| RetrofitEcapiServicePois | Points of interest (store locations) |
| RetrofitEcapiServiceStocks | Product stock availability |

---

## Push Notification Services (NCS)

Source: `com.nestle.nespresso.ncs.service.NcsPushService`

### Configuration

| Field | Description |
|-------|-------------|
| baseUrl | NCS service URL |
| channel | NcsChannel (B2C or B2B) |
| country | Target country |
| language | Notification language |
| deviceInfo | Device identification |

### Push Providers

The app uses three push notification providers:

1. **Firebase Cloud Messaging (FCM)** - Primary push delivery
2. **Salesforce Marketing Cloud** - Marketing campaigns, in-app messages, journey orchestration
3. **Adobe Experience Platform** - Experience-driven notifications, identity management

---

## HTTP Client Configuration

Source: `com.nestle.nespresso.idp.interceptor`, ECAPI configuration classes

### Request Headers

All API requests include standard headers configured via interceptors:

| Header | Source |
|--------|--------|
| Device Name | `Build.MODEL` |
| Device Version | Android version string |
| Manufacturer | `Build.MANUFACTURER` |
| App Name | Application name |
| App Version | Application version |
| Channel | B2C or B2B |
| FrontEnd | ANDROID_APP or ANDROID_APP_V2 |
| Country | User's country |
| Language | User's language |
| Device ID | Unique device identifier |

### Interceptor Framework

Source: `InterceptorType`

Interceptors can be scoped to specific endpoints using include/exclude lists, allowing different header configurations per API.
