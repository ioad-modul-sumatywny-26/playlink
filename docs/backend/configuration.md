# Backend Configuration & Validation

This document covers every runtime configuration point of the Playlink backend: environment variables, the admin authorization model, rate limiting, CORS middleware, and username validation rules.

> **Source:** `backend/main.py` (lines 56–104, 508–527, 77–80, 83–103, 309–320), `backend/usernames.py`, `docker-compose.yml`, `.env.example`

---

## Environment Variables

The backend loads configuration from a `.env` file at the project root (`backend/../.env`). On startup `main.py` calls `dotenv.load_dotenv()` if that file exists; the variables below are then read via `os.getenv()`.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | SQLAlchemy database URL (e.g. `postgresql+psycopg://user:pass@host:port/db`). Raises `RuntimeError` at import time when unset. |
| `JWT_SECRET` | Yes | — | Symmetric key for HS256 JWT signing/verification. Raises `RuntimeError` at import time when unset. |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm. Only HS256 is used. |
| `NONCE_EXPIRATION_MINUTES` | No | `5` | Lifetime of an auth nonce before it expires. |
| `JWT_EXPIRATION_MINUTES` | No | `60` | Lifetime of a JWT session token after issuance. |
| `ROOM_CLEANUP_INTERVAL_SECONDS` | No | `60` | Interval between background sweeps that delete expired rooms. |
| `DEFAULT_RATE_LIMIT` | No | `10/minute` | slowapi rate-limit string applied to every REST endpoint (see [Rate Limiting](#rate-limiting)). |
| `WS_RATE_LIMIT_MAX_MESSAGES` | No | `10` | Maximum number of chat messages a single address may send within the time window. |
| `WS_RATE_LIMIT_TIME_WINDOW_SECONDS` | No | `10` | Sliding time window (seconds) for the WebSocket chat rate limit. |
| `ADMIN_ADDRESSES` | No | `""` (empty) | Comma-separated identity addresses granted admin privileges. Case-insensitive (see [Admin Authorization](#admin-authorization)). |

### Postgres Compose Variables

These are the individual variables in `.env.example` that feed into `DATABASE_URL`. The backend itself reads only `DATABASE_URL`; the compose variables are used by the `db` service in `docker-compose.yml`.

| Variable | Example Value | Purpose |
|---|---|---|
| `POSTGRES_USER` | `postgres` | Database user name |
| `POSTGRES_PASSWORD` | `postgres` | Database password |
| `POSTGRES_DB` | `playlink` | Database name |
| `POSTGRES_HOST` | `db` | Database hostname (the Docker service name) |
| `POSTGRES_PORT` | `5432` | Database port |

The assembled `DATABASE_URL` takes the form:

```
postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
```

#### `@db` → `@localhost` Rewrite

When the backend runs outside Docker (e.g. during local development) and `DATABASE_URL` contains `@db:`, `database.py` rewrites it to `@localhost:` so the connection targets the locally-mapped Postgres port. The presence of `/.dockerenv` disables this rewrite.

---

## Admin Authorization

Admin authority lives **entirely** in the `ADMIN_ADDRESSES` environment variable. There is no `is_admin` column on the `User` model — the only way to grant or revoke admin power is to edit `.env` and restart.

### Address Parsing

```python
# main.py:83-98
def _parse_admin_addresses(raw: str | None) -> set[str]:
    """Parse the comma-separated `ADMIN_ADDRESSES` env value into a set.
    Addresses are lower-cased so membership checks are case-insensitive and
    independent of EIP-55 checksum casing. An empty/unset value yields an
    empty set — i.e. the system simply has no admins.
    """
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}

ADMIN_ADDRESSES: set[str] = _parse_admin_addresses(os.getenv("ADMIN_ADDRESSES"))
```

The resulting `ADMIN_ADDRESSES` set is a module-level mutable object so tests can hot-swap it.

### Membership Check

```python
# main.py:101-103
def is_admin_address(address: str) -> bool:
    return address.lower() in ADMIN_ADDRESSES
```

Lower-casing both sides makes membership independent of EIP-55 checksum casing.

### Auth Dependency

All admin-gated endpoints (room deletion, game CRUD, member kick) use the `get_admin_address` dependency:

```python
# main.py:309-320
async def get_admin_address(
    address: Annotated[str, Depends(get_current_user_address)],
) -> str:
    if not is_admin_address(address):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return address
```

This function first resolves the caller's identity via normal JWT auth (`get_current_user_address`), then checks the whitelist. A forged `is_admin` claim in the JWT payload cannot grant access here because the source of truth is `ADMIN_ADDRESSES`.

### Admin Flag in Responses

The JWT payload and the `GET /users/me` / `PATCH /users/me` responses include an `is_admin` boolean computed at response time:

```python
# main.py:666-675
def _user_payload(user: User) -> dict:
    return {
        ...
        "is_admin": is_admin_address(user.identity_address),
    }
```

### Enforcing Admin for Kick

The kick endpoint (`POST /rooms/{name}/members/{address}/kick`) receives the admin's resolved address as a dependency. The response payload marks members with `"is_admin": true` (see `_members_payload` at line 328).

---

## Rate Limiting

Two independent rate-limiting mechanisms run in the backend.

### REST API Rate Limiting (slowapi)

Configured at app startup:

```python
# main.py:508-511
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.extension import _rate_limit_exceeded_handler

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

- **Key**: Remote client IP address (via `get_remote_address`).
- **Default window**: `10/minute` (configurable via `DEFAULT_RATE_LIMIT`).
- **429 handler**: The standard slowapi `_rate_limit_exceeded_handler`, which returns `429 Too Many Requests`.
- **Scope**: Every REST endpoint carries `@limiter.limit(DEFAULT_RATE_LIMIT)`. This includes health check, auth, users, rooms, games, lobby-locations, events, and kick endpoints.
- **Test override**: The test conftest sets `app.state.limiter.enabled = False` (see `conftest.py`).

### WebSocket Chat Rate Limiting

The `/ws/rooms/{name}/chat` endpoint enforces a **per-address** sliding-window limit independent of slowapi:

```python
# main.py:77-80
WS_LIMITS: dict[str, list[float]] = defaultdict(list)

MAX_MSGS = int(os.getenv("WS_RATE_LIMIT_MAX_MESSAGES", "10"))
WINDOW = int(os.getenv("WS_RATE_LIMIT_TIME_WINDOW_SECONDS", "10"))
```

Inside the per-message receive loop (line 1486–1496):

1. Prune entries older than `WINDOW` seconds from the address's timestamp list.
2. If the remaining list length ≥ `MAX_MSGS`, close the WebSocket with code **4429**.
3. Otherwise append the current timestamp and process the message.

The `WS_LIMITS` dictionary is never pruned globally — stale entries for inactive addresses remain in memory until the process restarts, but they cost only a few floats per address.

---

## CORS

CORS middleware is configured with an explicit whitelist of five origins:

```python
# main.py:513-527
origins = [
    "https://playlink.bartek.monster",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- **allow_credentials**: `True` — necessary for the `session` cookie used by the frontend BFF (see [API Reference](api-reference.md#authentication)).
- **allow_methods**: `["*"]` — all HTTP methods permitted.
- **allow_headers**: `["*"]` — all HTTP headers permitted.
- No `expose_headers` is set; the default set applies.

The production origin (`https://playlink.bartek.monster`) points at the deployed frontend. The four `localhost` variants cover SvelteKit dev server (`:5173`) and the Node adapter production mode (`:3000`), with both `localhost` and `127.0.0.1` to handle DNS variations.

---

## Username Validation

Defined in `backend/usernames.py` and called by `PATCH /users/me`.

### Format Constraint

```python
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
```

Usernames must be:
- 3–20 characters long
- Alphanumeric (`a–z`, `A–Z`, `0–9`), underscore (`_`), or hyphen (`-`)
- No leading/trailing whitespace, no spaces

### Profanity Stoplist

The backend vendors the [LDNOOBW English word list](https://github.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words) at `backend/data/profanity_en.txt` (git blob `a438b9ca33af77341768bd6c63ce3e48e726b76e`, retrieved 2026-05-29). The check is fully offline.

```python
# usernames.py:21-39
@lru_cache(maxsize=1)
def load_stoplist() -> frozenset[str]:
    """Load the profanity stoplist once, lowercased, blanks dropped."""
    lines = _STOPLIST_PATH.read_text(encoding="utf-8").splitlines()
    return frozenset(word.strip().lower() for word in lines if word.strip())


def contains_profanity(name: str) -> bool:
    """True if `name` as a whole, or any `_`/`-` token, is a stoplist word.

    Exact whole-string and per-token matching (rather than substring) avoids
    false positives like `assassin` or `classic` while still catching
    evasions such as `xX_fuck_Xx`.
    """
    stoplist = load_stoplist()
    lowered = name.lower()
    if lowered in stoplist:
        return True
    return any(token in stoplist for token in _TOKEN_SPLIT.split(lowered) if token)
```

- Whole-string match against the stoplist.
- Per-token split on `_` and `-` (regex `[_-]`), with each non-empty token checked.
- **No substring matching**: a name like `assassin` passes because neither `assassin` nor any of its `_-delimited` tokens is in the stoplist as a complete entry.

### Validation Function

```python
# usernames.py:42-52
def validate_username(name: str) -> str | None:
    """Return an error code, or `None` when valid.
    Codes: "invalid_format" (fails the regex), "profane" (hits the stoplist).
    """
    if not USERNAME_RE.match(name):
        return "invalid_format"
    if contains_profanity(name):
        return "profane"
    return None
```

| Return value | Meaning | HTTP status (in endpoint) |
|---|---|---|
| `None` | Valid | 200 (success) |
| `"invalid_format"` | Regex failed | 400 (see [API Reference](api-reference.md#patch-usersme)) |
| `"profane"` | Stoplist match | 400 |

Duplicate usernames produce a 409 Conflict, detected via SQL `IntegrityError` on the `user.username` unique index.

---

## Related Documents

- [API Reference](api-reference.md) — endpoint signatures, request/response shapes, status codes.
- [Realtime](realtime.md) — WebSocket protocol, close codes including rate-limit code 4429.
- [Deployment](../operations/deployment.md) — Docker Compose setup, database configuration, CI/CD pipeline.
