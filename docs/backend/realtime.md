# Realtime / WebSocket Protocol

Playlink exposes two WebSocket endpoints for live push: a **global room-list channel** (unauthenticated) and a **per-room chat channel** (authenticated via JWT query parameter). Both are served from `backend/main.py` using two in-memory connection registries — `ConnectionManager` and `RoomChatManager`.

> **Source:** `backend/main.py` (classes `ConnectionManager`, `RoomChatManager`; handlers `websocket_rooms`, `websocket_chat`; helpers `get_rooms_payload`, `_members_payload`, `_serialize_event_state`, `_msg_dict`, `_chat_signing_message`, `_verify_chat_signature`; constants `CHAT_SIGNATURE_SKEW_SECONDS`, `SYSTEM_SENDER_ADDRESS`, `WS_LIMITS`, `MAX_MSGS`, `WINDOW`), `frontend/src/lib/roomsStore.ts`, `frontend/src/lib/chatStore.ts`, `frontend/src/lib/signing.ts`.

---

## Connection Managers

### `ConnectionManager` — global room list

| Member | Type | Description |
|--------|------|-------------|
| `active_connections` | `list[WebSocket]` | Every connected `/ws/rooms` socket |
| `connect(ws)` | coroutine | Accept socket, append to list |
| `disconnect(ws)` | void | Remove from list (noop if absent) |
| `broadcast(data: str)` | coroutine | Send string to **every** connection; drop stale sockets that raise on send |

Unreachable browsers (tab close, network loss) are pruned lazily during the next broadcast. There is no server-side heartbeat.

### `RoomChatManager` — per-room chat

| Member | Type | Description |
|--------|------|-------------|
| `rooms` | `dict[str, dict[WebSocket, str]]` | `room_name → { WebSocket → identity_address }` |
| `connect(room, ws, address)` | coroutine | Accept socket, register under room key |
| `disconnect(room, ws)` | void | Unregister single socket; delete room key when empty |
| `broadcast(room, payload: str)` | coroutine | Send string to **every** connection in that room; prune stale sockets |
| `disconnect_user(room, address, code=4409)` | coroutine | Close every socket authenticated as `address` (case-insensitive) |

---

## `/ws/rooms` — Global Room-List Channel

```
GET /ws/rooms
```

### Connection

- **No authentication.** The socket is accepted unconditionally and registered in the `ConnectionManager`.
- The server immediately sends a JSON payload — the current active rooms list — as the first frame.
- After that the socket sits in a `receive_text()` loop, consuming any inbound data silently (no actions taken on inbound messages).

### Outbound Frames

The channel sends a single frame type: a **bare JSON array** of room-summary objects (no wrapping `type` field). Each array element:

```json
{
  "name": "duel-arena",
  "game": "Quake III Arena",
  "lobby_location": "eu-central",
  "players_active": 2,
  "players_max": 4,
  "member_addresses": ["0xAbc…", "0xDef…"],
  "description": "Looking for a duel partner",
  "communicator_link": "https://discord.gg/abc123",
  "requirements": "Microphone required",
  "expires_at": "2026-06-19T12:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Room slug (unique) |
| `game` | string | Game category name |
| `lobby_location` | string | Region code (e.g. `eu-central`, `us-west`) |
| `players_active` | number | Current member count (`len(r.members)`) |
| `players_max` | number | Capacity set at creation |
| `member_addresses` | string[] | Checksummed identity addresses of current members |
| `description` | string | nullable | Free-text room description |
| `communicator_link` | string | nullable | External voice/chat link |
| `requirements` | string | nullable | Requirements text |
| `expires_at` | string | ISO 8601 with `Z` suffix |

### When Broadcasts Occur

The `ConnectionManager.broadcast(get_rooms_payload(session))` is called after every mutation that changes the visible room set:

| Event | Endpoint / Source |
|-------|-------------------|
| **Room created** | `POST /rooms` |
| **Room joined** | `POST /rooms/{name}/join` |
| **Room left** | `POST /rooms/{name}/leave` |
| **Member kicked** | `POST /rooms/{name}/members/{addr}/kick` |
| **Room closed** (admin) | `DELETE /rooms/{name}` |
| **Game deleted** (admin) | `DELETE /games/{name}` (closes all rooms for that game) |
| **Room expired** (background) | `cleanup_expired_rooms_task` runs every 60s |
| **Room expiry changed** | Indirectly via event set/update when room expiry shifts |

### Expired-Room Pruning

Expired rooms (`Room.expires_at <= now`) are deleted synchronously inside `get_rooms_payload()` on **every** call, so the list broadcast never contains stale entries. The separate background task `cleanup_expired_rooms_task` (runs every 60s, interval set by `ROOM_CLEANUP_INTERVAL_SECONDS`) catches rooms that expire between`/ws/rooms` payload fetches.

**Caution:** The cleanup task does **not** send `room_closed` frames to the chat channel — it only refreshes the global room list. Chat connections to an expired room remain open until the client sends a message (at which point the DB lookup will fail) or the client disconnects.

---

## `/ws/rooms/{room_name}/chat` — Per-Room Chat Channel

```
GET /ws/rooms/{room_name}/chat?token=<JWT>
```

### Connection & Authentication

1. **JWT via query parameter.** The `token` query string carries the HS256 JWT obtained during login. Browsers cannot set custom WebSocket headers, so the token is passed in the URL.
2. The server decodes the JWT via `_decode_jwt()` to extract the identity address (`sub` claim). Failure → close code **4401** (Unauthorized).
3. The room must exist in the database. Not found → close code **4404** (Not Found).
4. The caller must be a current member of the room. Not a member → close code **4403** (Forbidden).

If all checks pass, the socket is registered with `RoomChatManager.connect()`.

### Close Codes

| Code | Meaning | When Sent |
|------|---------|-----------|
| 4401 | Unauthorized | JWT missing, expired, or invalid |
| 4403 | Forbidden — not a member | Caller is not in the room's member list (checked on connect **and** per-iteration) |
| 4404 | Not Found | Room name does not exist |
| 4409 | Room membership terminated | Admin kick `disconnect_user`; client reconnects and gets 4403 |
| 4429 | Rate limited | Per-address message rate exceeded

On the frontend, close codes **4403** and **4409** set `kicked = true` and suppress reconnection. All other codes trigger exponential backoff reconnect.

### Membership Re-validation

After every inbound message the server re-queries the `RoomMember` link table directly (not the ORM relationship cache):

```python
membership = session.exec(
    select(RoomMember).where(
        RoomMember.room_id == room.id,
        RoomMember.user_id == user.id,
    )
).first()
```

If the member row is gone, the socket is closed with code **4403**. This ensures a kicked or removed member cannot continue writing even if their WebSocket stays open.

### Per-Address Rate Limiting

A sliding window is enforced per identity address:

| Variable | Env Variable | Default | Description |
|----------|-------------|---------|-------------|
| `MAX_MSGS` | `WS_RATE_LIMIT_MAX_MESSAGES` | 10 | Maximum messages per window per address |
| `WINDOW` | `WS_RATE_LIMIT_TIME_WINDOW_SECONDS` | 10 | Window duration in seconds |

Rate limit state lives in the global `WS_LIMITS: dict[str, list[float]]` (in-memory, **not** shared across workers). On each inbound message the server prunes timestamps older than `WINDOW`, checks count >= `MAX_MSGS`, and if exceeded closes the socket with code **4429**.

### Outbound Frame Types

Every outbound frame is a JSON object with a `type` string field and type-specific payload fields.

#### `history`

Sent immediately after socket connect (before the read loop starts). Contains the last 50 messages in chronological order.

```json
{
  "type": "history",
  "messages": [
    {
      "id": 1,
      "sender_address": "0xAbc…",
      "sender_username": "player1",
      "content": "gg",
      "created_at": "2026-06-18T20:00:00Z",
      "signature": "0x1234…",
      "sent_at": "2026-06-18T20:00:00.000Z",
      "verified": true
    }
  ]
}
```

| Sub-field | Type | Description |
|-----------|------|-------------|
| `messages` | ChatMessage[] | Array of message objects (see `ChatMessage` table below) |

#### `message`

Broadcast to every connection in the room after a new message is stored.

```json
{
  "type": "message",
  "message": {
    "id": 42,
    "sender_address": "0xAbc…",
    "sender_username": "player1",
    "content": "Hello!",
    "created_at": "2026-06-18T20:01:00Z",
    "signature": "0x1234…",
    "sent_at": "2026-06-18T20:01:00.000Z",
    "verified": true
  }
}
```

#### ChatMessage fields (`_msg_dict`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | number | Auto-increment primary key |
| `sender_address` | string | Checksummed identity address |
| `sender_username` | string | Username of the sender (resolved at broadcast time) |
| `content` | string | Message body |
| `created_at` | string | ISO 8601 server timestamp (with `Z`) |
| `signature` | string | nullable | EIP-191 hex signature, or `null` for unsigned |
| `sent_at` | string | nullable | Client-provided ISO 8601 timestamp that was signed, or `null` |
| `verified` | boolean | `true` when the server recovered a valid signer matching `sender_address` |
| `kind` | string | *(optional, only when sender is system)* `"system"` |

A `kind: "system"` message is sent when the server injects an announcement (e.g. "player was removed from the room by an administrator"). The `sender_address` is `"__system__"`.

#### `event_update`

Sent when a room event is created, updated, cancelled, or its RSVP set changes.

```json
{
  "type": "event_update",
  "event": {
    "starts_at": "2026-06-20T18:00:00Z",
    "ends_at": "2026-06-20T21:00:00Z",
    "created_by": "0xAbc…",
    "created_at": "2026-06-18T12:00:00Z",
    "updated_at": "2026-06-18T12:30:00Z",
    "rsvps": [
      {
        "address": "0xAbc…",
        "username": "player1",
        "status": "present",
        "updated_at": "2026-06-18T12:30:00Z"
      }
    ]
  }
}
```

| Sub-field | Type | Description |
|-----------|------|-------------|
| `event` | object | nullable | The full event state, or `null` when cancelled |

**Event object fields:**

| Field | Type | Description |
|-------|------|-------------|
| `starts_at` | string | ISO 8601 event start |
| `ends_at` | string | ISO 8601 event end |
| `created_by` | string | Checksummed address of the member who created the event |
| `created_at` | string | ISO 8601 creation timestamp |
| `updated_at` | string | ISO 8601 last-update timestamp |
| `rsvps` | RsvpEntry[] | Array of RSVP entries (one per member who responded) |

**RsvpEntry fields:**

| Field | Type | Description |
|-------|------|-------------|
| `address` | string | Checksummed identity address |
| `username` | string | Username |
| `status` | string | One of `"present"`, `"absent"`, `"maybe"` |
| `updated_at` | string | ISO 8601 timestamp of this RSVP |

#### `rsvp_update`

Sent when a single member upserts their RSVP (via `PUT /rooms/{name}/event/rsvp`).

```json
{
  "type": "rsvp_update",
  "rsvp": {
    "address": "0xDef…",
    "username": "player2",
    "status": "maybe",
    "updated_at": "2026-06-18T13:00:00Z"
  }
}
```

The frontend merges this into the local event state by replacing any existing RSVP from the same address (case-insensitive address dedup).

#### `roster_update`

Sent when a member joins or leaves the room, or when a member is kicked.

```json
{
  "type": "roster_update",
  "members": [
    { "address": "0xAbc…", "username": "player1", "is_admin": false },
    { "address": "0xDef…", "username": "player2", "is_admin": true }
  ]
}
```

| Sub-field | Type | Description |
|-----------|------|-------------|
| `members` | RoomMember[] | **Full** current roster (not a diff); replaces client state |

**RoomMember fields:**

| Field | Type | Description |
|-------|------|-------------|
| `address` | string | Checksummed identity address |
| `username` | string | Username |
| `is_admin` | boolean | Whether the address is in the `ADMIN_ADDRESSES` whitelist |

#### `room_closed`

Sent when an admin **deletes the room** or a **game is deleted** (which cascades to all its rooms).

```json
{
  "type": "room_closed",
  "room": "duel-arena"
}
```

The frontend sets `closed = true`, tears down the socket, and suppresses reconnect.

#### `member_kicked`

Sent when an admin removes a member via `POST /rooms/{name}/members/{addr}/kick`.

```json
{
  "type": "member_kicked",
  "member_address": "0xAbc…",
  "member_username": "player1",
  "created_by": "0xAdmin…",
  "ownership_transferred": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `member_address` | string | Checksummed address of the removed member |
| `member_username` | string | Username of removed member |
| `created_by` | string | Address of the **new** room owner (after potential transfer) |
| `ownership_transferred` | boolean | `true` when the removed member **was** the room owner |

The frontend updates `owner` to `created_by`. If `member_address` matches the current session's address, it sets `kicked = true` and tears down the socket.

Immediately after this frame, the server calls `disconnect_user()` for the kicked address (close code 4409).

#### `error`

Sent when a server-side validation rejects an inbound message (e.g. signature verification failed).

```json
{
  "type": "error",
  "detail": "signature_invalid"
}
```

The frontend logs a warning; no state change occurs. The rejected message was **never stored** in the database.

### Inbound Frame Types (Client → Server)

The client sends **one** type of frame — a chat message. The server expects a JSON object with at least a `content` field.

#### Unsigned (legacy / no-signer client)

```json
{
  "content": "Hello, everyone!"
}
```

#### Signed (EIP-191)

```json
{
  "content": "Hello, everyone!",
  "sent_at": "2026-06-18T20:01:00.000Z",
  "signature": "0x…"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | Message body; trimmed, must be non-empty and ≤1000 chars |
| `sent_at` | string | With `signature` | ISO 8601 client timestamp included in the signing payload |
| `signature` | string | No | EIP-191 hex signature over the canonical message (see below) |

**Validation pipeline (server):**

1. Parse JSON; reject malformed.
2. Trim `content`; reject empty or >1000 chars.
3. Per-iteration membership check — close 4403 if no longer a member.
4. Rate-limit check — close 4429 if over limit.
5. If `signature` present:
   - Verify via `_verify_chat_signature()` (see [Message Signing](#message-signing-eip-191) below).
   - On failure: send `{"type": "error", "detail": "signature_invalid"}`, skip storage (do **not** close socket).
6. Create `Message` row, commit, then broadcast `{"type": "message", "message": …}` to all room connections.

---

## Message Signing (EIP-191)

Chat messages can be cryptographically signed with the sender's BIP39-derived ECDSA key so the server can prove authorship end-to-end rather than trusting the JWT alone. This is **opt-in**: clients without a signing key send unsigned messages (marked `verified: false`).

### Canonical Message String

Both server and frontend construct this exact string:

```
PlayLink signed chat message
room={room_name}
sent_at={sent_at}
content={content}
```

- **Whitespace is significant.** The four lines are joined with literal `\n` (0x0A). No trailing newline.
- `room` is the raw room name (URL-encoded when connecting, but stored decoded).
- `sent_at` is the client-generated ISO 8601 string passed in the message payload.
- `content` is the trimmed message body.

**Server implementation** (`_chat_signing_message`):
```python
def _chat_signing_message(room_name: str, content: str, sent_at: str) -> str:
    return (
        "PlayLink signed chat message\n"
        f"room={room_name}\n"
        f"sent_at={sent_at}\n"
        f"content={content}"
    )
```

**Frontend equivalent** (`buildChatSigningMessage` in `signing.ts`):
```typescript
export function buildChatSigningMessage(room: string, content: string, sentAt: string): string {
    return `PlayLink signed chat message\nroom=${room}\nsent_at=${sentAt}\ncontent=${content}`;
}
```

> See the [frontend library reference](../frontend/library.md) for the `ChatSigner` interface and `signChatMessage` usage.

### Signature Verification

The server verifies with `_verify_chat_signature`:

```python
def _verify_chat_signature(
    room_name: str, content: str, sent_at: str, signature: str, address: str
) -> bool:
```

| Step | Detail |
|------|--------|
| Parse `sent_at` | Must be valid ISO 8601 via `datetime.fromisoformat()` |
| Timezone | Naive timestamps are treated as UTC |
| Clock skew | `abs(now - sent_at)` must be ≤ **120 seconds** (`CHAT_SIGNATURE_SKEW_SECONDS`) — prevents replay |
| Recover signer | `encode_defunct(text=canonical_message)` then `Account.recover_message(message, signature)` |
| Compare | Recovered address lower-cased and compared to claimed `address` (lower-cased) |

### Replay Window

`CHAT_SIGNATURE_SKEW_SECONDS = 120` (hardcoded, not configurable). The server compares `abs(now - sent_at)` against this value. Signatures outside the window are rejected as `signature_invalid`.

### `SYSTEM_SENDER_ADDRESS`

System-generated messages (kick notifications, etc.) use the constant address `"__system__"` and always have `kind: "system"` in the payload. They are inserted by the server, not signed.

---

## Cross-Links

- [REST API Reference](api-reference.md) — REST endpoints for room CRUD, event management, RSVP, kick
- [Backend Configuration](configuration.md) — `WS_RATE_LIMIT_MAX_MESSAGES`, `WS_RATE_LIMIT_TIME_WINDOW_SECONDS`, `JWT_SECRET`, `ADMIN_ADDRESSES`
- [Frontend Library Reference](../frontend/library.md) — `ChatSigner`, `buildChatSigningMessage`, `signChatMessage`, `ChatStore` interface
- [Data Model Reference](data-model.md) — `Room`, `Message`, `RoomEvent`, `RoomEventRsvp` SQLModel schemas
