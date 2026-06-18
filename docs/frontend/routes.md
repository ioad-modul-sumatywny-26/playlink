# Frontend Routes

Playlink uses SvelteKit's server-side load functions and form actions to implement a Backend-for-Frontend (BFF) pattern. The JWT issued by the FastAPI backend is never exposed to client JavaScript; it is posted to the `?/login` form action via standard `fetch` and stored exclusively in an httpOnly, sameSite=strict `session` cookie with a 1-hour max age. Every server load function and action reads the cookie, decodes it with `jwtDecode`, and the page receives only derived data (address, username, isAdmin). Logout deletes the cookie. The `hooks.server.ts` handle also decodes the JWT on every request, populating `event.locals.user` with `{ address: string; isAdmin: boolean }` (see [library](library.md)).

> **Source:** `frontend/src/routes/+layout.server.ts`, `frontend/src/routes/+layout.svelte`, `frontend/src/routes/+page.svelte`, `frontend/src/routes/about/+page.svelte`, `frontend/src/routes/auth/+page.server.ts`, `frontend/src/routes/auth/+page.svelte`, `frontend/src/routes/profile/+page.server.ts`, `frontend/src/routes/profile/+page.svelte`, `frontend/src/routes/rooms/+page.server.ts`, `frontend/src/routes/rooms/+page.svelte`, `frontend/src/routes/rooms/[name]/+page.server.ts`, `frontend/src/routes/rooms/[name]/+page.svelte`, `frontend/src/routes/test/+page.svelte`, `frontend/src/hooks.server.ts`

## Route Map

| Route | File(s) | Purpose | Auth Gating |
|---|---|---|---|
| `/` | `+page.svelte` | Splash screen — crest, title, "Enter Realm" CTA | None |
| `/about` | `about/+page.svelte` | Static informational page | None |
| `/auth` | `auth/+page.server.ts`, `auth/+page.svelte` | BIP39 mnemonic-based sign-in (3-phase auth), login/logout actions | None (renders differently when authenticated) |
| `/profile` | `profile/+page.server.ts`, `profile/+page.svelte` | View and edit username, display sigil/address/dates | Server redirects to `/auth` if no session |
| `/rooms` | `rooms/+page.server.ts`, `rooms/+page.svelte` | Real-time room list with WebSocket updates, filters, create/join/leave/admin | Load fetches games/locations publicly; actions require session |
| `/rooms/[name]` | `rooms/[name]/+page.server.ts`, `rooms/[name]/+page.svelte` | Room detail: chat via `ChatStore`, member rail, event scheduling/RSVP, kick/close | Server requires session + membership (or admin) |
| `/test` | `test/+page.svelte` | Developer observatory — backend status, latency, raw JSON | None |

## BFF Authentication Model

The frontend never holds the JWT in JavaScript memory. The flow:

1. Client generates or receives a BIP39 mnemonic phrase.
2. `authenticate(mnemonic)` in `$lib/auth.ts` performs the three-phase handshake (see `/auth` below) against the backend.
3. On success, the backend returns a JWT (`{ token, username }`).
4. The client **does not store the token**; instead it POSTs the token as a form body field `token` to the `?/login` action.
5. The server action sets the cookie: `cookies.set('session', token, { httpOnly: true, sameSite: 'strict', secure: process.env.NODE_ENV === 'production', maxAge: 3600, path: '/' })`.
6. All subsequent server load functions and form actions read `cookies.get('session')` and decode it with `jwtDecode`.
7. The `hooks.server.ts` handle runs on every request, decoding the JWT into `event.locals.user` (`{ address, isAdmin }`). Expired or invalid cookies are deleted.
8. Logout calls `?/logout`, which runs `cookies.delete('session', { path: '/' })`.

The signing key (private key derived from the mnemonic) is kept in `sessionStorage` via `saveSigningKey()` so chat messages can be signed without re-entering the phrase. It is cleared on logout or tab close.

## `/` — Splash

**Purpose:** Landing page for unauthenticated visitors.

**Server data:** None (no `+page.server.ts`). Page is fully static.

**UI behavior:**
- Renders a centered splash with the D2 crest (`Crest` component, `size={104}`, `tone="gold"`), the "PLAYLINK" title, subtitle "Lobbies · Rooms · Kin", and an `OrnateButton` linking to `/auth`.
- Keyboard `Enter` navigates to `/auth`.
- HintBar shows `Enter: Enter Realm` (gold tone).

## `/about` — About

**Purpose:** Static informational page explaining the app purpose and usage ritual.

**Server data:** None (no `+page.server.ts`).

**Content:**
- Identity model explanation (non-custodial, BIP39-based).
- "The Ritual" three-step guide:
  1. **Forge a Lobby** — pick a game, declare player count, name it.
  2. **Watch the Hall** — open lobbies stream onto the game list in real time; filter by slots, status, ping.
  3. **Stand in the Room** — join, chat, coordinate, leave or let the timer expire.
- HintBar shows `Esc: Back` (red).

## `/auth` — Identity / Vault Keeper

**Server load** (`auth/+page.server.ts`):

```
load({ cookies }): { user: { address: string; username: string } | null }
```

- Reads `cookies.get('session')`.
- If absent → returns `{ user: null }`.
- If present, `jwtDecode<SessionTokenClaims>` (claims: `sub`, `username`, `exp`).
- If valid → returns `{ user: { address: decoded.sub, username: decoded.username } }`.
- If invalid/expired → deletes cookie, returns `{ user: null }`.

**Form actions:**

| Action | Input | Backend call | Cookie | Returns |
|---|---|---|---|---|
| `login` | `token` (formData string) | None (cookie-only BFF) | Sets `session` cookie (httpOnly, sameSite=strict, maxAge 3600, secure in prod) | `{ success: true }` |
| `logout` | None | None | Deletes `session` cookie | `{ success: true }` |

**UI behavior:**

Two states, controlled by `data.user`:

*Unauthenticated (Vault Keeper):*
- 3-column `MnemonicInput` grid for a 12-word BIP39 phrase.
- Keyboard shortcuts: `G` generates a new mnemonic (calls `generateMnemonic()`), `C` copies phrase to clipboard (fallback to `document.execCommand('copy')` when async clipboard API is blocked in HTTP context), `Enter` confirms.
- `startAuth()` function:
  1. Calls `authenticate(mnemonic)` from `$lib/auth.ts`:
     - **Phase 1 (challenge):** POST `$PUBLIC_BACKEND_URL/auth/request-nonce?address=<address>`. Returns `{ nonce }`. Rate-limited (429 → `"Rate limited"`).
     - **Phase 2 (local signing):** Derives `HDNodeWallet` from mnemonic. Saves signing key to `sessionStorage` via `saveSigningKey()`. Signs message `"Sign in to Playlink\nNonce: ${nonce}"` with `identity.signMessage()`.
     - **Phase 3 (verification):** POST `$PUBLIC_BACKEND_URL/auth/verify` with JSON body `{ address, nonce, signature }`. Returns `{ token, username }`.
  2. POSTs the JWT to `?/login` with form data `{ token }`.
  3. On success, calls `invalidateAll()` to re-run all active load functions.
- Shows `SystemDialog` on error.

*Authenticated (Active Covenant):*
- Displays the user's `Sigil` (88px), username, and address.
- "Sever Covenant" button posts to `?/logout` (via hidden form). Keyboard `L` triggers it.
- After logout, `invalidateAll()` re-runs loads so the page flips to the unauthenticated state.

## `/profile` — Wanderer's Profile

**Server load** (`profile/+page.server.ts`):

```
load({ cookies }): { profile: { identity_address: string; username: string; created_at: string | null; last_login: string | null } }
```

- No session cookie → `throw redirect(303, '/auth')`.
- GET `$BACKEND_INTERNAL_URL/users/me` (or `$PUBLIC_BACKEND_URL` fallback) with `Authorization: Bearer <session>`.
- Non-OK response → `throw redirect(303, '/auth')`.
- Returns profile data: `{ identity_address, username, created_at, last_login }`.

**Form actions:**

| Action | Input | Backend call | Returns |
|---|---|---|---|
| `update` | `username` (formData string, trimmed, 3–20 chars, `[a-zA-Z0-9_-]`) | PATCH `$BACKEND_BASE/users/me` with `Authorization: Bearer <session>` and JSON `{ username }` | Success: `{ success: true, username: returned_username }`. Failure: `fail(status, { error, username? })` |

- Missing session → `fail(401, { error: 'Not authenticated' })`.
- Empty username → `fail(400, { error: 'Username is required.' })`.
- Server errors → `fail(500, { error: 'Server error' })`.

**UI behavior:**
- Displays Sigil (88px), username, `identity_address`, `created_at`, `last_login` (formatted via `toLocaleString()`; `—` when null).
- Editable username field with client-side validation: `^[a-zA-Z0-9_-]{3,20}$`. Submit button disabled when `!dirty || !clientValid || saving`.
- Uses `use:enhance` for the `?/update` form.
- `SystemDialog` shown for server errors.
- HintBar shows `Enter: Save Name` (gold).

## `/rooms` — Game List

**Server load** (`rooms/+page.server.ts`):

```
load({ cookies }): {
  isAuthenticated: boolean;
  user: { address: string } | null;
  isAdmin: boolean;
  games: string[];
  lobbyLocations: LobbyLocation[];
  defaultLobbyLocation: string;
}
```

- Reads session cookie and decodes it for `address` and `isAdmin` fields (silently fails if invalid).
- Fetches in parallel:
  - GET `$BACKEND_BASE/games` → expects `string[]` of game names. On failure, `games` is empty `[]`.
  - GET `$BACKEND_BASE/lobby-locations` → expects `{ default?: string; locations?: { code: string; label: string; lat: number; lon: number }[] }`. Parsed via `parseLobbyLocations()` with fallback to `FALLBACK_LOBBY_LOCATIONS`/`FALLBACK_LOBBY_LOCATION`.
- Never redirects — falls back to empty data so the page renders even when unauthenticated.

**Form actions:**

| Action | Input | Backend call | Returns |
|---|---|---|---|
| `create` | `name`, `game` (or `__custom__` + `custom_game`), `lobby_location`, `players_max`, optional `description`, `communicator_link`, `requirements` | POST `$BACKEND_BASE/rooms` (JSON body) | `{ success: true, message }` or `fail(status, { error })` |
| `join` | `room_name` | POST `$BACKEND_BASE/rooms/{name}/join` | `{ success: true, message }` or `fail(status, { error })` |
| `leave` | `room_name` | POST `$BACKEND_BASE/rooms/{name}/leave` | `{ success: true, message }` or `fail(status, { error })` |
| `deleteRoom` | `room_name` | DELETE `$BACKEND_BASE/rooms/{name}` | `{ success: true, message }` or `fail(status, { error })` |
| `addGame` | `name` (string) | POST `$BACKEND_BASE/games` (JSON `{ name }`) | `{ success: true, message }` or `fail(status, { error })` |
| `deleteGame` | `name` (string), `force` (optional `"true"`) | DELETE `$BACKEND_BASE/games/{name}?force=true` | `{ success: true, message }` or `fail(status, { error, conflict?, game? })` |

All actions require session; missing → `fail(401)`.

`create` action details:
- `game` can be `"__custom__"` — in that case `customGame` is used as the game name.
- `players_max` is parsed via `parseInt(…, 10)`.
- Optional fields (`description`, `communicator_link`, `requirements`) are trimmed; empty strings become `null`.

`deleteGame` special handling:
- 409 status (active rooms still playing the game) returns `fail(409, { error, conflict: true, game })` so the UI can offer a force-delete confirmation.

**UI behavior** (1554-line page):

**WebSocket room list:** `roomsStore` singleton connects to `WS $PUBLIC_WS_URL/ws/rooms` for live room list updates (see [realtime](../backend/realtime.md) and [library](library.md)). Rooms filter to active (unexpired) ones every reactivity tick.

**Ping measurement:**
- Pings GET `$PUBLIC_BACKEND_URL/` every 15 seconds.
- Estimated per-room latency combines API ping + Haversine distance between viewer's location and room's lobby location (divided by 100).
- 3 pip buckets: LOW (≤80ms, 3 pips), MID (≤160ms, 2 pips), HIGH (>160ms, 1 pip).

**Room timer display:**
- Live countdown per room showing `MM:SS` from `expires_at`. Low timer (<60s) triggers visual warning.

**Filters:**
- Text search (searches room name, game, location label).
- Slot count checkboxes (2, 4, 8, 16+).
- Status: ANY / OPEN / FULL.
- Ping: ANY / LOW / MID / HIGH.

**Selection & side panel:**
- Click a room to select it; side column shows details (location, players, description, etc.).
- `Enter` navigates to `/rooms/{name}` (requires membership or admin). Click outside deselects.

**Create dialog:**
- `N` keyboard shortcut opens create dialog (requires auth).
- Dropdown: game selector (from `games` array) or custom game name.
- Lobby location: dropdown + "Detect" button using `navigator.geolocation` (`nearestLobbyLocation()` from `$lib/lobbyLocations`).
- Saved location persisted to `localStorage` key `playlink.viewerLocation`.

**Admin features:**
- `GameManager` component for adding/deleting games (handles 409 conflict for active games).
- Admin can delete any room directly from the list.

**Toast notifications:** Form action results (success/error) shown as toast, auto-dismissed after 4.5s.

**Keyboard shortcuts:**
| Key | Action |
|---|---|
| `/` | Focus search input |
| `R` | Reload page |
| `N` | Open create dialog (authenticated) |
| `Enter` | Open selected room (if member or admin) |
| `Esc` | Close dialog / deselect / history.back() |

## `/rooms/[name]` — Room Detail

**Server load** (`rooms/[name]/+page.server.ts`):

```
load({ params, cookies }): {
  roomName: string;
  roomGame: string;
  roomLocation: string;
  roomLocationLabel: string;
  description: string | null;
  communicatorLink: string | null;
  requirements: string | null;
  token: string; // raw JWT (for WebSocket auth)
  address: string;
  username: string;
  memberAddresses: string[];
  members: RoomMember[];
  event: RoomEventState | null;
  isAdmin: boolean;
  isMember: boolean;
  isPreview: boolean;
  createdBy: string;
  isCreator: boolean;
}
```

- No session → `throw redirect(303, '/auth')`.
- Decodes session JWT for `address`, `username`, `isAdmin`. Invalid → `/auth`.
- GET `$BACKEND_BASE/rooms/{params.name}` (public, no auth header). Failure/null → `/rooms`.
- If user is not a member AND not admin → redirect to `/rooms`.
- Returns room detail including `members` (typed `RoomMember[]`), `event` (typed `RoomEventState | null`), and the session token for WebSocket auth.
- `isPreview` = admin viewing a room they don't belong to (no WebSocket, read-only).

**Form actions:**

| Action | Input | Backend call | Returns |
|---|---|---|---|
| `closeRoom` | None | DELETE `$BACKEND_BASE/rooms/{name}` | `{ success: true, closed: true }` or `fail(status, { error })` |
| `kickMember` | `member_address` | POST `$BACKEND_BASE/rooms/{name}/members/{address}/kick` | `{ success: true, kick: result }` or `fail(status, { error })` |
| `scheduleEvent` | `starts_at`, `ends_at` (local datetime strings) | PUT `$BACKEND_BASE/rooms/{name}/event` (JSON `{ starts_at: ISO, ends_at: ISO }`) | `{ success: true, message }` or `fail(status, { error })` |
| `cancelEvent` | None | DELETE `$BACKEND_BASE/rooms/{name}/event` | `{ success: true, message }` or `fail(status, { error })` |
| `setRsvp` | `status` (one of `present`, `absent`, `maybe`) | PUT `$BACKEND_BASE/rooms/{name}/event/rsvp` (JSON `{ status }`) | `{ success: true, message }` or `fail(status, { error })` |

All actions require session → `fail(401)`.

`scheduleEvent`: `starts_at`/`ends_at` are local datetime-local input strings; converted to ISO UTC via `localInputToIsoUtc()`. Invalid dates → `fail(400)`.

`setRsvp`: Validated against set `{ 'present', 'absent', 'maybe' }`. Invalid → `fail(400)`.

**UI behavior** (1181-line page):

**WebSocket chat:**
- Members connect via `createChatStore(roomName, token, options)` from `$lib/chatStore` (see [library](library.md) and [realtime](../backend/realtime.md)).
- `ChatStore` subscribes to `messages`, `event`, `members`, `owner`, `closed`, `kicked` stores.
- Chat input: `Enter` sends, `Shift+Enter` newline. Auto-scrolls to bottom on new messages.
- Chat messages are signed using the key from `loadSigner()` (from `sessionStorage`).

**Member rail:**
- `partyMembers` computed reactive array with `{ address, username, isMe, isAdmin, isOwner }`.
- Each member shows a `Sigil` (small), username (or truncated address like `0x1234…5678`), admin/owner badges.

**Admin preview mode:**
- When `isPreview` is true (admin viewing a room they don't belong to): no WebSocket connection, no chat input, read-only view. State synchronized on form action invalidation (`$effect` watching `data`).

**RoomEvent component:**
- Render/edit/cancel events with `D2DatePicker` + `D2TimePicker` popover widgets.
- RSVP buttons for members: Present / Absent / Maybe.
- Live countdown to event start. Roster adjusts as members come/go.

**Close/kick flow:**
- `closeRoom()`: POSTs `?/closeRoom`, then immediately navigates to `/rooms` via `goto()`.
- `kickMember()`: POSTs `?/kickMember` with `member_address`. On success, removes member from local roster and cleans up RSVPs. If ownership transferred, updates `ownerAddress`.
- When WebSocket announces `room_closed` or `member_kicked`: shows a modal `SystemDialog` (tone `blood`) with a 5-second countdown (`CLOSE_REDIRECT_SECONDS`), then auto-redirects to `/rooms`.

**Dialogs:**
- `SystemDialog` modals for: kicked notification, room closed notification, kick target confirmation, close room confirmation.

**HintBar:**
- Members: Enter: Transmit, ⇧Enter: Newline, Esc: Leave.
- Admin preview: Esc: Back to Rooms.

## `/test` — Developer Observatory

**Purpose:** Development-only backend health probe.

**Server data:** None (no `+page.server.ts`).

**UI behavior:**
- On mount, fetches GET `$PUBLIC_BACKEND_URL/` and displays the raw JSON response.
- Shows backend URL, HTTP status, latency (ms), and a `PipMeter` (3 pips <80ms, 2 <250ms, 1 otherwise, 0 on error).
- `R` key re-pings the backend.
- HintBar: `R: Re-ping`, `Esc: Back`.
- Title: "PlayLink — Observatory".

---

## Cross-References

- [Backend REST API Reference](../backend/api-reference.md) — all endpoints called by form actions.
- [UI Components](components.md) — `MnemonicInput`, `RoomEvent`, `GameManager`, and all chrome components referenced above.
- [Frontend Library & Stores](library.md) — `auth.ts`, `roomsStore`, `chatStore`, `signingKey`, `hooks.server.ts`, `lobbyLocations`.
- [Realtime Protocol](../backend/realtime.md) — WebSocket frame types for rooms and chat.
- [Data Model](../backend/data-model.md) — `Room`, `RoomEvent`, `RoomMember` entity definitions.
