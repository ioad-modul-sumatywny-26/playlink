# Playlink — Moduł Sumatywny

Playlink is a full-stack **LFG (Looking For Group)** web application for finding players for niche, retro, and less popular multiplayer titles. Users create short-lived game sessions ("rooms") and browse open lobbies in real time. Authentication is non-custodial: identity is derived locally from a BIP39 mnemonic and verified against the backend with an ECDSA signature.

The system is built with a FastAPI backend, a SvelteKit frontend, and a PostgreSQL database, orchestrated via Docker Compose. It runs as two independent regional stacks (EU and US) behind Cloudflare Tunnel.

**Project Kanban:** [GitHub Project Board](https://github.com/orgs/ioad-modul-sumatywny-26/projects/2)

## Access

Public hostnames are derived from the configured `PLAYLINK_DOMAIN` (`<domain>`):

| Purpose | URL |
| --- | --- |
| Region chooser | `https://playlink.<domain>` |
| EU frontend | `https://playlink-eu.<domain>` |
| EU API | `https://playlink-eu-api.<domain>` |
| US frontend | `https://playlink-us.<domain>` |
| US API | `https://playlink-us-api.<domain>` |

Without a domain the stack runs in local mode: EU on `http://localhost:3000` (API `:8000`), US on `http://localhost:3001` (API `:8001`), chooser at `http://127.0.0.1:3000`.

The entry host measures both regions and redirects to the faster live one. Each region has its own session: switching regions requires signing in again with the same 12 words. Rooms are regional — a room created in EU does not exist in US.

## Releases and deployment

Deployments use versioned container images; the VMs never build code. Everything is started by one command, `deploy/deploy.sh <eu|us> [tag]`.

1. Run the stack locally and pass the tests (commands below).
2. Tag a tested commit:
   ```bash
   git tag -a v0.1.0 -m "multi-region deploy"
   git push origin v0.1.0
   ```
3. The `Release` workflow runs CI, builds the backend and frontend images, pushes them to GHCR, and creates a GitHub Release.
4. Region VMs are pull-based: a systemd timer (every 2 minutes) runs `deploy/update.sh`, which deploys the latest release. US waits until EU reports that version, so a failing release stops at EU. A failed health check rolls back to the previous tag. No GitHub secrets are needed.

Published images:

- `ghcr.io/ioad-modul-sumatywny-26/playlink-backend:vX.Y.Z`
- `ghcr.io/ioad-modul-sumatywny-26/playlink-frontend:vX.Y.Z`

Pre-release tags (`vX.Y.Z-rc.N`) are deployed only when pinned with `PLAYLINK_TAG`. Start, stop and inspect the VMs with `deploy/azure.sh`. The full runbook (current deployment, local and public mode, Cloudflare hostnames, Azure VMs, rollback, failure drills) (local and public mode, Cloudflare hostnames, Azure VMs, rollback, failure drills) is in [`docs/operations/runbook-regions.md`](docs/operations/runbook-regions.md).

## Features

- **Identity authentication** — BIP39 mnemonic + ECDSA signature challenge, JWT session.
- **Rooms** — create, list, join, and leave game sessions through REST endpoints.
- **Realtime room list** — WebSocket broadcast pushes the current room list to all connected clients on every change.
- **Game catalog** — pre-seeded list of supported games (Quake III Arena, Diablo II, StarCraft, Half-Life, Unreal Tournament).
- **Two regions** — independent EU/US stacks with a browser-side latency probe and a manual region switch.

## Technical Architecture

| Component      | Technology             | Management |
| -------------- | ---------------------- | ---------- |
| Frontend       | SvelteKit (TypeScript) | Bun        |
| Backend        | FastAPI (Python)       | uv         |
| Database       | PostgreSQL 18          | Docker     |
| ORM            | SQLModel               | —          |
| Migrations     | Alembic                | uv         |
| Realtime       | WebSockets (FastAPI)   | —          |
| Authentication | BIP39 Identity / ECDSA | ethers.js  |
| Ingress        | Cloudflare Tunnel      | cloudflared |
| Git Hooks      | prek                   | uv         |

### Identity Authentication Flow

The application utilizes a non-custodial challenge-response mechanism based on BIP39 and ECDSA signatures:

1. **Local Derivation:** The client derives a cryptographic identity from a 12-word mnemonic phrase locally; the private key never leaves the client environment.
2. **Challenge Generation:** The backend issues a unique, one-time random nonce (challenge).
3. **Cryptographic Proof:** The client signs the challenge using the derived private key.
4. **Session Verification:** The backend verifies the signature against the nonce and issues a JSON Web Token (JWT).

Detailed specifications are available in [`backend/docs/auth-flow.md`](backend/docs/auth-flow.md).

## Local Development

Without `PLAYLINK_DOMAIN` in `deploy/site.env`, `deploy/deploy.sh` runs in local mode: it builds images from the working tree, uses dev secrets, and publishes ports on localhost.

```bash
deploy/deploy.sh eu    # EU: frontend :3000, API :8000
deploy/deploy.sh us    # optional second region: frontend :3001, API :8001
```

- Chooser — `http://127.0.0.1:3000`
- EU app — `http://localhost:3000`; EU API (OpenAPI docs at `/docs`) — `http://localhost:8000`
- US app — `http://localhost:3001`; US API — `http://localhost:8001`
- PostgreSQL — internal to each region's compose network

The stacks are the compose projects `playlink-eu` and `playlink-us`; generated env files land in `.run/<region>.env`.

For running each service outside Docker, see [`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md).

## Project Organization

- `backend/` — FastAPI service, SQLModel schemas, Alembic migrations, authentication and rooms logic.
- `frontend/` — SvelteKit application, identity management UI, and the region chooser.
- `deploy/` — `deploy.sh` (deploy a region), `update.sh` (pull-based rollout), `azure-vm.sh` and `cloud-init.yaml` (region VMs), `config.env` (shared settings), `site.env.example`.
- `compose.yaml` — one regional stack (no host-exposed ports by default).
- `compose.build.yaml` — builds images from the working tree.
- `compose.ports.yaml` — publishes ports on localhost (local mode).
- `prezentacje/` — Project documentation and presentation materials.
- `CONTRIBUTING.md` — Workflow, branching, and quality standards.
