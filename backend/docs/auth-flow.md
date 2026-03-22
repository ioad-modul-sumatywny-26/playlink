# Identity Authentication Flow

This document describes the challenge-response authentication mechanism used by Playlink.

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Browser as Client (Browser)
    participant Backend as FastAPI (Auth Service)
    participant Svelte as SvelteKit (BFF)
    participant DB as PostgreSQL

    Note over User,Browser: Phase 1: Request Challenge
    User->>Browser: Enter 12-word mnemonic
    Browser->>Browser: Derive Address (local only)
    Browser->>Backend: POST /auth/request-nonce { "address": "0x..." }
    Backend->>DB: Upsert User (identity_address, random username)
    Backend->>Backend: Generate random UUID (nonce)
    Backend->>Backend: Hash Nonce (SHA-256)
    Backend->>DB: Invalidate old nonces for address
    Backend->>DB: Store hashed nonce (TTL: 5m)
    Backend-->>Browser: { "nonce": "uuid-..." }

    Note over Browser: Phase 2: Local Signing
    Note right of Browser: Message: "Sign in to Playlink\nNonce: <uuid>"
    Browser->>Browser: Sign message with Private Key

    Note over Browser,Backend: Phase 3: Verification
    Browser->>Backend: POST /auth/verify { "address": "0x...", "nonce": "...", "signature": "0x..." }
    Backend->>Backend: Hash provided nonce
    Backend->>DB: Fetch matching unused/unexpired hashed nonce

    alt Nonce found
        Backend->>Backend: Recover address from signature
        alt Signature valid
            Backend->>DB: Mark nonce as used
            Backend->>DB: Update user.last_login
            Backend->>Backend: Generate JWT (sub: address, username: string)
            Backend-->>Browser: { "token": "jwt...", "username": "..." }
        else Signature Invalid
            Backend-->>Browser: 401 Identity verification failed
        end
    else Nonce Invalid/Expired
        Backend-->>Browser: 401 Invalid or expired challenge
    end

    Note over Browser,Svelte: Phase 4: Secure Session
    Browser->>Svelte: POST /auth?/login { "token": "jwt..." }
    Svelte->>Browser: Set-Cookie session=jwt (httpOnly, Secure)
    Svelte-->>Browser: 200 OK / Success
```

## Key Security Features

### 1. Replay Protection
- Nonces are **one-time use** (`used` flag in DB).
- Requesting a new nonce **invalidates** all previous ones for that address.
- Nonces have a short **TTL** (default: 5 minutes).

### 2. Database Integrity
- The database only stores the **SHA-256 hash** of the nonce.
- This prevents "pre-signing" attacks if the database is compromised.

### 3. Non-Custodial
- The private key **never leaves the client**.
- The backend only verifies the proof of ownership.

### 4. XSS Protection (BFF Pattern)
- The JWT is stored in an **httpOnly cookie** by the SvelteKit server.
- This prevents malicious browser scripts from stealing the session token.

### 5. Identity Normalization
- All addresses are converted to **EIP-55 checksum format** before storage or lookup.
- Users are assigned a random persistent `username` upon first registration.
