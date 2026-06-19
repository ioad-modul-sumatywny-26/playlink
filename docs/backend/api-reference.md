# API Reference

Complete reference for the Playlink REST API. The server is a Python FastAPI application served with `uv`. Responses are JSON unless noted otherwise.

The OpenAPI specification is available interactively at `/docs` when the server is running.

> **Source:** `backend/main.py`, `backend/models.py`, `backend/usernames.py`

---

## Base URL

| Environment | URL |
|---|---|
| Local development | `http://localhost:8000` |
| Production | `https://playlink.bartek.monster` |

## Authentication

All authenticated endpoints require an HTTP `Authorization` header in the OAuth2 **Password Bearer** scheme:

```
Authorization: Bearer <jwt>
```

JWT tokens are obtained via the `POST /auth/verify` endpoint (see [Auth](#auth) below). The token is a standard HS256 JWT with a configurable expiry (default 60 minutes, see [configuration](configuration.md)). The dependency injection uses FastAPI's `OAuth2PasswordBearer(tokenUrl="auth/verify", auto_error=False)` — a missing or invalid token yields `401` with no redirect.

## Rate Limiting

Every endpoint is guarded by `slowapi` with a configurable default rate limit (`DEFAULT_RATE_LIMIT` env var; default `"10/minute"`). Rate-limited requests receive:

| Status | Body |
|---|---|
| `429 Too Many Requests` | `{"detail": "Rate limit exceeded: 10 per 1 minute"}` (or the configured limit) |

See [configuration](configuration.md) for environment variable details.

## Global Errors

| Status | Condition |
|---|---|
| `422 Unprocessable Entity` | Request body fails Pydantic validation (missing fields, type errors, constraint violations). Returned automatically by FastAPI. |
| `429 Too Many Requests` | Rate limit exceeded. |

---

## Endpoint Overview

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | — | Health check |
| `POST` | `/auth/request-nonce` | — | Request a one-time authentication nonce |
| `POST` | `/auth/verify` | — | Verify signature and issue JWT |
| `GET` | `/users/me` | JWT | Get the authenticated user's profile |
| `PATCH` | `/users/me` | JWT | Update the authenticated user's username |
| `GET` | `/rooms` | — | List all active rooms |
| `GET` | `/lobby-locations` | — | List supported lobby locations |
| `GET` | `/rooms/{room_name}` | — | Get a single room's details |
| `GET` | `/games` | — | List game categories |
| `POST` | `/rooms` | JWT | Create a new room |
| `POST` | `/rooms/{room_name}/join` | JWT | Join a room |
| `POST` | `/rooms/{room_name}/leave` | JWT | Leave a room |
| `POST` | `/rooms/{room_name}/members/{member_address}/kick` | Admin | Kick a member from a room |
| `GET` | `/rooms/{room_name}/event` | — | Get the room's scheduled event |
| `PUT` | `/rooms/{room_name}/event` | JWT | Schedule or update the room's event |
| `DELETE` | `/rooms/{room_name}/event` | JWT | Cancel the room's event |
| `PUT` | `/rooms/{room_name}/event/rsvp` | JWT | Set the caller's RSVP for the event |
| `POST` | `/games` | Admin | Add a new game category |
| `DELETE` | `/games/{name}` | Admin | Delete a game category |
| `DELETE` | `/rooms/{room_name}` | Admin | Close a room |

> **WebSocket endpoints** are documented separately in [realtime.md](realtime.md): `GET /ws/rooms` (live room-list broadcast) and `GET /ws/rooms/{room_name}/chat` (per-room chat with EIP-191 signature verification).

---

## Health

### `GET /`

Basic health check. No authentication required.

**Response `200 OK`**

```json
{
  "status": "ok",
  "service": "playlink-auth"
}
```

---

## Auth

### `POST /auth/request-nonce`

Request a one-time challenge nonce for an Ethereum identity address. The nonce is hashed (SHA-256) before storage; the plaintext is returned once and must be signed with EIP-191 `personal_sign` for the subsequent verification step.

Previous unused nonces for the same address are automatically invalidated.

**Query parameter**

| Field | Type | Constraints |
|---|---|---|
| `address` | `string` | Valid Ethereum address (hex, 0x-prefixed, 42 chars). Converted to EIP-55 checksum. |

**Response `200 OK`**

```json
{
  "nonce": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Errors**

| Status | Condition |
|---|---|
| `400 Bad Request` | `address` is not a valid Ethereum address format. `{"detail": "Invalid identity address format"}` |

---

### `POST /auth/verify`

Verify an EIP-191 `personal_sign` signature over a nonce and issue a JWT. The signed message format is:

```
Sign in to Playlink\nNonce: {nonce}
```

On success, the nonce is marked as used, the user's `last_login` is updated, and a JWT is returned.

**Request body (`VerifyRequest`)**

| Field | Type | Constraints |
|---|---|---|
| `address` | `string` | Valid Ethereum address (EIP-55 checksum-compatible). |
| `nonce` | `string` | The plaintext nonce returned by `POST /auth/request-nonce`. |
| `signature` | `string` | Hex-encoded EIP-191 signature (0x-prefixed, 132 chars) produced by signing the message above with the private key corresponding to `address`. |

**Response `200 OK`**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "username": "alice_42",
  "is_admin": false
}
```

| Field | Type | Description |
|---|---|---|
| `token` | `string` | HS256 JWT. Expiry configurable via `JWT_EXPIRATION_MINUTES` (default 60 min). Claims: `sub` (checksum address), `username`, `is_admin`, `iat`, `exp`, `iss` (`"playlink-auth"`). |
| `username` | `string` | The user's display name; auto-generated if not yet set (format: `user_<8 hex chars>`). |
| `is_admin` | `boolean` | Whether the address is in the `ADMIN_ADDRESSES` whitelist. A `false` client must not interpret JWT claims to bypass this check on admin endpoints. |

**Errors**

| Status | Condition |
|---|---|
| `400 Bad Request` | `address` is not a valid Ethereum address format. `{"detail": "Invalid identity address format"}` |
| `401 Unauthorized` | Nonce not found, already used, or expired. `{"detail": "Invalid or expired challenge"}` |
| `401 Unauthorized` | Signature format is invalid (recover fails). `{"detail": "Invalid signature format"}` |
| `401 Unauthorized` | Recovered address does not match `address`. `{"detail": "Identity verification failed"}` |

---

## Users

### `GET /users/me`

Return the authenticated user's profile. Requires JWT.

**Response `200 OK`**

```json
{
  "id": 1,
  "identity_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
  "username": "alice_42",
  "created_at": "2026-06-18T12:00:00Z",
  "last_login": "2026-06-18T14:30:00Z",
  "is_admin": false
}
```

| Field | Type | Description |
|---|---|---|
| `id` | `integer` | Internal user ID. |
| `identity_address` | `string` | Ethereum address (EIP-55 checksum). |
| `username` | `string \| null` | Display name, or `null` if not yet set. |
| `created_at` | `string` | ISO 8601 timestamp (`Z`-suffixed). |
| `last_login` | `string \| null` | ISO 8601 timestamp of most recent successful `POST /auth/verify`. |
| `is_admin` | `boolean` | Whether the address is in the `ADMIN_ADDRESSES` whitelist. |

**Errors**

| Status | Condition |
|---|---|
| `401 Unauthorized` | Missing or invalid JWT. `{"detail": "Not authenticated"}` / `"Token expired"` / `"Invalid token"` |
| `404 Not Found` | User record not found (should not happen after successful auth). `{"detail": "User not found"}` |

---

### `PATCH /users/me`

Update the authenticated user's username. Requires JWT.

**Request body (`UpdateUserRequest`)**

| Field | Type | Constraints |
|---|---|---|
| `username` | `string` | 3–20 characters. Allowed: letters `a-zA-Z`, digits `0-9`, underscore `_`, hyphen `-`. Must not match any entry in the profanity stoplist (LDNOOBW English), checked as whole-string and per-`_`/`-` token. |

**Response `200 OK`**

Same shape as `GET /users/me`.

**Errors**

| Status | Condition |
|---|---|
| `400 Bad Request` | Username fails format validation. `{"detail": "Username must be 3-20 characters: letters, numbers, _ or -."}` |
| `400 Bad Request` | Username contains profanity. `{"detail": "Username contains inappropriate language."}` |
| `401 Unauthorized` | Missing or invalid JWT. |
| `404 Not Found` | User record not found. |
| `409 Conflict` | Username already taken (by another user). `{"detail": "Username already taken."}` |

---

## Rooms

### `GET /rooms`

List all active (non-expired) rooms. No authentication required.

Each room is serialised from the `Room` ORM model. The response is a JSON array of objects.

**Response `200 OK`**

```json
[
  {
    "name": "dm-arena",
    "game": "Quake III Arena",
    "lobby_location": "eu-central",
    "players_max": 8,
    "description": "Casual deathmatch",
    "communicator_link": "https://discord.gg/example",
    "requirements": "Microphone preferred",
    "created_by": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
    "created_at": "2026-06-18T12:00:00Z",
    "expires_at": "2026-06-18T13:00:00Z",
    "members": []
  }
]
```

Note: This endpoint returns the raw ORM model. For a richer view with `member_addresses`, `players_active`, and the nested `event` object, use `GET /rooms/{room_name}`.

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Room name (unique). |
| `game` | `string` | Game category name. |
| `lobby_location` | `string` | Lobby location code (e.g. `"eu-central"`). |
| `players_max` | `integer` | Maximum number of members. |
| `description` | `string \| null` | Free-text description (max 500 chars). |
| `communicator_link` | `string \| null` | Voice/text chat link (max 500 chars). |
| `requirements` | `string \| null` | Free-text requirements (max 1000 chars). |
| `created_by` | `string` | Identity address of the room creator. |
| `created_at` | `string` | ISO 8601 timestamp. |
| `expires_at` | `string` | ISO 8601 timestamp. Rooms expire 60 min after creation by default (extended automatically when an event is scheduled). |
| `members` | `array` | List of `User` objects (currently empty array; membership details available via `GET /rooms/{room_name}`). |

---

### `GET /rooms/{room_name}`

Get a single room's full details, including the member roster and scheduled event. No authentication required.

**Path parameter**

| Field | Type | Description |
|---|---|---|
| `room_name` | `string` | Room name (unique identifier). |

**Response `200 OK`**

```json
{
  "name": "dm-arena",
  "game": "Quake III Arena",
  "lobby_location": "eu-central",
  "players_max": 8,
  "players_active": 2,
  "member_addresses": [
    "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
    "0x1234567890abcdef1234567890abcdef12345678"
  ],
  "members": [
    {
      "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
      "username": "alice_42",
      "is_admin": false
    }
  ],
  "description": "Casual deathmatch",
  "communicator_link": "https://discord.gg/example",
  "requirements": "Microphone preferred",
  "created_by": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
  "expires_at": "2026-06-18T13:00:00Z",
  "event": null
}
```

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Room name. |
| `game` | `string` | Game category. |
| `lobby_location` | `string` | Lobby location code. |
| `players_max` | `integer` | Max members. |
| `players_active` | `integer` | Current member count. |
| `member_addresses` | `array[string]` | Identity addresses of all members. |
| `members` | `array[object]` | Detailed member roster. Each entry: `{ address, username, is_admin }`. |
| `description` | `string \| null` | Room description. |
| `communicator_link` | `string \| null` | Voice/text link. |
| `requirements` | `string \| null` | Member requirements. |
| `created_by` | `string` | Creator's identity address. |
| `expires_at` | `string` | ISO 8601 expiration timestamp. |
| `event` | `object \| null` | Scheduled event, or `null` if none. Shape matches `GET /rooms/{room_name}/event` response. |

**Errors**

| Status | Condition |
|---|---|
| `404 Not Found` | Room name does not exist. `{"detail": "Room not found"}` |

---

### `POST /rooms`

Create a new room. The creator is automatically added as a member.

**Side effects:** Broadcasts the updated room list over the `/ws/rooms` WebSocket to all connected global listeners. If the game name is new, a `Game` record is created automatically (via `_ensure_game`).

**Rate limiting:** Non-admin users may create at most **3 active rooms**. The check counts rooms where `created_by` matches the caller's address.

**Auth:** JWT required.

**Request body (`CreateRoomRequest`)**

| Field | Type | Constraints |
|---|---|---|
| `name` | `string` | Room name (unique). Must not already exist. |
| `game` | `string` | Game category name. 1–100 chars. If the game does not exist it is auto-created at the end of the sort order. |
| `lobby_location` | `string` | Must be one of the 10 supported location codes (see `GET /lobby-locations`). |
| `players_max` | `integer` | Maximum number of members (no min/max constraint enforced by API beyond integer type). |
| `description` | `string \| null` | Max 500 characters. |
| `communicator_link` | `string \| null` | Must be a valid URL (Pydantic `HttpUrl`) if provided. Stored as string. |
| `requirements` | `string \| null` | Max 1000 characters. |

**Response `201 Created`**

```json
{
  "status": "created",
  "room": "dm-arena"
}
```

**Errors**

| Status | Condition |
|---|---|
| `400 Bad Request` | Non-admin user has reached the 3-room limit. `{"detail": "You can create a maximum of 3 rooms."}` |
| `400 Bad Request` | Game name is empty after trimming. `{"detail": "Game name is required"}` |
| `400 Bad Request` | `lobby_location` is not a recognised code. `{"detail": "Unsupported lobby location"}` |
| `401 Unauthorized` | Missing or invalid JWT. |
| `409 Conflict` | Room name already taken. `{"detail": "Room name already taken"}` |
| `422 Unprocessable Entity` | Pydantic validation failure (e.g. `players_max` not an integer, `communicator_link` not a valid URL, `description` >500 chars). |

---

### `POST /rooms/{room_name}/join`

Join a room as a member.

**Side effects:** Broadcasts the updated room list over `/ws/rooms`, and emits a `roster_update` WebSocket frame to the room's chat channel.

**Auth:** JWT required.

**Path parameter**

| Field | Type | Description |
|---|---|---|
| `room_name` | `string` | Room name. |

**Response `200 OK`**

```json
{
  "status": "joined",
  "room": "dm-arena"
}
```

**Errors**

| Status | Condition |
|---|---|
| `400 Bad Request` | Caller is already a member. `{"detail": "You are already in this room"}` |
| `400 Bad Request` | Room is full (member count >= `players_max`). `{"detail": "Room is full"}` |
| `401 Unauthorized` | Missing or invalid JWT. |
| `404 Not Found` | Room does not exist. `{"detail": "Room not found"}` |
| `404 Not Found` | User record not found (should not happen after successful auth). `{"detail": "User not found"}` |

---

### `POST /rooms/{room_name}/leave`

Leave a room. The caller's RSVP for the room's event (if any) is automatically dropped.

**Side effects:** Broadcasts the updated room list over `/ws/rooms`. Emits a `roster_update` frame to the room's chat channel. If the leaver had an RSVP, also emits an `event_update` frame with the updated event state.

**Auth:** JWT required.

**Path parameter**

| Field | Type | Description |
|---|---|---|
| `room_name` | `string` | Room name. |

**Response `200 OK`**

```json
{
  "status": "left",
  "room": "dm-arena"
}
```

**Errors**

| Status | Condition |
|---|---|
| `400 Bad Request` | Caller is not a member. `{"detail": "You are not in this room"}` |
| `401 Unauthorized` | Missing or invalid JWT. |
| `404 Not Found` | Room does not exist. `{"detail": "Room not found"}` |
| `404 Not Found` | User record not found. `{"detail": "User not found"}` |

---

### `POST /rooms/{room_name}/members/{member_address}/kick`

Remove a non-admin member from a room. Only administrators (addresses in the `ADMIN_ADDRESSES` whitelist) may kick.

**Side effects:**
- If the kicked member was the room creator, ownership is transferred to the kicking admin (`room.created_by` updated).
- The kicked member's RSVP (if any) is removed.
- A system message is inserted into the room's chat: `"{username} was removed from the room by an administrator."`
- Emits `message`, `roster_update`, `event_update` (if event exists), and `member_kicked` WebSocket frames to the room's chat channel.
- Broadcasts updated room list over `/ws/rooms`.
- Disconnects the kicked member's active chat WebSocket connections (close code `4409`).

**Auth:** Admin (JWT + address in `ADMIN_ADDRESSES`).

**Path parameters**

| Field | Type | Description |
|---|---|---|
| `room_name` | `string` | Room name. |
| `member_address` | `string` | Identity address of the member to kick. Case-insensitive lookup. |

**Response `200 OK`**

```json
{
  "status": "kicked",
  "member_address": "0x1234567890abcdef1234567890abcdef12345678",
  "member_username": "bob_99",
  "created_by": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
  "ownership_transferred": false
}
```

| Field | Type | Description |
|---|---|---|
| `status` | `string` | `"kicked"` |
| `member_address` | `string` | Identity address of the removed member. |
| `member_username` | `string` | Username of the removed member. |
| `created_by` | `string` | Room creator after the operation (may have been transferred). |
| `ownership_transferred` | `boolean` | Whether room ownership was transferred to the admin as a result of the kick. |

**Errors**

| Status | Condition |
|---|---|
| `401 Unauthorized` | Missing or invalid JWT. |
| `403 Forbidden` | Caller is not an admin. `{"detail": "Admin privileges required"}` |
| `403 Forbidden` | Target member is an admin. `{"detail": "Administrators cannot be kicked"}` |
| `404 Not Found` | Room does not exist. `{"detail": "Room not found"}` |
| `404 Not Found` | Target user not found. `{"detail": "User not found"}` |
| `409 Conflict` | Target user is not a member of the room. `{"detail": "User is not a room member"}` |

---

## Room Events / RSVP

### `GET /rooms/{room_name}/event`

Get the room's scheduled event, including the RSVP roster. This endpoint is public — anyone may browse the schedule, but only members may RSVP.

**Path parameter**

| Field | Type | Description |
|---|---|---|
| `room_name` | `string` | Room name. |

**Response `200 OK`**

```json
{
  "starts_at": "2026-06-20T18:00:00Z",
  "ends_at": "2026-06-20T20:00:00Z",
  "created_by": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
  "created_at": "2026-06-18T12:00:00Z",
  "updated_at": "2026-06-18T12:00:00Z",
  "rsvps": [
    {
      "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
      "username": "alice_42",
      "status": "present",
      "updated_at": "2026-06-18T12:05:00Z"
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `starts_at` | `string` | ISO 8601 start timestamp. |
| `ends_at` | `string` | ISO 8601 end timestamp. |
| `created_by` | `string` | Identity address of the room creator (who scheduled the event). |
| `created_at` | `string` | ISO 8601 creation timestamp. |
| `updated_at` | `string` | ISO 8601 last-update timestamp. |
| `rsvps` | `array[object]` | List of RSVPs. Each entry: `{ address, username, status ("present"|"absent"|"maybe"), updated_at }`. |

**Errors**

| Status | Condition |
|---|---|
| `404 Not Found` | Room does not exist. `{"detail": "Room not found"}` |
| `404 Not Found` | Room has no event scheduled. `{"detail": "No event scheduled"}` |

---

### `PUT /rooms/{room_name}/event`

Create or replace the room's scheduled event. Only the room creator may schedule. The room's `expires_at` is automatically extended to `ends_at + 30 minutes` (grace period) if the new expiry would be later.

**Side effects:** Broadcasts an `event_update` WebSocket frame to the room's chat channel. If the room expiry changed, also broadcasts the updated room list over `/ws/rooms`.

If the event time window changes (compared to an existing event), all existing RSVPs are dropped — members must reconfirm.

**Auth:** JWT required. `address` must match `room.created_by`.

**Path parameter**

| Field | Type | Description |
|---|---|---|
| `room_name` | `string` | Room name. |

**Request body (`ScheduleEventRequest`)**

| Field | Type | Constraints |
|---|---|---|
| `starts_at` | `datetime` | Must be in the future (UTC). Converted to UTC if timezone-naive. |
| `ends_at` | `datetime` | Must be after `starts_at`. Converted to UTC if timezone-naive. |

**Response `200 OK`**

Same shape as `GET /rooms/{room_name}/event`.

**Errors**

| Status | Condition |
|---|---|
| `400 Bad Request` | `starts_at` is not in the future. `{"detail": "starts_at must be in the future"}` |
| `400 Bad Request` | `ends_at` is not after `starts_at`. `{"detail": "ends_at must be after starts_at"}` |
| `401 Unauthorized` | Missing or invalid JWT. |
| `403 Forbidden` | Caller is not the room creator. `{"detail": "Only the room creator can schedule an event"}` |
| `404 Not Found` | Room does not exist. `{"detail": "Room not found"}` |

---

### `DELETE /rooms/{room_name}/event`

Cancel a scheduled event and clear all RSVPs. Only the room creator may cancel.

**Side effects:** Broadcasts `{"type": "event_update", "event": null}` to the room's chat channel.

**Auth:** JWT required. `address` must match `room.created_by`.

**Path parameter**

| Field | Type | Description |
|---|---|---|
| `room_name` | `string` | Room name. |

**Response `200 OK`**

```json
{
  "status": "cancelled",
  "room": "dm-arena"
}
```

**Errors**

| Status | Condition |
|---|---|
| `401 Unauthorized` | Missing or invalid JWT. |
| `403 Forbidden` | Caller is not the room creator. `{"detail": "Only the room creator can cancel the event"}` |
| `404 Not Found` | Room does not exist. `{"detail": "Room not found"}` |
| `404 Not Found` | Room has no event scheduled. `{"detail": "No event scheduled"}` |

---

### `PUT /rooms/{room_name}/event/rsvp`

Upsert the caller's RSVP for the room's scheduled event. Only current room members may RSVP. One RSVP per user per event (previous status is overwritten).

**Side effects:** Broadcasts an `rsvp_update` WebSocket frame to the room's chat channel.

**Auth:** JWT required. Caller must be a member of the room.

**Path parameter**

| Field | Type | Description |
|---|---|---|
| `room_name` | `string` | Room name. |

**Request body (`SetRsvpRequest`)**

| Field | Type | Constraints |
|---|---|---|
| `status` | `string` | One of `"present"`, `"absent"`, `"maybe"` (values of `RsvpStatus` enum). |

**Response `200 OK`**

```json
{
  "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
  "username": "alice_42",
  "status": "present",
  "updated_at": "2026-06-18T12:05:00Z"
}
```

**Errors**

| Status | Condition |
|---|---|
| `401 Unauthorized` | Missing or invalid JWT. |
| `403 Forbidden` | Caller is not a room member. `{"detail": "Only room members can RSVP to the event"}` |
| `404 Not Found` | Room does not exist. `{"detail": "Room not found"}` |
| `404 Not Found` | User record not found. `{"detail": "User not found"}` |
| `404 Not Found` | Room has no event scheduled. `{"detail": "No event scheduled"}` |

---

## Lobby Locations

### `GET /lobby-locations`

Return the list of supported lobby locations with display labels and approximate geo-coordinates, plus the default location code.

**Response `200 OK`**

```json
{
  "default": "eu-central",
  "locations": [
    { "code": "na-east", "label": "North America East", "lat": 39.0, "lon": -77.0 },
    { "code": "na-west", "label": "North America West", "lat": 37.8, "lon": -122.4 },
    { "code": "eu-west", "label": "Europe West", "lat": 51.5, "lon": -0.1 },
    { "code": "eu-central", "label": "Europe Central", "lat": 50.1, "lon": 8.7 },
    { "code": "eu-north", "label": "Europe North", "lat": 59.3, "lon": 18.1 },
    { "code": "sa-east", "label": "South America East", "lat": -23.6, "lon": -46.6 },
    { "code": "asia-east", "label": "Asia East", "lat": 35.7, "lon": 139.7 },
    { "code": "asia-south", "label": "Asia South", "lat": 1.3, "lon": 103.8 },
    { "code": "oceania", "label": "Oceania", "lat": -33.9, "lon": 151.2 },
    { "code": "africa-south", "label": "Africa South", "lat": -26.2, "lon": 28.0 }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `default` | `string` | The default lobby location code (`"eu-central"`). |
| `locations` | `array[object]` | List of location objects. Each: `{ code, label, lat, lon }`. |

---

## Games

### `GET /games`

List all game categories ordered by `sort_order`.

**Response `200 OK`**

```json
[
  "Quake III Arena",
  "Diablo II",
  "StarCraft",
  "Half-Life",
  "Unreal Tournament"
]
```

The five default games are seeded on first startup. Additional games may be added and removed via admin endpoints.

---

### `POST /games`

Add a new game category at the end of the sort order.

**Auth:** Admin (JWT + address in `ADMIN_ADDRESSES`).

**Request body (`CreateGameRequest`)**

| Field | Type | Constraints |
|---|---|---|
| `name` | `string` | Game name. 1–100 characters. Trimmed server-side. |

**Response `201 Created`**

```json
{
  "name": "Team Fortress 2",
  "sort_order": 6
}
```

**Errors**

| Status | Condition |
|---|---|
| `400 Bad Request` | Name is empty after trimming. `{"detail": "Game name is required"}` |
| `401 Unauthorized` | Missing or invalid JWT. |
| `403 Forbidden` | Caller is not an admin. `{"detail": "Admin privileges required"}` |
| `409 Conflict` | Game name already exists. `{"detail": "Game already exists"}` |

---

### `DELETE /games/{name}`

Delete a game category. If rooms are currently playing this game, the request is refused with `409` unless the query parameter `force=true` is set, in which case those rooms are closed first (same cascade as `DELETE /rooms/{room_name}`).

**Side effects (when `force=true`):** Each affected room is purged (messages, event, RSVPs, members), a `room_closed` WebSocket frame is broadcast to each room's chat channel, and the updated room list is broadcast over `/ws/rooms`.

**Auth:** Admin (JWT + address in `ADMIN_ADDRESSES`).

**Path parameter**

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Game name. |

**Query parameter**

| Field | Type | Default | Description |
|---|---|---|---|
| `force` | `boolean` | `false` | If `true`, close all rooms playing this game before deleting it. |

**Response `200 OK`**

```json
{
  "status": "deleted",
  "game": "Team Fortress 2",
  "rooms_closed": ["dm-arena", "ctf-base"]
}
```

| Field | Type | Description |
|---|---|---|
| `status` | `string` | `"deleted"` |
| `game` | `string` | The deleted game name. |
| `rooms_closed` | `array[string]` | Names of rooms closed as part of the deletion (empty array when none). |

**Errors**

| Status | Condition |
|---|---|
| `401 Unauthorized` | Missing or invalid JWT. |
| `403 Forbidden` | Caller is not an admin. `{"detail": "Admin privileges required"}` |
| `404 Not Found` | Game name does not exist. `{"detail": "Game not found"}` |
| `409 Conflict` | Active rooms are playing this game and `force` is not `true`. `{"detail": "There are N active rooms currently playing this game."}` |

---

## Admin

### `DELETE /rooms/{room_name}`

Close (delete) a room. Cascades deletion of the room's chat messages, scheduled event, and all RSVPs.

**Side effects:**
- Broadcasts `{"type": "room_closed", "room": "{room_name}"}` to the room's chat channel so clients redirect out.
- Broadcasts the updated room list over `/ws/rooms`.

**Auth:** Admin (JWT + address in `ADMIN_ADDRESSES`).

**Path parameter**

| Field | Type | Description |
|---|---|---|
| `room_name` | `string` | Room name. |

**Response `200 OK`**

```json
{
  "status": "closed",
  "room": "dm-arena"
}
```

**Errors**

| Status | Condition |
|---|---|
| `401 Unauthorized` | Missing or invalid JWT. |
| `403 Forbidden` | Caller is not an admin. `{"detail": "Admin privileges required"}` |
| `404 Not Found` | Room does not exist. `{"detail": "Room not found"}` |

---

## WebSocket Endpoints

The two WebSocket endpoints are documented in [realtime.md](realtime.md):

| Path | Description |
|---|---|
| `/ws/rooms` | Unauthenticated live room-list broadcast. |
| `/ws/rooms/{room_name}/chat` | JWT-authenticated, membership-gated per-room chat with EIP-191 message signing. |

---

## Data Model

See [data-model.md](data-model.md) for entity shapes: `Room`, `RoomMember`, `Message`, `RoomEvent`, `RoomEventRsvp`, `User`, `Nonce`, `Game`.

## Configuration

See [configuration.md](configuration.md) for environment variables (`DATABASE_URL`, `JWT_SECRET`, `JWT_ALGORITHM`, `NONCE_EXPIRATION_MINUTES`, `JWT_EXPIRATION_MINUTES`, `DEFAULT_RATE_LIMIT`, `ADMIN_ADDRESSES`, `ROOM_CLEANUP_INTERVAL_SECONDS`, etc.) and rate-limit details.
