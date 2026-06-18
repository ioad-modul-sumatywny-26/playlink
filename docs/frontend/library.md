# Frontend Library — Client-Logic Reference

This document describes the non-UI TypeScript/Svelte modules in `frontend/src/lib/`: authentication, chat-message signing, session key custody, WebSocket-backed stores (room list and per-room chat), a Svelte 5 runes hints context, and lobby-location helpers. The server-side `hooks.server.ts` and `app.d.ts` type augmentation are also covered here for completeness.

> **Source:** `frontend/src/lib/auth.ts`, `signing.ts`, `signingKey.ts`, `roomsStore.ts`, `chatStore.ts`, `hintsContext.svelte.ts`, `lobbyLocations.ts`, `frontend/src/hooks.server.ts`, `frontend/src/app.d.ts`

---

## Public Environment Variables

| Variable | Used In | Purpose | Default |
|---|---|---|---|
| `PUBLIC_BACKEND_URL` | `auth.ts` | Base URL for HTTP REST calls | `http://localhost:8000` |
| `PUBLIC_WS_URL` | `roomsStore.ts`, `chatStore.ts` | Base URL for WebSocket connections | `ws://localhost:8000` |

Both are accessed via `$env/dynamic/public` (`import { env } from '$env/dynamic/public'`).

---

## `auth.ts` — Identity Derivation and Authentication

Three-phase authentication flow using BIP39 mnemonics and EIP-191 (`personal_sign`) signatures. Uses ethers v6.

### `getIdentityFromMnemonic(phrase: string): HDNodeWallet`

Derives an `ethers.HDNodeWallet` (private/public key pair) from a 12-word BIP39 mnemonic phrase.

```ts
import { ethers, Mnemonic, HDNodeWallet } from 'ethers';

export function getIdentityFromMnemonic(phrase: string): HDNodeWallet {
    try {
        const mnemonic = Mnemonic.fromPhrase(phrase);
        return HDNodeWallet.fromMnemonic(mnemonic);
    } catch (e) {
        console.error('Wallet derivation failed:', e);
        throw new Error('Invalid mnemonic phrase');
    }
}
```

- **Input:** A space-delimited 12-word BIP39 phrase.
- **Output:** `HDNodeWallet` — `wallet.address` is the checksummed Ethereum address used as the user's identity.
- **Throws:** `Error('Invalid mnemonic phrase')` on parse/derivation failure.

### `generateMnemonic(): string`

Generates a fresh 12-word BIP39 mnemonic from 16 bytes of entropy.

```ts
export function generateMnemonic(): string {
    return Mnemonic.fromEntropy(ethers.randomBytes(16)).phrase;
}
```

- **Return:** A space-separated phrase of 12 BIP39 words.

### `signMessage(identity: HDNodeWallet, message: string): Promise<string>`

Signs an arbitrary string using ethers' `signMessage` (EIP-191 `personal_sign` prefix).

```ts
export async function signMessage(identity: HDNodeWallet, message: string): Promise<string> {
    return await identity.signMessage(message);
}
```

- **Input:** `identity` — an `HDNodeWallet` from `getIdentityFromMnemonic`; `message` — the raw text payload.
- **Return:** `0x`-prefixed hex signature string (65 bytes: `r || s || v`).

### `authenticate(mnemonicPhrase: string): Promise<{ token: string; address: string; username: string }>`

Performs the full three-phase authentication handshake with the backend.

#### Phase 1 — Request Nonce

```
POST {PUBLIC_BACKEND_URL}/auth/request-nonce?address=<checksummedAddress>
```

- **Query param:** `address` — the checksummed Ethereum address from `HDNodeWallet.address`.
- **Response (200):** `{ nonce: string }` — a UUID v4 challenge.
- **Errors:** 429 (rate-limited) — reads `error.error` field; other — reads `error.detail`.
- **No auth required** (rate-limited by source IP / address).

#### Phase 2 — Local Signing

The message string signed (`personal_sign` via `signMessage`):

```
Sign in to Playlink\nNonce: <nonce>
```

The literal newline is a single `\n` (U+000A) character. No trailing newline. This is the exact payload passed to `identity.signMessage()`.

#### Phase 3 — Verify

```
POST {PUBLIC_BACKEND_URL}/auth/verify
Content-Type: application/json

{
    "address": "<checksummedAddress>",
    "nonce": "<nonce>",
    "signature": "<0x-signed-message>"
}
```

- **Response (200):** `{ token: string; username: string }` — the JWT is also set as an httpOnly `session` cookie by the backend via `Set-Cookie`. The frontend extracts only `username` from the response body; `token` is informational.
- **Errors:** Reads `error.detail` from response body.

#### Return value

```ts
{ token: string; address: string; username: string }
```

**Side effect:** The private key is saved to `sessionStorage` via `saveSigningKey(identity.privateKey)` immediately after derivation (see [`signingKey.ts`](#signingkeyts--session-key-custody)).

#### Consumed by

[Routes](routes.md) that require an authenticated user (login page, room-creation forms).

---

## `signing.ts` — Chat Message Signing Contract

Per-message EIP-191 signing so the backend can cryptographically prove authorship (issue #59). The canonical payload string MUST match the backend's `_chat_signing_message` byte-for-byte (see [../backend/realtime.md](../backend/realtime.md)).

### `ChatSigner`

```ts
export interface ChatSigner {
    signMessage(message: string): Promise<string>;
}
```

Any object with a `signMessage` method returning a `0x`-hex EIP-191 signature — `ethers.HDNodeWallet` and `ethers.Wallet` both satisfy this interface.

### `buildChatSigningMessage(room: string, content: string, sentAt: string): string`

Constructs the canonical plaintext that is signed for a chat message.

```ts
export function buildChatSigningMessage(room: string, content: string, sentAt: string): string {
    return `PlayLink signed chat message\nroom=${room}\nsent_at=${sentAt}\ncontent=${content}`;
}
```

**Format (verbatim, with literal `\n` (U+000A) line breaks):**

```
PlayLink signed chat message
room=<room>
sent_at=<sentAt>
content=<content>
```

- `room`: the room name (already `encodeURIComponent`-encoded by the URL — here it is the plain room name the user sees).
- `sentAt`: ISO 8601 string from `new Date().toISOString()`.
- `content`: the trimmed message body.

### `signChatMessage(signer: ChatSigner, room: string, content: string, sentAt: string): Promise<string>`

Builds the canonical message via `buildChatSigningMessage` and signs it.

```ts
export async function signChatMessage(
    signer: ChatSigner,
    room: string,
    content: string,
    sentAt: string
): Promise<string> {
    return signer.signMessage(buildChatSigningMessage(room, content, sentAt));
}
```

- **Return:** `0x`-prefixed hex EIP-191 signature.

---

## `signingKey.ts` — Session Key Custody

Stores the BIP39-derived ECDSA private key in `sessionStorage` for the duration of the browser tab session. The key is **never persisted to disk, cookie, or `localStorage`** — it lives only in session-scoped memory.

**Security model:** The private key is XSS-exposed (the same exposure class as any in-page secret in a self-custody web app without a browser extension).

```ts
const STORAGE_KEY = 'playlink.sk';
```

### `saveSigningKey(privateKey: string): void`

Persists the signing key for the current tab session. No-op when not running in the browser (`$app/environment` `browser` guard).

```ts
export function saveSigningKey(privateKey: string): void {
    if (!browser) return;
    try {
        sessionStorage.setItem(STORAGE_KEY, privateKey);
    } catch (e) {
        console.error('Could not persist signing key', e);
    }
}
```

### `loadSigner(): Wallet | null`

Returns a signer for the stored key, or `null` when none is available or the stored key is invalid. Invalid keys are silently removed.

```ts
export function loadSigner(): Wallet | null {
    if (!browser) return null;
    const privateKey = sessionStorage.getItem(STORAGE_KEY);
    if (!privateKey) return null;
    try {
        return new Wallet(privateKey);
    } catch (e) {
        console.error('Stored signing key is invalid; discarding', e);
        sessionStorage.removeItem(STORAGE_KEY);
        return null;
    }
}
```

- **Return:** `ethers.Wallet` (satisfies `ChatSigner`) or `null`.

### `clearSigningKey(): void`

Forgets the signing key (called on logout). No-op when not in browser.

```ts
export function clearSigningKey(): void {
    if (!browser) return;
    sessionStorage.removeItem(STORAGE_KEY);
}
```

---

## `roomsStore.ts` — Live Room List Store

WebSocket-based store that maintains the list of active game rooms. Connects to `${PUBLIC_WS_URL}/ws/rooms`.

### `RoomSummary`

```ts
export interface RoomSummary {
    name: string;
    game: string;
    lobby_location: string;
    players_active: number;
    players_max: number;
    member_addresses: string[];
    description: string | null;
    communicator_link: string | null;
    requirements: string | null;
    expires_at: string;
}
```

### `isNullableString(value: unknown): value is string | null`

Type guard helper for nullable string fields.

```ts
export function isNullableString(value: unknown): value is string | null {
    return value === null || typeof value === 'string';
}
```

### `isRoomSummary(value: unknown): value is RoomSummary`

Validates an untrusted value against the `RoomSummary` shape. Every frame from the rooms WebSocket is validated through this guard.

```ts
export function isRoomSummary(value: unknown): value is RoomSummary {
    if (typeof value !== 'object' || value === null) return false;
    const room = value as Record<string, unknown>;
    return (
        typeof room.name === 'string' &&
        typeof room.game === 'string' &&
        typeof room.lobby_location === 'string' &&
        typeof room.players_active === 'number' &&
        typeof room.players_max === 'number' &&
        Array.isArray(room.member_addresses) &&
        isNullableString(room.description) &&
        isNullableString(room.communicator_link) &&
        isNullableString(room.requirements) &&
        typeof room.expires_at === 'string'
    );
}
```

### `roomsStore: Readable<RoomSummary[]> & { destroy(): void }`

A singleton store exported from the module. Created via a private `createRoomsStore()` factory.

```ts
export const roomsStore = createRoomsStore();
```

**WebSocket connection:**

- **URL:** `${PUBLIC_WS_URL}/ws/rooms`
- **Protocol:** Plain WebSocket (no authentication — room list is public).
- **Frame format:** Bare JSON array of `RoomSummary` objects. There is no wrapping `{ type: ... }` envelope; the raw array is validated with `Array.isArray(data) && data.every(isRoomSummary)`.
- **On message:** Parses JSON, validates as `RoomSummary[]`, then `set(data)` on the underlying writable.
- **Reconnect:** Exponential backoff with +50% random jitter:
  - Base delay: 1 000 ms
  - Max delay: 30 000 ms
  - Formula: `delay = min(30_000, 1_000 * 2^attempts) + random * (0.5 * exponential)`.

  Reconnect resets to 0 after a successful open.

- **`destroy()`:** Tears down the socket, clears pending reconnect timeouts, sets `isTornDown = true` to suppress future reconnects.

**Consumed by:** [Route components](routes.md) showing the lobby/room list.

---

## `chatStore.ts` — Per-Room Chat WebSocket Store

Factory-based store for a single room's chat. Each room gets its own `createChatStore()` instance.

### Public Types

#### `ChatMessage`

```ts
export interface ChatMessage {
    id: number;
    sender_address: string;
    sender_username: string;
    content: string;
    created_at: string;
    kind?: 'user' | 'system';
    /** EIP-191 signature, or null for legacy/unsigned. */
    signature?: string | null;
    /** Exact client timestamp that was signed, or null for legacy/unsigned. */
    sent_at?: string | null;
    /** True when the server recovered a valid signer. */
    verified?: boolean;
}
```

#### `RoomMember`

```ts
export interface RoomMember {
    address: string;
    username: string;
    is_admin: boolean;
}
```

#### `RsvpStatus`

```ts
export type RsvpStatus = 'present' | 'absent' | 'maybe';
```

#### `RsvpEntry`

```ts
export interface RsvpEntry {
    address: string;
    username: string;
    status: RsvpStatus;
    updated_at: string;
}
```

#### `RoomEventState`

```ts
export interface RoomEventState {
    starts_at: string;
    ends_at: string;
    created_by: string;
    created_at: string;
    updated_at: string;
    rsvps: RsvpEntry[];
}
```

### Validators

Each validator function checks the structural type at runtime, matching the exact field shapes above.

| Function | Signature |
|---|---|
| `isChatMessage` | `(value: unknown) => value is ChatMessage` |
| `isRoomMember` | `(value: unknown) => value is RoomMember` |
| `isRsvpStatus` | `(value: unknown) => value is RsvpStatus` |
| `isRsvpEntry` | `(value: unknown) => value is RsvpEntry` |
| `isRoomEventState` | `(value: unknown) => value is RoomEventState` |

### `parseFrame(raw: string): ChatFrame | null`

Parses and validates a raw WebSocket message string. Returns a discriminated `ChatFrame` object on success, or `null` when the JSON is malformed or the frame type is unknown.

**Frame types handled** (see [../backend/realtime.md](../backend/realtime.md) for the server-side spec):

| `type` | Extra Fields | Store Action |
|---|---|---|
| `history` | `messages: ChatMessage[]` | `messages.set(messages)` — replaces all |
| `message` | `message: ChatMessage` | `messages.update(msgs => [...msgs, msg])` |
| `event_update` | `event: RoomEventState \| null` | `event.set(event)` |
| `rsvp_update` | `rsvp: RsvpEntry` | `event.update()` — merges RSVP, dedicated by case-insensitive address |
| `roster_update` | `members: RoomMember[]` | `members.set(members)` — replaces all |
| `room_closed` | `room: string` | `closed.set(true)`; `isTornDown = true`; socket closed |
| `member_kicked` | `member_address, member_username, created_by, ownership_transferred: boolean` | `owner.set(created_by)`; if `member_address` matches `options.currentAddress`, `kicked.set(true)` and `isTornDown = true` |
| `error` | `detail: string` | `console.warn('Chat message rejected:', detail)` |

### `ChatStore`

```ts
export interface ChatStore {
    messages: Readable<ChatMessage[]>;
    event: Readable<RoomEventState | null>;
    members: Readable<RoomMember[]>;
    closed: Readable<boolean>;
    owner: Readable<string>;
    kicked: Readable<boolean>;
    send(content: string): Promise<void>;
    destroy(): void;
}
```

| Readable | Initial Value | Description |
|---|---|---|
| `messages` | `[]` | Live chat history for the room. |
| `event` | `options.initialEvent ?? null` | Current scheduled event (or null when none). |
| `members` | `options.initialMembers ?? []` | Live room roster, updated on join/leave. |
| `closed` | `false` | Becomes `true` when an admin closes the room (`room_closed`). |
| `owner` | `options.initialOwner ?? ''` | Current room owner address. Updated after a creator kick. |
| `kicked` | `false` | Becomes `true` when this client is removed from the room. |

### `CreateChatStoreOptions`

```ts
export interface CreateChatStoreOptions {
    initialEvent?: RoomEventState | null;
    initialMembers?: RoomMember[];
    initialOwner?: string;
    currentAddress?: string;
    signer?: ChatSigner | null;
}
```

| Option | Purpose |
|---|---|
| `initialEvent` | Pre-populated event state from SSR, avoids flash of empty content. |
| `initialMembers` | Pre-populated roster from SSR, used until first WS update. |
| `initialOwner` | Room owner address from SSR. |
| `currentAddress` | Address of this browser session. Used for kick self-detection. |
| `signer` | Key for signing outgoing messages (issue #59). When absent, messages sent unsigned. |

### `createChatStore(roomName: string, token: string, options?: CreateChatStoreOptions): ChatStore`

Factory that returns a `ChatStore` for a specific room.

**WebSocket connection:**

- **URL:** `${PUBLIC_WS_URL}/ws/rooms/${encodeURIComponent(roomName)}/chat?token=${encodeURIComponent(token)}`
- **Auth:** JWT passed as query parameter (browsers cannot set custom WebSocket headers).
- **Reconnect:** Same exponential backoff as `roomsStore` (base 1 000 ms, max 30 000 ms, +50% jitter). Reconnect is suppressed after `closed`, `kicked`, or close codes 4403/4409.

**Send behavior** — `async send(content: string): Promise<void>`:

1. Trims `content`. No-ops if empty or socket not `OPEN`.
2. If `options.signer` is set, generates `sentAt = new Date().toISOString()`, calls `signChatMessage(signer, roomName, trimmed, sentAt)`, and sends `{"content": "<trimmed>", "sent_at": "<sentAt>", "signature": "<0x-hex>"}`.
3. On signing failure, falls back to unsigned `{"content": "<trimmed>"}` with `console.error`.
4. If no signer, sends unsigned `{"content": "<trimmed>"}`.

**Close code handling:**

| Close Code | Behavior |
|---|---|
| 4403 | Not a member of this room — `kicked.set(true)`, no reconnect. |
| 4409 | Unknown room — `kicked.set(true)`, no reconnect. |
| Others | Schedule reconnect (unless torn down). |

### Lifecycle

```ts
const store = createChatStore(roomName, token, { signer, currentAddress });
// ... use store.messages, store.send(...) ...
store.destroy();  // tear down socket, cancel reconnect
```

**Consumed by:** [Route components](routes.md) for the per-room chat page. See also [../backend/realtime.md](../backend/realtime.md) for the WebSocket frame protocol from the server side.

---

## `hintsContext.svelte.ts` — Svelte 5 Runes Hints System

Reactive context for populating contextual hint/tooltip overlays. Uses Svelte 5 `$state` runes.

### `HintTone`

```ts
export type HintTone = 'gold' | 'green' | 'amber' | 'red' | 'stone' | 'blue';
```

### `HintEntry`

```ts
export interface HintEntry {
    key: string;
    label: string;
    tone?: HintTone;
    onclick?: () => void;
}
```

### `HintsState`

```ts
export class HintsState {
    hints = $state<HintEntry[]>([]);

    constructor(initial: HintEntry[] = []) {
        this.hints = initial;
    }

    set(entries: HintEntry[]): void {
        this.hints = entries;
    }

    clear(): void {
        this.hints = [];
    }
}
```

- `hints` is a reactive `$state` field — any Svelte component reading it via `getHintsState()` will re-render when it changes.

### `provideHints(initial?: HintEntry[]): HintsState`

Creates a `HintsState` and sets it in the Svelte component context under a `Symbol('hints')` key. Should be called once in a layout or page component (during `<script>` initialization).

```ts
export function provideHints(initial: HintEntry[] = []): HintsState {
    const state = new HintsState(initial);
    setContext(KEY, state);
    return state;
}
```

- **Returns:** The `HintsState` instance for direct manipulation.

### `getHintsState(): HintsState | undefined`

Retrieves the `HintsState` from context. Undefined when called outside of a subtree that called `provideHints`.

```ts
export function getHintsState(): HintsState | undefined {
    return getContext<HintsState | undefined>(KEY);
}
```

---

## `lobbyLocations.ts` — Lobby Location Data and Geo Helpers

### `LobbyLocation`

```ts
export interface LobbyLocation {
    code: string;
    label: string;
    lat: number;
    lon: number;
}
```

### `FALLBACK_LOBBY_LOCATIONS`

A constant array of 10 pre-defined lobby locations covering major regions:

| Code | Label | Lat | Lon |
|---|---|---|---|
| `na-east` | North America East | 39.0 | -77.0 |
| `na-west` | North America West | 37.8 | -122.4 |
| `eu-west` | Europe West | 51.5 | -0.1 |
| `eu-central` | Europe Central | 50.1 | 8.7 |
| `eu-north` | Europe North | 59.3 | 18.1 |
| `sa-east` | South America East | -23.6 | -46.6 |
| `asia-east` | Asia East | 35.7 | 139.7 |
| `asia-south` | Asia South | 1.3 | 103.8 |
| `oceania` | Oceania | -33.9 | 151.2 |
| `africa-south` | Africa South | -26.2 | 28.0 |

### `FALLBACK_LOBBY_LOCATION`

```ts
export const FALLBACK_LOBBY_LOCATION = 'eu-central';
```

The fallback lobby location code used when no location is set.

### `isLobbyLocation(value: unknown): value is LobbyLocation`

Runtime type guard for `LobbyLocation`.

```ts
export function isLobbyLocation(value: unknown): value is LobbyLocation {
    if (typeof value !== 'object' || value === null) return false;
    const location = value as Record<string, unknown>;
    return (
        typeof location.code === 'string' &&
        typeof location.label === 'string' &&
        typeof location.lat === 'number' &&
        typeof location.lon === 'number'
    );
}
```

### `lobbyLocationLabel(locations: LobbyLocation[], code: string): string`

Resolves a location code to its human-readable label.

```ts
export function lobbyLocationLabel(locations: LobbyLocation[], code: string): string {
    return locations.find((location) => location.code === code)?.label ?? code;
}
```

- **Return:** The matching location's `label`, or `code` itself when not found.

### `distanceKm(a, b): number`

Computes the great-circle distance between two geographic coordinates using the Haversine formula.

```ts
export function distanceKm(
    a: Pick<LobbyLocation, 'lat' | 'lon'>,
    b: Pick<LobbyLocation, 'lat' | 'lon'>
): number {
    const toRad = (deg: number) => (deg * Math.PI) / 180;
    const earthRadiusKm = 6371;
    const dLat = toRad(b.lat - a.lat);
    const dLon = toRad(b.lon - a.lon);
    const lat1 = toRad(a.lat);
    const lat2 = toRad(b.lat);
    const h = Math.sin(dLat / 2) ** 2
        + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
    return 2 * earthRadiusKm * Math.asin(Math.sqrt(h));
}
```

- **Input:** Two objects with `lat`/`lon` properties (satisfies `Pick<LobbyLocation, 'lat' | 'lon'>`).
- **Return:** Distance in kilometres.

### `nearestLobbyLocation(locations: LobbyLocation[], coords): LobbyLocation | null`

Finds the nearest lobby location to a given coordinate pair by iterating all locations and tracking minimum distance.

```ts
export function nearestLobbyLocation(
    locations: LobbyLocation[],
    coords: Pick<LobbyLocation, 'lat' | 'lon'>
): LobbyLocation | null {
    let nearest: LobbyLocation | null = null;
    let nearestDistance = Number.POSITIVE_INFINITY;
    for (const location of locations) {
        const d = distanceKm(coords, location);
        if (d < nearestDistance) {
            nearestDistance = d;
            nearest = location;
        }
    }
    return nearest;
}
```

- **Return:** The `LobbyLocation` with the smallest Haversine distance, or `null` when the array is empty.

---

## `hooks.server.ts` — Session Hook

The SvelteKit server `handle` hook that runs on every server-side request. Reads the `session` httpOnly cookie, decodes the JWT, validates expiration, and populates `event.locals.user`.

```ts
import { jwtDecode } from 'jwt-decode';
import type { Handle } from '@sveltejs/kit';

interface SessionTokenClaims {
    sub?: string;
    exp?: number;
    is_admin?: boolean;
}

export const handle: Handle = async ({ event, resolve }) => {
    const session = event.cookies.get('session');

    if (session) {
        try {
            const decoded = jwtDecode<SessionTokenClaims>(session);

            if (decoded.exp && decoded.exp * 1000 < Date.now()) {
                throw new Error('Token expired');
            }

            if (decoded.sub) {
                event.locals.user = {
                    address: decoded.sub,
                    isAdmin: decoded.is_admin === true
                };
            }
        } catch {
            event.cookies.delete('session', { path: '/' });
        }
    }

    return await resolve(event);
};
```

### Behavior

- **No `session` cookie:** `event.locals.user` remains `undefined`. The request proceeds without authentication.
- **Valid JWT:** Decodes the token, checks `exp` (in seconds — converted to ms for comparison). Sets `event.locals.user = { address: decoded.sub, isAdmin: decoded.is_admin === true }`.
- **Expired or malformed JWT:** Deletes the `session` cookie (with `path: '/'`), leaving `event.locals.user` undefined.

---

## `app.d.ts` — Global Type Augmentation

```ts
declare global {
    namespace App {
        interface Locals {
            user?: {
                address: string;
                isAdmin: boolean;
            };
        }
    }
}

export {};
```

Augments SvelteKit's `App.Locals` so that `event.locals.user` is type-safe in hooks, load functions, and form actions across the application. `user` is optional (`undefined` when no valid session cookie exists); when present, `address` is always a string and `isAdmin` is always `boolean`.

---

## Cross-References

- [Route components](routes.md) — consumers of all stores and auth functions.
- [Backend realtime](../backend/realtime.md) — WebSocket frame protocol, close codes, and the `_chat_signing_message` builder.
- [Backend API reference](../backend/api-reference.md) — REST endpoints for auth.
- [Data model](../backend/data-model.md) — room and event schema.
- [Architecture](../architecture.md) — system-wide data flow.
