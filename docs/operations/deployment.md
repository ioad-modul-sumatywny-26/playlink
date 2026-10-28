# Deployment & Operations

Reference for local development, Docker infrastructure, container startup, and the CI/release pipeline for the Playlink project.

> **Source:** `compose.yaml`, `compose.build.yaml`, `compose.ports.yaml`, `backend/Dockerfile`, `backend/entrypoint.sh`, `frontend/Dockerfile`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `deploy/`, `.env.example`, `frontend/.env.example`, `backend/database.py`

## Local Development Quick Start

```bash
# EU stack, built from the working tree (local mode)
deploy/deploy.sh eu

# optional: US stack next to it
deploy/deploy.sh us
```

Without `PLAYLINK_DOMAIN` in `deploy/site.env` the script runs in local mode: dev secrets, ports published on `127.0.0.1`, no tunnel. After startup:

| Service | URL | Notes |
|---------|-----|-------|
| Chooser | `http://127.0.0.1:3000` | Entry host in local mode (served by the EU stack) |
| Frontend EU / US (SvelteKit) | `http://localhost:3000` / `http://localhost:3001` | `@sveltejs/adapter-node` build |
| Backend EU / US (FastAPI) | `http://localhost:8000` / `http://localhost:8001` | OpenAPI docs at `/docs`; probes at `/healthz` and `/readyz` |
| Postgres 18 | `db:5432` (internal) | No host port mapping — see rationale below |

### `deploy/deploy.sh <eu|us> [tag]`

| Step | Behaviour |
|------|-----------|
| Config | Loads `deploy/config.env` (shared, non-secret) then `deploy/site.env` (gitignored; see `site.env.example`) |
| Mode | No `PLAYLINK_DOMAIN`: local mode (`compose.ports.yaml`). With `PLAYLINK_DOMAIN` + `TUNNEL_TOKEN_<REGION>`: public via Cloudflare Tunnel, no published ports. `JWT_SECRET` and `POSTGRES_PASSWORD` are then required |
| Env file | Generates `.run/<region>.env` (mode 0600): shared settings, `PUBLIC_*` URLs, `CORS_ORIGINS`, secrets. The tunnel token goes only to `cloudflared` |
| Images | No tag: builds from the working tree (`compose.build.yaml`). With a tag: pulls `ghcr.io` images (logs in when `GHCR_TOKEN` is set) |
| Start | `docker compose -p playlink-<region> up -d --wait`; project names `playlink-eu` / `playlink-us` let both regions share one machine |
| Rollback | On failed health, redeploys the previous tag from `.run/<region>.tag` and exits non-zero |

### Database port visibility

The `db` service in `compose.yaml` deliberately omits a `ports:` directive. Docker's iptables rules bypass UFW and similar host firewalls, so even a guarded `5432:5432` would expose Postgres to the public internet. The database is reachable only on the project's internal compose network.

---

## Docker Compose Breakdown

`compose.yaml` describes one regional stack. Extra files are added by `deploy.sh`:

| File | Added when | Effect |
|------|------------|--------|
| `compose.build.yaml` | no tag | Builds `backend` and `frontend` from `./backend` and `./frontend` |
| `compose.ports.yaml` | no `PLAYLINK_DOMAIN` | Publishes `127.0.0.1:${BACKEND_PORT}:8000` and `127.0.0.1:${FRONTEND_PORT}:3000` |

All services read the env file named by `APP_ENV_FILE` (`.run/<region>.env`). Service addressing uses compose service names on the project's default network (e.g. `http://backend:8000`); there are no static container IPs.

### Volume: `postgres_data`

Named Docker volume mounted at `/var/lib/postgresql` inside the `db` container. Survives container restarts; delete manually to reset the database.

### `db` (Postgres 18)

| Field | Value |
|-------|-------|
| Image | `postgres:18-alpine` |
| Ports | None — see security rationale above |
| Volume | `postgres_data:/var/lib/postgresql` |
| Limits | `mem_limit: 320m`, tuned `shared_buffers` / `max_connections` |
| Healthcheck | `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB` — interval 10s, timeout 5s, retries 10, start_period 20s |

### `backend` (FastAPI)

| Field | Value |
|-------|-------|
| Image | `ghcr.io/ioad-modul-sumatywny-26/playlink-backend:${IMAGE_TAG:-local}` |
| Ports | Only in local mode: `127.0.0.1:${BACKEND_PORT}:8000` |
| Depends on | `db` condition: `service_healthy` |
| Limits | `mem_limit: 320m` |
| Healthcheck | Python `urllib` GET `http://127.0.0.1:8000/readyz` — interval 10s, timeout 5s, retries 10, start_period 30s |

### `frontend` (SvelteKit)

| Field | Value |
|-------|-------|
| Image | `ghcr.io/ioad-modul-sumatywny-26/playlink-frontend:${IMAGE_TAG:-local}` |
| Ports | Only in local mode: `127.0.0.1:${FRONTEND_PORT}:3000` |
| Environment | `BACKEND_INTERNAL_URL=http://backend:8000`, `PROTOCOL_HEADER=x-forwarded-proto`; the host comes from the original `Host` header |
| Depends on | `backend` condition: `service_healthy` |
| Limits | `mem_limit: 256m` |
| Healthcheck | `bun -e "fetch('http://127.0.0.1:3000/healthz')"` — interval 10s, timeout 5s, retries 10 |

**`BACKEND_INTERNAL_URL`** — used by SvelteKit server-side `load` functions and form actions for in-cluster calls to the FastAPI backend. Browser-side code uses `PUBLIC_BACKEND_URL` / `PUBLIC_WS_URL`.

**Do not set `ORIGIN`** on a frontend container that serves both the entry host and a regional hostname. `@sveltejs/adapter-node` takes the scheme from `X-Forwarded-Proto` and the host from the original `Host` header (which cloudflared preserves); a fixed `ORIGIN` would make `playlink.<domain>` and `playlink-eu.<domain>` indistinguishable. Plain-http localhost has no proxy header, so `frontend/svelte.config.js` lists `http://localhost:3000` and `http://localhost:3001` as CSRF trusted origins.

### `cloudflared` (Cloudflare Tunnel)

| Field | Value |
|-------|-------|
| Image | `cloudflare/cloudflared:2025.10.0` |
| Command | `tunnel --no-autoupdate run` |
| Environment | `TUNNEL_TOKEN` (`TUNNEL_TOKEN_<REGION>` from `site.env`) — never on the command line |
| Profile | `tunnel` — enabled by `deploy.sh` when a token is set; skipped in local mode |
| Depends on | `frontend` healthy |
| Routes | Configured in the tunnel on Cloudflare: frontend hosts -> `http://frontend:3000`, API hosts -> `http://backend:8000` |

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

## CI/Release Pipeline

Releases are tag-based and pull-based. Full operating instructions live in [runbook-regions.md](runbook-regions.md).

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| `ci.yml` | PR / push to `main`, or called by Release | Lint, tests, Alembic round-trip/drift check, Compose validation, shellcheck of `deploy/*.sh`, no-push image build |
| `release.yml` | `vX.Y.Z` tag | Run CI, build and push backend/frontend images to GHCR, create the GitHub Release |

There are no deploy workflows. Each region VM runs a systemd timer (every 2 minutes, installed by `deploy/cloud-init.yaml`) that executes `deploy/update.sh <region>`:

1. Resolves the latest GitHub Release, or `PLAYLINK_TAG` from `site.env` if set.
2. Skips if that tag is already running or previously failed (`.run/<region>.tag`, `.run/<region>.failed`).
3. US only: waits until EU's `/healthz` reports the same version, so a broken release stops at EU.
4. Checks out the tag and runs `deploy/deploy.sh <region> <tag>`, which pulls the images and rolls back on failed health.

The VMs never build images. No GitHub secrets are needed for deploys; GHCR packages must be public, or `GHCR_USER` / `GHCR_TOKEN` set in `site.env`. Rollback is a tag change, not a rebuild.

Region VMs are created with `deploy/azure-vm.sh` (no inbound ports; see the runbook).

---

## Related Documentation

- [Configuration](../backend/configuration.md) — all backend env var definitions and validation
- [Testing](../operations/testing.md) — local test suite reference
- [Migrations](../backend/migrations.md) — Alembic chain and migration workflow
- [Architecture](../architecture.md) — system context and component relationships
- [Index](../index.md) — full documentation map
