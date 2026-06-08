# Playlink Backend (FastAPI)

FastAPI application handling identity authentication, room management, and realtime room-list broadcasting over WebSockets.

## Tech Stack

- **Framework:** FastAPI
- **ORM:** SQLModel (SQLAlchemy + Pydantic)
- **Database:** PostgreSQL (production / Docker) / SQLite (testing)
- **Migrations:** Alembic
- **Auth:** BIP39 identity address + ECDSA signature verification, JWT sessions
- **Package Manager:** `uv`

## Project Structure

- `main.py` — API endpoints, WebSocket handler, application lifecycle.
- `models.py` — SQLModel schemas (`User`, `Nonce`, `Room`, `RoomMember`, `Game`).
- `database.py` — Engine and session management. Auto-rewrites `@db:` to `@localhost:` when not running inside a container.
- `alembic/` — Migration environment and version scripts.
- `entrypoint.sh` — Container entrypoint: waits for the DB, runs `alembic upgrade head`, then starts uvicorn.
- `docs/auth-flow.md` — Detailed authentication flow specification.
- `tests/` — Pytest suite.

## API Endpoints

| Method | Path                       | Auth | Description                                                                                                                                       |
| ------ | -------------------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET    | `/`                        | —    | Service health check.                                                                                                                             |
| POST   | `/auth/request-nonce`      | —    | Request a one-time nonce for an identity address.                                                                                                 |
| POST   | `/auth/verify`             | —    | Verify a signed nonce and receive a JWT.                                                                                                          |
| GET    | `/users/me`                | JWT  | Return the authenticated user.                                                                                                                    |
| GET    | `/rooms`                   | —    | List all rooms.                                                                                                                                   |
| POST   | `/rooms`                   | JWT  | Create a room (max 3 active rooms per user). Auto-joins the creator.                                                                              |
| POST   | `/rooms/{room_name}/join`  | JWT  | Join a room (rejected if full or already a member).                                                                                               |
| POST   | `/rooms/{room_name}/leave` | JWT  | Leave a room.                                                                                                                                     |
| GET    | `/games`                   | —    | List supported game names, ordered by `sort_order`.                                                                                               |
| WS     | `/ws/rooms`                | —    | On connect, sends the current room list as JSON. Broadcasts an updated list to all connected clients whenever a room is created, joined, or left. |

OpenAPI docs are served at `/docs`.

## Realtime

A `ConnectionManager` in `main.py` keeps the set of active WebSocket clients. After every successful `POST /rooms`, `/rooms/{name}/join`, or `/rooms/{name}/leave`, the server broadcasts the full room list (computed by `get_rooms_payload`) to every connected client. Expired rooms (`expires_at <= now`) are pruned during this step.

## Authentication Flow (Summary)

1. Client `POST`s its `identity_address` to `/auth/request-nonce`.
2. Client signs the message `Sign in to Playlink\nNonce: <uuid>` locally.
3. Client `POST`s `{ address, nonce, signature }` to `/auth/verify`.
4. Backend recovers the address from the signature, marks the nonce as used, and issues a JWT.

Authenticated endpoints expect `Authorization: Bearer <token>` (OAuth2 password bearer scheme). Full specification in [`docs/auth-flow.md`](docs/auth-flow.md).

## Development Setup

### 1. Prerequisites

- Install `uv`: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Python 3.14+
- A running PostgreSQL instance (or use Docker Compose from the project root).

### 2. Environment Configuration

Copy `.env.example` from the project root to `.env`. The backend reads it via `python-dotenv`.

| Variable                   | Purpose                                                                        | Default |
| -------------------------- | ------------------------------------------------------------------------------ | ------- |
| `DATABASE_URL`             | SQLAlchemy URL (e.g. `postgresql+psycopg://user:pass@host:5432/db`). Required. | —       |
| `JWT_SECRET`               | Secret used to sign JWTs. Required.                                            | —       |
| `JWT_ALGORITHM`            | JWT signing algorithm.                                                         | `HS256` |
| `NONCE_EXPIRATION_MINUTES` | TTL for issued auth nonces.                                                    | `5`     |
| `JWT_EXPIRATION_MINUTES`   | TTL for issued JWT sessions.                                                   | `60`    |

CORS is hard-coded in `main.py` for `playlink.bartek.monster`, `localhost:3000`, `localhost:5173`, and their `127.0.0.1` equivalents.

### 3. Install Dependencies

```bash
uv sync
```

### 4. Apply Migrations

From the `backend/` directory:

```bash
uv run alembic upgrade head
```

### 5. Run the API

From the `backend/` directory:

```bash
uv run uvicorn main:app --reload
```

The API will be available at `http://localhost:8000` with interactive docs at `/docs`.

## Database Migrations

Alembic is configured against the SQLModel metadata. To create a new migration after changing models:

```bash
cd backend
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

In Docker, `entrypoint.sh` runs `alembic upgrade head` automatically before launching uvicorn.

## Running Tests

Tests use an in-memory SQLite database and do not require PostgreSQL to be running.

```bash
uv run pytest
```

To see backend coverage locally, run:

```bash
uv run pytest --cov=main --cov=models --cov=database --cov=usernames --cov-report=term-missing:skip-covered --cov-fail-under=80
```

The coverage job measures the backend application modules (`main.py`,
`models.py`, `database.py`, and `usernames.py`) and fails if total coverage
drops below 80%. The test suite combines unit tests for helper functions with
integration tests through FastAPI's `TestClient`. WebSocket behavior is covered
through `websocket_connect`, and Alembic has a smoke test that upgrades a clean
SQLite database to `head`.

## Docker

The backend is designed to run via Docker Compose from the project root:

```bash
docker compose up --build backend
```

The container waits for the `db` service to accept connections, runs migrations, and then starts uvicorn on port `8000`.
