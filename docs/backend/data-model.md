# Data Model Reference

> **Source:** `backend/models.py`, `backend/database.py`, `backend/usernames.py`

This document describes every database table, field, constraint, relationship, and enum used in the Playlink backend. The project uses **SQLModel** (a thin wrapper that fuses SQLAlchemy ORM models with Pydantic v2 validation) managed through **Alembic** for schema migrations. The runtime engine/session setup lives in `database.py`; the table classes live in `models.py`.

────────────────

## Engine & Session Setup

The backend connects to PostgreSQL (SQLite in tests) via a single `DATABASE_URL` environment variable:

- `DATABASE_URL` **MUST** be set at process start; if missing, `database.py` raises `RuntimeError("DATABASE_URL environment variable is not set")`.
- If the URL contains `@db:` (the Docker Compose hostname) **and** the file `/.dockerenv` does **not** exist, the engine replaces `@db:` with `@localhost:` — this lets developers on the host machine reuse the same config without manual edits.
- The engine is created with `create_engine(DATABASE_URL)` (no special pool config).

Two utility functions are exported:

| Function | Signature | Behaviour |
|----------|-----------|-----------|
| `create_db_and_tables()` | `() -> None` | Calls `SQLModel.metadata.create_all(engine)`. Used in tests; in production the schema is managed by Alembic migrations via `entrypoint.sh` (`alembic upgrade head`). |
| `get_session()` | `() -> Generator[Session]` | Opens a `Session(engine)`, yields it as a FastAPI dependency, and closes it when the request ends. |

────────────────

## Entity-Relationship Overview

```mermaid
erDiagram
    Game {
        int id PK
        string name UK
        int sort_order
    }

    Room {
        int id PK
        string name UK
        string game
        string lobby_location
        int players_max
        string description
        string communicator_link
        string requirements
        string created_by
        datetime created_at
        datetime expires_at
    }

    RoomMember {
        int room_id PK, FK
        int user_id PK, FK
        datetime joined_at
    }

    Message {
        int id PK
        int room_id FK
        string sender_address
        string content
        datetime created_at
        string signature
        string sent_at
    }

    RoomEvent {
        int id PK
        int room_id FK, UQ
        datetime starts_at
        datetime ends_at
        string created_by
        datetime created_at
        datetime updated_at
    }

    RoomEventRsvp {
        int id PK
        int event_id FK
        int user_id FK
        string status
        datetime updated_at
    }

    User {
        int id PK
        string identity_address UK
        string username UK
        datetime created_at
        datetime last_login
    }

    Nonce {
        int id PK
        string identity_address
        string value UK
        datetime expires_at
        bool used
        int user_id FK
    }

    Room  ||--o{ Message  : "has"
    Room  ||--o{ RoomEvent : "has"
    Room  ||--o{ RoomMember : "membership"
    RoomMember }o--|| User : "belongs to"
    RoomEvent ||--o{ RoomEventRsvp : "rsvp"
    RoomEventRsvp }o--|| User : "respondent"
    User  ||--o{ Nonce    : "auth"
    User  ||--o{ RoomMember : "joined"
```

> **Foreign-key graph (acyclic):** `nonce.user_id → user.id`, `roommember.room_id → room.id`, `roommember.user_id → user.id`, `message.room_id → room.id`, `roomevent.room_id → room.id` (ON DELETE CASCADE, UNIQUE), `roomeventrsvp.event_id → roomevent.id` (ON DELETE CASCADE), `roomeventrsvp.user_id → user.id` (ON DELETE CASCADE).

────────────────

## RsvpStatus (StrEnum)

Defined at module level in `models.py`. Used as the `status` column type in `RoomEventRsvp`.

| Member    | String value |
|-----------|--------------|
| `present` | `"present"`  |
| `absent`  | `"absent"`   |
| `maybe`   | `"maybe"`    |

## DEFAULT_LOBBY_LOCATION

```python
DEFAULT_LOBBY_LOCATION = "eu-central"
```

Fallback value for `Room.lobby_location` when the client omits the field.

────────────────

## Table: `roommember` — RoomMember

Many-to-many link table between `User` and `Room`. The composite primary key means a user can hold at most one membership per room; re-joining after leaving inserts a new row.

| Field       | Type     | Constraints / Field() options                                | Description                                  |
|-------------|----------|--------------------------------------------------------------|----------------------------------------------|
| `room_id`   | `int`    | `primary_key=True`, `foreign_key="room.id"`                  | Composite PK: room this membership refers to |
| `user_id`   | `int`    | `primary_key=True`, `foreign_key="user.id"`                  | Composite PK: member user                    |
| `joined_at` | `datetime` | `default_factory=lambda: datetime.now(UTC)`                | Timestamp when membership was created        |

**Relationships:** None declared directly (used via `link_model=RoomMember` on `Room.members` and `User.rooms`).

────────────────

## Table: `room` — Room

The core grouping entity. A room represents a game session that expires after a configurable TTL.

| Field              | Type             | Constraints / Field() options                                          | Description                                                        |
|--------------------|------------------|------------------------------------------------------------------------|--------------------------------------------------------------------|
| `id`               | `int \| None`    | `primary_key=True`, `default=None`                                    | Auto-increment primary key                                         |
| `name`             | `str`            | `index=True`, `unique=True`                                           | Human-readable room name (unique, used in URLs)                    |
| `game`             | `str`            | *(none)*                                                              | Name of the game being played (free text, validated at API layer)  |
| `lobby_location`   | `str`            | `default=DEFAULT_LOBBY_LOCATION`, `index=True`                        | Region/city of the lobby (e.g. `"eu-central"`, `"us-west"`)       |
| `players_max`      | `int`            | *(none)*                                                              | Maximum number of members                                          |
| `description`      | `str \| None`    | `default=None`, `max_length=500`                                      | Free-text description of the session / expectations                |
| `communicator_link`| `str \| None`    | `default=None`, `max_length=500`                                      | Voice-chat invite link (Discord, TeamSpeak, etc.)                  |
| `requirements`     | `str \| None`    | `default=None`, `max_length=1000`                                     | Hardware / software / skill requirements                           |
| `created_by`       | `str`            | `index=True`                                                          | Ethereum address (`identity_address`) of the room creator          |
| `created_at`       | `datetime`       | `default_factory=lambda: datetime.now(UTC)`                           | Creation timestamp                                                 |
| `expires_at`       | `datetime`       | `default_factory=lambda: datetime.now(UTC) + timedelta(minutes=60)`   | TTL; rooms past this timestamp are pruned by the query layer       |

**Relationships:**

| Attribute  | Type         | Back-populates / link_model                                  |
|------------|--------------|--------------------------------------------------------------|
| `members`  | `list[User]` | `back_populates="rooms"`, `link_model=RoomMember`            |

────────────────

## Table: `message` — Message

Chat messages sent via WebSocket, stored for history replay. Supports EIP-191 signed messages (added in migration `c4a9f1e7b6d2`, Issue #59); legacy (pre-signing) messages have NULL `signature` and `sent_at`.

| Field            | Type             | Constraints / Field() options                                 | Description                                                       |
|------------------|------------------|---------------------------------------------------------------|-------------------------------------------------------------------|
| `id`             | `int \| None`    | `primary_key=True`, `default=None`                            | Auto-increment primary key                                        |
| `room_id`        | `int`            | `foreign_key="room.id"`, `index=True`                         | Owning room                                                       |
| `sender_address` | `str`            | `index=True`                                                  | Ethereum address of the sender (`identity_address`)               |
| `content`        | `str`            | *(none)*                                                      | Message body text                                                 |
| `created_at`     | `datetime`       | `default_factory=lambda: datetime.now(UTC)`, `index=True`     | Server-assigned timestamp when message was persisted              |
| `signature`      | `str \| None`    | `default=None`                                                | EIP-191 hex signature over the canonical payload (Issue #59)      |
| `sent_at`        | `str \| None`    | `default=None`                                                | Client-supplied ISO-8601 timestamp that was signed                |

────────────────

## Table: `roomevent` — RoomEvent

A single scheduled gathering attached to a room. Currently constrained to at most one event per room (`room_id` is `UNIQUE`); lifting that constraint later is a non-breaking change (Issue #62).

| Field        | Type             | Constraints / Field() options                                                          | Description                                       |
|--------------|------------------|----------------------------------------------------------------------------------------|---------------------------------------------------|
| `id`         | `int \| None`    | `primary_key=True`, `default=None`                                                     | Auto-increment primary key                        |
| `room_id`    | `int`            | `sa_column=Column("room_id", Integer, ForeignKey("room.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)` | Owning room (UNIQUE — one event per room)         |
| `starts_at`  | `datetime`       | `index=True`                                                                           | Scheduled start time                              |
| `ends_at`    | `datetime`       | `index=True`                                                                           | Scheduled end time                                |
| `created_by` | `str`            | `index=True`                                                                           | Ethereum address of the room creator              |
| `created_at` | `datetime`       | `default_factory=lambda: datetime.now(UTC)`                                            | Creation timestamp                                |
| `updated_at` | `datetime`       | `default_factory=lambda: datetime.now(UTC)`                                            | Last-update timestamp (bumped on reschedule)      |

────────────────

## Table: `roomeventrsvp` — RoomEventRsvp

A member's attendance declaration for a `RoomEvent`. Uses **upsert semantics** — an RSVP is created or updated in place. The unique constraint on `(event_id, user_id)` enforces one RSVP per user per event.

| Field        | Type             | Constraints / Field() options                                                          | Description                                     |
|--------------|------------------|----------------------------------------------------------------------------------------|-------------------------------------------------|
| `id`         | `int \| None`    | `primary_key=True`, `default=None`                                                     | Auto-increment primary key                      |
| `event_id`   | `int`            | `sa_column=Column("event_id", Integer, ForeignKey("roomevent.id", ondelete="CASCADE"), index=True, nullable=False)` | Target event (CASCADE-deleted with event)       |
| `user_id`    | `int`            | `sa_column=Column("user_id", Integer, ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False)`       | Responding user (CASCADE-deleted with user)     |
| `status`     | `RsvpStatus`     | *(none)*                                                                               | One of `present`, `absent`, `maybe`             |
| `updated_at` | `datetime`       | `default_factory=lambda: datetime.now(UTC)`                                            | Last modification timestamp                     |

**`__table_args__`:**

```python
__table_args__ = (UniqueConstraint("event_id", "user_id"),)
```

────────────────

## Table: `game` — Game

A curated list of games users can select when creating a room. Seeded at migration time with five entries: *Quake III Arena*, *Diablo II*, *StarCraft*, *Half-Life*, *Unreal Tournament*.

| Field       | Type          | Constraints / Field() options          | Description                                    |
|-------------|---------------|----------------------------------------|------------------------------------------------|
| `id`        | `int \| None` | `primary_key=True`, `default=None`     | Auto-increment primary key                     |
| `name`      | `str`         | `index=True`, `unique=True`            | Display name of the game                       |
| `sort_order`| `int`         | `index=True`                           | Ordinal for UI ordering (lower = earlier)      |

────────────────

## Table: `user` — User

Represents an authenticated participant. A user is created lazily on first successful wallet signature verification.

| Field             | Type             | Constraints / Field() options                                        | Description                                         |
|-------------------|------------------|----------------------------------------------------------------------|-----------------------------------------------------|
| `id`              | `int \| None`    | `primary_key=True`, `default=None`                                   | Auto-increment primary key                          |
| `identity_address`| `str`            | `index=True`, `unique=True`                                          | Ethereum address (checksummed, from ECDSA recovery) |
| `username`        | `str`            | `default_factory=lambda: f"user_{secrets.token_hex(4)}"`, `index=True`, `unique=True` | Auto-generated display name (e.g. `user_a1b2c3d4`); owner may change once |
| `created_at`      | `datetime`       | `default_factory=lambda: datetime.now(UTC)`                          | Registration timestamp                              |
| `last_login`      | `datetime \| None` | `default=None`                                                     | Timestamp of most recent successful authentication   |

**Relationships:**

| Attribute | Type           | Back-populates / link_model                                  |
|-----------|----------------|--------------------------------------------------------------|
| `nonces`  | `list[Nonce]`  | `back_populates="user"`                                      |
| `rooms`   | `list[Room]`   | `back_populates="members"`, `link_model=RoomMember`          |

────────────────

## Table: `nonce` — Nonce

Ephemeral authentication tokens used in the EIP-191 / ECDSA challenge-response flow. The `value` field stores a SHA-256 hash of the original nonce string (computed by the `hash_nonce` helper in `main.py`), preventing the raw nonce from persisting in the database.

| Field             | Type             | Constraints / Field() options                  | Description                                             |
|-------------------|------------------|-------------------------------------------------|---------------------------------------------------------|
| `id`              | `int \| None`    | `primary_key=True`, `default=None`              | Auto-increment primary key                              |
| `identity_address`| `str`            | `index=True`                                    | Ethereum address that requested the nonce               |
| `value`           | `str`            | `unique=True`                                   | SHA-256 hash of the challenge nonce                     |
| `expires_at`      | `datetime`       | *(none — required)*                             | Expiry timestamp; expired nonces are rejected by the API|
| `used`            | `bool`           | `default=False`                                 | Single-use flag — set to `True` after successful verification |
| `user_id`         | `int \| None`    | `default=None`, `foreign_key="user.id"`          | FK to the user, populated only after successful auth    |

**Relationships:**

| Attribute | Type           | Back-populates / link_model         |
|-----------|----------------|-------------------------------------|
| `user`    | `User \| None` | `back_populates="nonces"`           |

────────────────

## Cross-References

- **[Migrations](migrations.md)** — Alembic migration chain, all seven versions from initial tables to message signing columns.
- **[API Reference](api-reference.md)** — REST endpoints that read and write each of these entities.
- **[Realtime](realtime.md)** — WebSocket frames that broadcast entity state changes (event-update, roster-update, rsvp-update).
