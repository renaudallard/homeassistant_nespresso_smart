# Authentication Documentation

The Nespresso Smart app uses OAuth2 with PKCE (Proof Key for Code Exchange) for secure user authentication.

## Table of Contents

- [Authentication Flow](#authentication-flow)
- [PKCE Implementation](#pkce-implementation)
- [Token Management](#token-management)
- [Cookie Management](#cookie-management)
- [Data Persistence](#data-persistence)

---

## Authentication Flow

### Login Flow

```
1. User enters email/password
2. App calls requestAuthToken(email, password)
   -> Returns: AuthToken { token }

3. App generates PKCE code_verifier (64 random bytes, Base64 encoded)
4. App generates code_challenge = SHA-256(code_verifier), Base64URL encoded

5. App calls requestAuthorizationCode(token, code_challenge)
   -> Returns: AuthorizationCode { authorization_code }

6. App calls requestAccessToken(authorization_code, code_verifier)
   -> Returns: AccessToken { access_token, refresh_token }

7. access_token is used as Bearer token in all subsequent API calls
```

### Token Refresh Flow

```
1. Access token expires
2. App calls refreshAccessToken(refresh_token)
   -> Returns: new AccessToken { access_token, refresh_token }
3. Old tokens replaced with new ones
```

### Logout Flow

```
1. App calls revokeRefreshToken(refresh_token)
   -> Invalidates the refresh token server-side
2. App clears local token storage
3. App clears cookies
```

---

## PKCE Implementation

Source: `com.nestle.nespresso.idp.service.auth.PkceServiceImpl`

### Code Verifier Generation

```
1. Create SecureRandom instance
2. Generate 64 random bytes
3. Encode as Base64 (URL-safe, no padding)
4. Result: 86-character random string
```

### Code Challenge Generation

```
1. Take code_verifier string
2. Compute SHA-256 hash
3. Encode as Base64 (URL-safe, no padding)
4. Algorithm parameter: "SHA-256" (default)
```

This follows RFC 7636 (PKCE) for preventing authorization code interception attacks.

---

## Token Management

### Token Types

| Token | Purpose | Storage |
|-------|---------|---------|
| AuthToken | Initial authentication proof | Transient (not stored) |
| AuthorizationCode | PKCE exchange code | Transient (not stored) |
| AccessToken | API authorization bearer token | Persistent (encrypted) |
| RefreshToken | Token renewal credential | Persistent (encrypted) |

### Token Lifecycle

1. **Acquisition**: Obtained through login or registration flow
2. **Usage**: Attached as `Authorization: Bearer <access_token>` header
3. **Refresh**: When access_token expires, refresh_token obtains new pair
4. **Revocation**: On logout, refresh_token is revoked server-side

---

## Cookie Management

Source: `com.nestle.nespresso.idp.service.auth.CookieServiceImpl`

The app manages HTTP cookies from IDP responses using Android's CookieManager:

- `clearCookies()`: Clears all cookies and flushes storage
- `getCookie(url)`: Retrieves cookies for a specific URL

Cookies are used alongside tokens for session state management with the IDP service.

---

## Data Persistence

### Persistent Data Sources

Source: `com.nestle.p060us.nespresso.nespressosmartmachines.data.source.local.persistent`

| Data Source | Content |
|-------------|---------|
| PersistentAccountDataSource | Auth tokens, user credentials |
| PersistentPairingDataSource | Device pairing state, keys |
| PersistentPermissionDataSource | User permission grants |
| PersistentMachineDataSource | Registered machine registry |
| PersistentEnvironmentDataSource | Environment/URL configuration |
| PersistentPushStateDataSource | Push notification registration state |

These use Android DataStore or SharedPreferences for local encrypted storage.
