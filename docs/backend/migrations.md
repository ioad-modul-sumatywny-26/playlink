# Migrations

This document describes the Alembic-based migration system used to manage the Playlink database schema. It covers wiring, common commands, the full migration history, and per-migration schema changes.

> **Source:** `backend/alembic/env.py`, `backend/alembic.ini`, `backend/alembic/versions/`, `backend/entrypoint.sh`

---

## Alembic Wiring

### `alembic/env.py`

The environment script configures Alembic's offline and online migration modes:

- **Model import for autogenerate**: Every SQLModel table class is imported so `SQLModel.metadata` reflects the full schema:
  ```python
  from models import Game, Message, Nonce, Room, RoomEvent, RoomEventRsvp, User
  ```
  `target_metadata = SQLModel.metadata` tells Alembic which metadata to diff against the live database.

- **`get_url()` — local dev rewrite**: Reads `DATABASE_URL` from the environment. When running outside Docker (no `/.dockerenv`), the host `@db:` is rewritten to `@localhost:` — the same logic in `backend/database.py`. Raises `RuntimeError` if `DATABASE_URL` is unset.

- **`load_dotenv`**: Loads `.env` from the project root (`backend/../.env`) if the file exists.

- **Offline mode** (`alembic upgrade --sql`): Uses `literal_binds=True` and `dialect_opts={"paramstyle": "named"}` to produce portable SQL.

- **Online mode**: Builds a connection pool via `engine_from_config` with `pool.NullPool` (no persistent connection pooling across migration steps), then configures the context.

### `alembic.ini`

| Key | Value | Notes |
|-----|-------|-------|
| `script_location` | `alembic` | Relative to `backend/` where `alembic.ini` lives |
| `prepend_sys_path` | `.` | Enables `from models import …` inside migrations |
| `logger_root` level | `WARN` | |
| `logger_sqlalchemy` level | `WARN` | Suppresses engine SQL logging |
| `logger_alembic` level | `INFO` | Shows migration progress |
| `handler_console` | `StreamHandler`, stderr | All log output |

---

## Operator Commands

All commands run from the `backend/` directory with the project's managed Python environment (`uv`).

### Create a revision (autogenerate)

```bash
uv run alembic revision --autogenerate -m "description of change"
```

Alembic diffs `SQLModel.metadata` against the live database and writes a new migration script under `alembic/versions/`. Review the generated output carefully — autogenerate can miss rename/type-change heuristics.

### Apply pending migrations

```bash
uv run alembic upgrade head
```

Migrations are idempotent and transactional. Alembic tracks applied revisions in the `alembic_version` table (single row with `version_num`).

### Check current revision

```bash
uv run alembic current
```

### Roll back one step

```bash
uv run alembic downgrade -1
```

### View history

```bash
uv run alembic history
```

### Docker startup

In production, `entrypoint.sh` waits for the database (TCP port 5432 on host `db`, up to 30 attempts with 2-second sleeps) then runs:

```bash
alembic upgrade head
```

before starting uvicorn. See [deployment](../operations/deployment.md) for the full startup sequence.

---

## Migration History

All migrations in dependency order (oldest first).

| Revision ID | Parent (down_revision) | Summary |
|-------------|------------------------|---------|
| `f273b29c941a` | `None` (root) | Initial schema: game, room, user, nonce, roommember + seed games |
| `a1b2c3d4e5f6` | `f273b29c941a` | Add `message` table |
| `17b0946aadca` | `a1b2c3d4e5f6` | Add room metadata columns |
| `4fb1ffbfc7d9` | `17b0946aadca` | Add `roomevent` + `roomeventrsvp` |
| `b7e2c1f4d8a3` | `4fb1ffbfc7d9` | Add `ends_at` to `roomevent` + backfill |
| `9c3d2e1f0a4b` | `b7e2c1f4d8a3` | Add `lobby_location` to `room` |
| `c4a9f1e7b6d2` | `9c3d2e1f0a4b` | Add `signature` + `sent_at` to `message` |

**Current head**: `c4a9f1e7b6d2`

---

## Per-Migration Detail

### `f273b29c941a` — initial

Root migration (`down_revision: None`). Creates five tables and seeds the `game` table.

**Tables created:**

| Table | Columns | Constraints & Indexes |
|-------|---------|-----------------------|
| `game` | `id` (PK, int), `name` (str), `sort_order` (int) | `ix_game_name` (unique), `ix_game_sort_order` |
| `room` | `id` (PK, int), `name` (str), `game` (str), `players_max` (int), `created_by` (str), `created_at` (datetime), `expires_at` (datetime) | `ix_room_name` (unique), `ix_room_created_by` |
| `user` | `id` (PK, int), `identity_address` (str), `username` (str), `created_at` (datetime), `last_login` (datetime, nullable) | `ix_user_identity_address` (unique), `ix_user_username` (unique) |
| `nonce` | `id` (PK, int), `identity_address` (str), `value` (str), `expires_at` (datetime), `used` (bool), `user_id` (int, nullable, FK → `user.id`) | `ix_nonce_identity_address`, unique on `value` |
| `roommember` | `room_id` (int, PK, FK → `room.id`), `user_id` (int, PK, FK → `user.id`), `joined_at` (datetime) | Composite primary key `(room_id, user_id)` |

**Seed data** — 5 games inserted via `op.bulk_insert`:

| name | sort_order |
|------|-----------|
| Quake III Arena | 1 |
| Diablo II | 2 |
| StarCraft | 3 |
| Half-Life | 4 |
| Unreal Tournament | 5 |

---

### `a1b2c3d4e5f6` — add message

`down_revision: f273b29c941a`

Creates the `message` table for room chat.

**`message` table:**

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | int (PK) | Auto-increment |
| `room_id` | int | FK → `room.id`, indexed (`ix_message_room_id`) |
| `sender_address` | str | Indexed (`ix_message_sender_address`) |
| `content` | str | |
| `created_at` | datetime | Indexed (`ix_message_created_at`) |

---

### `17b0946aadca` — add room metadata

`down_revision: a1b2c3d4e5f6`

Adds three nullable informational columns to the `room` table.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `description` | `VARCHAR(500)` | yes | Free-text room description |
| `communicator_link` | `VARCHAR(500)` | yes | Voice/chat link (Discord etc.) |
| `requirements` | `VARCHAR(1000)` | yes | Prerequisites for joining |

---

### `4fb1ffbfc7d9` — add room event and RSVP

`down_revision: 17b0946aadca`

Creates the `roomevent` and `roomeventrsvp` tables for scheduling.

**`roomevent` table:**

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | int (PK) | Auto-increment |
| `room_id` | int | FK → `room.id` (`ON DELETE CASCADE`), **unique** (one event per room — see Issue #62) |
| `starts_at` | datetime | Indexed (`ix_roomevent_starts_at`) |
| `created_by` | str | Indexed (`ix_roomevent_created_by`) |
| `created_at` | datetime | |
| `updated_at` | datetime | |

**`roomeventrsvp` table:**

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | int (PK) | Auto-increment |
| `event_id` | int | FK → `roomevent.id` (`ON DELETE CASCADE`), indexed |
| `user_id` | int | FK → `user.id` (`ON DELETE CASCADE`), indexed |
| `status` | ENUM `'rsvpstatus'` | One of `present`, `absent`, `maybe` |
| `updated_at` | datetime | |

Additional constraint: `UniqueConstraint("event_id", "user_id")` — one RSVP per user per event.

The downgrade explicitly drops the Postgres ENUM type via `sa.Enum(name="rsvpstatus").drop()` — a no-op on SQLite.

---

### `b7e2c1f4d8a3` — add event `ends_at`

`down_revision: 4fb1ffbfc7d9`

Adds an `ends_at` column to `roomevent` with a data backfill step.

| Column | Type | Constraints |
|--------|------|-------------|
| `ends_at` | datetime | NOT NULL, indexed (`ix_roomevent_ends_at`) |

**Backfill logic** (for environments that already have rows from the prior migration):

1. Column is added as nullable.
2. For each existing row, `ends_at` is set to `starts_at + 2 hours`.
3. Column is altered to `NOT NULL` using `batch_alter_table` (SQLite compatibility — it rebuilds the table; Postgres uses a plain `ALTER COLUMN`).

New rows always provide `ends_at` via the API, so the backfill only affects pre-existing events.

---

### `9c3d2e1f0a4b` — add room `lobby_location`

`down_revision: b7e2c1f4d8a3`

Adds a geographical lobby location column to `room`.

| Column | Type | Default | Constraints |
|--------|------|---------|-------------|
| `lobby_location` | `VARCHAR` | `'eu-central'` | NOT NULL, `server_default='eu-central'`, indexed (`ix_room_lobby_location`) |

The column is added directly as `NOT NULL` with a `server_default` — no backfill needed since the default applies to existing rows on creation.

---

### `c4a9f1e7b6d2` — add message signature and `sent_at`

`down_revision: 9c3d2e1f0a4b`

Issue #59 — adds EIP-191 signature verification fields to `message`.

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `signature` | str | yes | EIP-191 `personal_sign` hex string |
| `sent_at` | str | yes | Client-supplied ISO-8601 timestamp (e.g. `"2026-06-18T12:00:00Z"`) |

Both columns are nullable so legacy messages remain valid and render as unverified. New signed messages populate both fields; unsigned messages leave them `NULL`.

---

## Current Schema

See the [data model reference](data-model.md) for the full, up-to-date table definitions including all fields, constraints, and relationships at current head (`c4a9f1e7b6d2`).
