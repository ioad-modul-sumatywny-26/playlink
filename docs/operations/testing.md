# Testing Reference

This document describes how to run and interpret the test suites for both the backend (Python/FastAPI) and frontend (SvelteKit/TypeScript) components of Playlink.

> **Source:** `backend/tests/conftest.py`, `backend/tests/test_*.py`, `backend/pyproject.toml`, `frontend/vite.config.js`, `frontend/package.json`, `frontend/src/test/*.test.ts`, `.github/workflows/cicd.yml`

---

## Backend Tests

The backend test suite uses **pytest** with coverage via **pytest-cov**. All tests target an ephemeral in-memory SQLite database so no Postgres instance is required for unit testing.

### Running

```bash
cd backend
uv run pytest
```

Arguments are forwarded normally:

```bash
uv run pytest -v                # verbose output
uv run pytest -k test_auth      # run only auth-related tests
uv run pytest --cov=main --cov=models --cov=database --cov=usernames   # local coverage report
```

The CI pipeline runs the full coverage gate:

```bash
uv run pytest \
  --cov=main --cov=models --cov=database --cov=usernames \
  --cov-report=term-missing:skip-covered \
  --cov-fail-under=80
```

This enforces at least **80% line coverage** across the four tracked modules (`main`, `models`, `database`, `usernames`). Skipped-covered lines are hidden in the terminal report.

### Configuration

From `backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
env = [
    "DATABASE_URL=sqlite://",
    "JWT_SECRET=this-is-a-very-secure-test-secret-at-least-32-chars",
]
```

The environment is set automatically by `pytest-env` — tests always see `DATABASE_URL=sqlite://` and a stable `JWT_SECRET`.

### Fixtures (conftest.py)

All fixtures live in `backend/tests/conftest.py`:

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `session` (name=`"session"`) | function | Creates in-memory SQLite engine (`sqlite://`) with `StaticPool` and `check_same_thread=False`. Creates all tables, seeds the `game` table with 5 reference titles (Quake III Arena, Diablo II, StarCraft, Half-Life, Unreal Tournament). Yields a `Session`. Disposes engine in `finally`. |
| `client` (name=`"client"`) | function | Overrides the `get_session` FastAPI dependency with the test `session`. Yields a `fastapi.testclient.TestClient`. Clears `dependency_overrides` in teardown. |
| `disable_rate_limit` (autouse) | function | Sets `app.state.limiter.enabled = False` so all endpoints are callable without hitting the rate limiter. |

The `session` fixture uses `sqlmodel.pool.StaticPool` to avoid SQLite threading issues and reuses the same connection for the entire test function.

### Coverage Areas

| Test file | Coverage |
|-----------|----------|
| `test_auth.py` (7 tests) | Happy-path authentication flow: request nonce, verify EIP-191 signature, `GET /users/me`, nonce invalidation chain. |
| `test_auth_edges.py` (9 tests) | Edge cases: nonce hashing & DB shape, replay attack, expired nonce, bad signature format, expired/missing-sub/not-found-user JWT, forged admin claim. |
| `test_rooms.py` (9 tests) | Room join/leave lifecycle: auth required, 404 on missing room, duplicate name (409), 3-room per-user limit, full room rejection, non-member leave, member payload shape updates. |
| `test_rooms_lifecycle.py` (15 tests) | Room CRUD with metadata: `lobby_location` validation, oversized `description` (422), unknown location (400), custom game auto-add, `/lobby-locations` endpoint. |
| `test_room_events.py` (33 tests) | Event scheduling (PUT/GET/DELETE), RSVP upsert & idempotency, reschedule clears RSVPs, leave clears RSVP, expiry pruning, WebSocket broadcasts (`event_update`, `rsvp_update`, `roster_update`), payload shape parity. |
| `test_chat.py` (12 tests) | Chat WebSocket: bad token/not-member/missing-room disconnect, member broadcast, history replay, oversize message drop, EIP-191 signed message verification (valid, tampered, wrong signer, stale timestamp, unsigned, history includes signature). |
| `test_kick.py` (7 tests) | Admin kick: auth required, cannot kick admin, RSVP removal + rejoin allowed, creator transfer, WS disconnect (4409) + notifications, admin exempt from 3-room limit, member payload `is_admin` flag. |
| `test_admin.py` (16 tests) | Admin auth enforcement (401/403), delete room cascade (messages, events, RSVPs, members) + WebSocket `room_closed` broadcast, game CRUD with `force` flag. |
| `test_admin_edges.py` (2 tests) | Admin edge cases: trimmed game name, force-delete game WS notifications across multiple rooms, broad WS connection handling. |
| `test_users.py` (11 tests) | Username validation unit tests (stoplist, profanity, format codes), `PATCH /users/me` (success, idempotent, bad format, profane, duplicate conflict, unauthenticated). |
| `test_cleanup.py` (2 tests) | Expired room pruning via `get_rooms_payload`: removes expired rooms + messages, preserves valid rooms. |
| `test_helpers.py` (9 tests) | Unit tests for module-level helpers: `_parse_admin_addresses`, `is_admin_address` case-insensitivity, `hash_nonce` stability, `_iso` datetime formatting, `_members_payload` shape, `_msg_dict` shape, `ConnectionManager`/`RoomChatManager` stale socket cleanup. |
| `test_migrations.py` (1 test) | Alembic smoke test: applies all migrations to empty SQLite in a temp directory, asserts all 8 tables exist, asserts room columns (`description`, `communicator_link`, `requirements`) and roomevent columns (`starts_at`, `ends_at`, `created_by`, `updated_at`). |

### WebSocket Coverage

The `TestClient` supports WebSocket calls via `client.websocket_connect("/ws/rooms/{room_name}/chat?token=...")`. Tests in `test_chat.py`, `test_room_events.py`, `test_kick.py`, `test_admin.py`, and `test_admin_edges.py` exercise real WS frames against the running app instance within the test session.

### Alembic Migration Tests

`test_migrations.py` runs `alembic upgrade head` against a fresh SQLite database in a `tmp_path`, then inspects the resulting schema for all expected tables and columns. A separate CI job (`backend-migrations`) applies migrations to a real Postgres container and additionally runs `alembic downgrade -1` + `alembic upgrade head` round-trip and `alembic check` for model/migration drift detection.

---

## Frontend Tests

The frontend test suite uses **Vitest** with **jsdom** environment. All tests are unit/integration — no browser is launched.

### Running

```bash
cd frontend
bun run test
```

With coverage:

```bash
bun run test -- --coverage
```

### Configuration

From `frontend/vite.config.js`:

```js
test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts']
}
```

- `globals: true` — `describe`, `it`, `expect`, `vi` are available without explicit imports (`vitest/globals` in `tsconfig.json` adds type support).
- `environment: 'jsdom'` — provides a browser-like DOM (`document`, `window`, `sessionStorage`, `FormData`, etc.) without a real browser.
- `setupFiles: ['./src/test/setup.ts']` — imports `@testing-library/jest-dom` for DOM matchers (`toBeInTheDocument`, etc.).

The `tsconfig.json` includes `"types": ["vitest/globals"]` for type-aware autocompletion.

### Coverage Areas

| Test file | Coverage |
|-----------|----------|
| `signing.test.ts` | Validates canonical chat message format from `signing.ts` — special characters preserved, `buildChatSigningMessage` produces exact payload, `signChatMessage` delegates to signer with correct message. |
| `signingKey.test.ts` | `saveSigningKey`, `loadSigner`, `clearSigningKey` — verifies sessionStorage round-trip and invalid key removal. |
| `roomsStore.test.ts` | Type guards `isNullableString` and `isRoomSummary` from `roomsStore.ts` — edge cases for missing fields, wrong types, nullable fields. |
| `chatStore.test.ts` | Validators and `parseFrame` from `chatStore.ts` — `isChatMessage`, `isRoomMember`, `isRsvpStatus`, `isRsvpEntry`, `isRoomEventState`, frame parsing for message/unknown/bad JSON. |
| `lobbyLocations.test.ts` | `isLobbyLocation`, `lobbyLocationLabel`, `distanceKm` (Haversine: zero distance, London→Frankfurt ~640 km), `nearestLobbyLocation`, `FALLBACK_LOBBY_LOCATION` exists in list. |
| `hintsContext.svelte.test.ts` | `HintsState` class — initialization with/without hints, `set()`, `clear()` methods. Svelte 5 runes (`$state`) integration. |
| `auth.page.server.test.ts` | `+page.server.ts` load and actions — no session → `user: null`, valid token → user decoded, invalid token cleared; login action (missing token, stores cookie); logout action (deletes cookie). |
| `profile.page.server.test.ts` | `+page.server.ts` load and update action — redirects without session, loads profile from API, redirects on invalid session; update requires auth, rejects empty username, updates via PATCH. |
| `rooms.page.server.test.ts` | `+page.server.ts` load and actions — loads without login, loads logged-in user; `create` rejects unauthenticated/missing-fields; `addGame` rejects empty name. |
| `rooms.name.page.server.test.ts` | `+page.server.ts` load and actions — redirects when room missing (303 → `/rooms`); `setRsvp` rejects missing auth and invalid status; `kickMember` rejects missing member. |

### Route-Level Tests

The four route tests (`auth.page.server.test.ts`, `profile.page.server.test.ts`, `rooms.page.server.test.ts`, `rooms.name.page.server.test.ts`) exercise SvelteKit server load functions and form actions directly by importing from the route modules. They mock `$env/dynamic/public`, `$env/dynamic/private`, `jwt-decode`, `globalThis.fetch`, and the `cookies` object to simulate server-side request context. These are not full end-to-end tests — they verify the server-side logic (auth guards, API proxying, validation) without starting the SvelteKit dev server.

---

## Related Documentation

- [REST API Reference](../backend/api-reference.md) — endpoint contracts tested by the backend suite.
- [WebSocket Protocol Reference](../backend/realtime.md) — WS frame types verified by `test_chat`, `test_room_events`, `test_kick`, and `test_admin`.
- [Deployment Guide](deployment.md) — CI pipeline integration, migration smoke tests, and coverage gates.
