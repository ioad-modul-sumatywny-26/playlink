# Deployment & Operations

Reference for local development, Docker infrastructure, container startup, and CI/CD pipeline for the Playlink project.

> **Source:** `docker-compose.yml`, `backend/Dockerfile`, `backend/entrypoint.sh`, `frontend/Dockerfile`, `.github/workflows/cicd.yml`, `.env.example`, `frontend/.env.example`, `backend/database.py`

## Local Development Quick Start

```bash
# 1. Copy environment files
cp .env.example .env
cp frontend/.env.example frontend/.env

# 2. Build and launch all services
docker compose up --build
```

After startup:

| Service | URL | Notes |
|---------|-----|-------|
| Frontend (SvelteKit) | `http://localhost:3000` | Dev server via `@sveltejs/adapter-node` |
| Backend (FastAPI) | `http://localhost:8000` | API root; OpenAPI docs at `/docs` |
| Postgres 18 | `db:5432` (internal) | No host port mapping — see rationale below |

### Database port visibility

The `db` service in `docker-compose.yml` deliberately omits a `ports:` directive. Docker's iptables rules bypass UFW and similar host firewalls, so even a guarded `5432:5432` would expose Postgres to the public internet. The database is reachable only on the internal bridge network (`app-network`).

---

## Docker Compose Breakdown

### Network: `app-network`

Single bridge network shared by all three services. No external connectivity required — inter-service communication uses service names as hostnames (e.g. `http://backend:8000`).

### Volume: `postgres_data`

Named Docker volume mounted at `/var/lib/postgresql` inside the `db` container. Survives container restarts; delete manually to reset the database.

### `db` (Postgres 18)

| Field | Value |
|-------|-------|
| Image | `postgres:18-alpine` |
| Env file | `.env` (root) |
| Ports | None — see security rationale above |
| Volume | `postgres_data:/var/lib/postgresql` |
| Network | `app-network` |
| Healthcheck | `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB` — interval 10s, timeout 5s, retries 5 |

### `backend` (FastAPI)

| Field | Value |
|-------|-------|
| Build | `./backend/Dockerfile` |
| Ports | `8000:8000` |
| Env file | `.env` (root) |
| Depends on | `db` condition: `service_healthy` |
| Network | `app-network` |
| Healthcheck | Python `urllib` GET `http://localhost:8000/` — interval 10s, timeout 5s, retries 5, start_period 5s |

### `frontend` (SvelteKit)

| Field | Value |
|-------|-------|
| Build | `./frontend/Dockerfile` |
| Ports | `3000:3000` |
| Env file | `frontend/.env` |
| Environment | `BACKEND_INTERNAL_URL=http://backend:8000`, `ORIGIN` (default `http://localhost:3000`) |
| Depends on | `backend` condition: `service_healthy` |
| Network | `app-network` |

**`BACKEND_INTERNAL_URL`** — used by SvelteKit server-side `load` functions and form actions for in-cluster calls to the FastAPI backend. Browser-side code uses `PUBLIC_BACKEND_URL` / `PUBLIC_WS_URL` from the frontend `.env`.

**`ORIGIN`** — required by `@sveltejs/adapter-node` for its CSRF check. The value must match the URL the browser navigates to. Defaults to `http://localhost:3000` for local development; override in the production `.env`.

---

## Container Startup

### Backend multi-stage Dockerfile

```
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim
```

Two-stage `uv sync`:

1. **Dependencies only** — mounts `uv.lock` and `pyproject.toml` from build context, runs `uv sync --frozen --no-install-project --no-dev`. Layers cached so source edits don't re-resolve.
2. **Project install** — copies full source, runs `uv sync --frozen --no-dev`.

Environment: `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`, `PATH` includes `/app/.venv/bin`.

The `ENTRYPOINT` is reset to empty (the base image's `uv` entrypoint is discarded). Non-root user `nonroot` (uid/gid 999) is created at build time.

```
CMD ["/app/entrypoint.sh"]
```

### Backend entrypoint (`entrypoint.sh`)

```sh
#!/bin/sh
set -e

for i in $(seq 1 30); do
  python - <<'PY' && break
import socket, sys
try:
    socket.getaddrinfo("db", 5432)
    s = socket.create_connection(("db", 5432), timeout=2)
    s.close()
except Exception:
    sys.exit(1)
PY
  echo "DB not ready yet ($i/30)"
  sleep 2
done

alembic upgrade head
exec uvicorn main:app --host 0.0.0.0 --port 8000
```

Steps, in order:

1. **DB readiness loop** — up to 30 attempts (2 s apart) testing TCP connectivity to host `db` port `5432` via raw Python socket. Exits the loop early on success, fails hard after exhausting retries.
2. **`alembic upgrade head`** — applies all pending migrations to the connected database.
3. **`exec uvicorn main:app …`** — replaces the shell process with the ASGI server.

### Frontend multi-stage Dockerfile

```
FROM oven/bun:1-slim AS base
```

Three stages:

| Stage | Purpose |
|-------|---------|
| `base` | Sets `WORKDIR /usr/src/app` |
| `build` | Installs deps (`bun install --frozen-lockfile`), copies source, runs `bun run build` |
| `runtime` | Copies production deps and `build/` output, sets `NODE_ENV=production`, `HOST=0.0.0.0`, `PORT=3000` |

Runtime command:

```
CMD ["bun", "run", "build/index.js"]
```

No `.env` is baked into the image — runtime env vars are injected via `docker compose` `env_file` / `environment`.

---

## Docker-Aware DATABASE_URL

In `backend/database.py` (and replicated in `alembic/env.py`):

```python
if "@db:" in DATABASE_URL and not Path("/.dockerenv").exists():
    DATABASE_URL = DATABASE_URL.replace("@db:", "@localhost:")
```

When the backend detects it is NOT running inside a Docker container (no `/.dockerenv` file), it rewrites the `@db:` host component to `@localhost:`. This allows the same `.env` file to work for both Docker Compose (where `db` resolves via the bridge network) and local development (where Postgres runs on the host). See [configuration](../backend/configuration.md) for the full env var reference.

---

## CI/CD Pipeline

The single workflow `.github/workflows/cicd.yml` runs on push to `main` and pull requests targeting `main`.

### Jobs

| Job | Runner | Dependencies | Trigger Condition | Key Steps |
|-----|--------|--------------|-------------------|-----------|
| `backend-lint` | `ubuntu-latest` | — | push/PR to main | `uv` setup, `ruff check .`, `ruff format --check .` |
| `backend-test` | `ubuntu-latest` | — | push/PR to main | `uv` setup, `pytest --cov=... --cov-fail-under=80` with `DATABASE_URL=sqlite:///` and `JWT_SECRET=ci-test-secret-at-least-thirty-two-chars` |
| `backend-migrations` | `ubuntu-latest` | Postgres service container | push/PR to main | `uv` setup, `alembic upgrade head`, `alembic downgrade -1 && alembic upgrade head` (round-trip), `alembic check` (drift detection) |
| `frontend-lint` | `ubuntu-latest` | — | push/PR to main | `bun install --frozen-lockfile`, `bun run lint`, `bun x prettier --check .` |
| `frontend-test` | `ubuntu-latest` | — | push/PR to main | `bun install --frozen-lockfile`, `bun run test -- --coverage` |
| `build-test` | `ubuntu-latest` | — | push/PR to main | `docker compose build` (verifies images compile) |
| `deploy` | `ubuntu-latest` | All 5 preceding jobs | push to main ONLY | Tailscale connect, SSH into production, write `.env` from secrets/vars, `git pull`, `docker compose up --build -d` |

### Deployment details (auto-deploy on merge to main)

The `deploy` job runs only when all preceding jobs pass AND the trigger is a `push` event on `refs/heads/main`.

- Establishes a Tailscale connection using `${{ secrets.TS_AUTHKEY }}`.
- Connects to the production server via SSH (`appleboy/ssh-action@v1`) authenticated with `${{ secrets.SERVER_SSH_KEY }}`.
- Writes a fresh `.env` to `~/playlink/.env` using GitHub Actions `secrets` (sensitive values) and `vars` (non-sensitive defaults), plus a separate `frontend/.env` with `PUBLIC_WS_URL` and `PUBLIC_BACKEND_URL`.
- Runs `git pull origin main`, then `docker compose up --build -d` with `DOCKER_BUILDKIT=1`.

Typical deploy duration: 30 s – 5 min depending on image cache state and network latency.

### Environment variables injected at deploy time

**Root `.env`** (production):
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST=db`, `POSTGRES_PORT=5432`
- `DATABASE_URL=postgresql+psycopg://<user>:<password>@db:5432/<db>`
- `JWT_SECRET`, `JWT_ALGORITHM`
- `NONCE_EXPIRATION_MINUTES`, `JWT_EXPIRATION_MINUTES`
- `ORIGIN=https://playlink.bartek.monster`
- `ADMIN_ADDRESSES`

**Frontend `.env`** (production):
- `PUBLIC_WS_URL=wss://<backend-domain>`
- `PUBLIC_BACKEND_URL=https://<backend-domain>`

---

## Related Documentation

- [Configuration](../backend/configuration.md) — all backend env var definitions and validation
- [Testing](../operations/testing.md) — local test suite reference
- [Migrations](../backend/migrations.md) — Alembic chain and migration workflow
- [Architecture](../architecture.md) — system context and component relationships
- [Index](../index.md) — full documentation map
