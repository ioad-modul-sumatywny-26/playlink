# Playlink — Moduł Sumatywny / Projekt Kompetencyjny

Playlink is a full-stack **LFG (Looking For Group)** web application for finding players for niche, retro, and less popular multiplayer titles. Users create short-lived game sessions ("rooms") and browse open lobbies in real time. Authentication is non-custodial: identity is derived locally from a BIP39 mnemonic and verified against the backend with an ECDSA signature.

The system is built with a FastAPI backend, a SvelteKit frontend, and a PostgreSQL database, orchestrated via Docker Compose. It runs as two independent regional stacks (EU and US) behind Cloudflare Tunnel.

**Project Kanban:** [GitHub Project Board](https://github.com/orgs/ioad-modul-sumatywny-26/projects/2)

## Table of Contents

- [Access](#access)
- [Releases and Deployment](#releases-and-deployment)
- [Features](#features)
- [Technical Architecture](#technical-architecture)
  - [Identity Authentication Flow](#identity-authentication-flow)
- [Local Development](#local-development)
- [Model Context Protocol (MCP)](#model-context-protocol-mcp)
  - [Testing via npx](#testing-via-npx)
  - [Assistant Configuration](#assistant-configuration)
- [Project Organization](#project-organization)

## Access

Public hostnames are derived from the configured `PLAYLINK_DOMAIN` (`<domain>`):

| Purpose | URL |
| --- | --- |
| Region chooser | `https://playlink.<domain>` |
| EU frontend | `https://playlink-eu.<domain>` |
| EU API | `https://playlink-eu-api.<domain>` |
| US frontend | `https://playlink-us.<domain>` |
| US API | `https://playlink-us-api.<domain>` |
| Grafana (logs and metrics of all regions) | `https://playlink-grafana.<domain>` (Cloudflare Access login) |
| Logs / metrics endpoints (for MCP) | `https://playlink-logs.<domain>`, `https://playlink-metrics.<domain>` (basic auth, `OBS_PASSWORD`) |

Without a domain the stack runs in local mode: EU on `http://localhost:3000` (API `:8000`), US on `http://localhost:3001` (API `:8001`), chooser at `http://127.0.0.1:3000`. Logs and metrics locally: `bash deploy/observability.sh up`, Grafana at `http://127.0.0.1:3300` (user `admin`, password `OBS_PASSWORD` from `deploy/site.env`), see [`docs/operations/observability.md`](docs/operations/observability.md).

The entry host measures both regions and redirects to the faster live one. Each region has its own session: switching regions requires signing in again with the same 12 words. Rooms are regional — a room created in EU does not exist in US.

## Releases and Deployment

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

Pre-release tags (`vX.Y.Z-rc.N`) are deployed only when pinned with `PLAYLINK_TAG`. Start, stop and inspect the VMs with `deploy/azure.sh`. The full runbook (current deployment, local and public mode, Cloudflare hostnames, Azure VMs, rollback, failure drills) is in [`docs/operations/runbook-regions.md`](docs/operations/runbook-regions.md). Logs and metrics of all regions in one Grafana: [`docs/operations/observability.md`](docs/operations/observability.md).

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

## Model Context Protocol (MCP)

PlayLink includes an MCP server (`backend/mcp_server`) that allows AI assistants (Claude Desktop, Claude Code, Cursor, Antigravity) to safely inspect platform status, retro games, active LFG lobbies, and regional health in read-only mode.

The MCP server always runs on your own machine (Windows, macOS or Linux) and only talks to a PlayLink API over HTTP. What differs is where that API runs:

| Case | API | You need |
| --- | --- | --- |
| [Local](#case-1-playlink-running-locally) | `localhost:8000` (EU) and `localhost:8001` (US) from `deploy/deploy.sh` | Docker |
| [Remote](#case-2-playlink-running-remotely-production) | Deployed regions, e.g. on Azure | The domain, optionally the logs password |

### 1. Install the tools

You need [Git](https://git-scm.com) and [uv](https://docs.astral.sh/uv/) (Python package manager; it installs the right Python itself).

| | Git | uv |
| --- | --- | --- |
| **Windows** (PowerShell) | `winget install Git.Git` | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| **macOS** (Terminal) | `xcode-select --install` or `brew install git` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` or `brew install uv` |
| **Linux** (shell) | `sudo apt install git` (Debian/Ubuntu), `sudo dnf install git` (Fedora) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

Open a new terminal afterwards and check `git --version` and `uv --version`.

### 2. Get the code

```bash
git clone https://github.com/ioad-modul-sumatywny-26/playlink.git
cd playlink/backend
uv sync
pwd          # Windows PowerShell: (Get-Location).Path
```

Keep the printed path: it is the absolute path to `backend` used below. Typical values:

| OS | Example |
| --- | --- |
| Windows | `C:/Users/you/playlink/backend` (forward slashes work in JSON; with backslashes double them: `C:\Users\you\...`) |
| macOS | `/Users/you/playlink/backend` |
| Linux | `/home/you/playlink/backend` |

### 3. Add the server to your assistant

Pick your assistant. The JSON entries are the same on every system; only the file location and the path to `backend` differ. The `env` block is what changes between the two cases below.

| Assistant | Where to add it |
| --- | --- |
| **Claude Code** | One command (see the cases below), same on all systems |
| **Claude Desktop** | Settings → Developer → Edit Config. Windows: `%APPDATA%\Claude\claude_desktop_config.json`; macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`. No official Linux app: use Claude Code or Cursor |
| **Cursor** | Settings → MCP, or `~/.cursor/mcp.json` (Windows: `%USERPROFILE%\.cursor\mcp.json`) |
| **Antigravity / Gemini** | `~/.gemini/config/mcp_config.json` |

Restart Claude Desktop and Cursor fully after saving. If the app cannot find `uv` (common for macOS/Linux desktop apps, which do not read your shell profile), put the absolute path in `"command"`: `which uv` (macOS/Linux) or `where uv` (Windows), e.g. `/Users/you/.local/bin/uv`.

### Case 1: PlayLink running locally

Start the regions first (`deploy/deploy.sh eu`, optionally `deploy/deploy.sh us`). Without any configuration the server uses `http://localhost:8000` (EU) and `http://localhost:8001` (US), so the entry needs no `env`:

```json
{
  "mcpServers": {
    "playlink": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/playlink/backend", "python", "-m", "mcp_server"]
    }
  }
}
```

Claude Code:

```bash
claude mcp add playlink -- uv run --directory /path/to/playlink/backend python -m mcp_server
```

To try the tools without an assistant, run the inspector from the repository root (Windows: PowerShell, same commands):

```bash
npx @modelcontextprotocol/inspector uv run --directory backend python -m mcp_server
npx @modelcontextprotocol/inspector --cli --method tools/list uv run --directory backend python -m mcp_server   # no browser UI
```

The log and metrics tools (`search_logs`, `query_metrics`) work locally only if you also run the [observability stack](docs/operations/observability.md); otherwise they answer that they are not configured.

### Case 2: PlayLink running remotely (production)

No access to the servers is needed. Point the MCP server at the deployed regions with `PLAYLINK_DOMAIN`; it derives `https://playlink-<region>-api.<domain>` for every region in `PLAYLINK_REGIONS`:

```json
{
  "mcpServers": {
    "playlink": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/playlink/backend", "python", "-m", "mcp_server"],
      "env": {
        "PLAYLINK_DOMAIN": "<domain>",
        "PLAYLINK_REGIONS": "eu,us"
      }
    }
  }
}
```

Claude Code (Windows PowerShell, macOS and Linux alike):

```bash
claude mcp add playlink -e PLAYLINK_DOMAIN=<domain> -e PLAYLINK_REGIONS=eu,us -- uv run --directory /path/to/playlink/backend python -m mcp_server
```

For `search_logs` and `query_metrics` add the following to `env` (see [logs and metrics](docs/operations/observability.md#ask-the-logs-through-mcp)); with Claude Code add one more `-e NAME=value` per variable. The password is the `OBS_PASSWORD` of the deployment: ask the maintainer and never commit it.

```json
"PLAYLINK_LOGS_URL": "https://playlink-logs.<domain>",
"PLAYLINK_METRICS_URL": "https://playlink-metrics.<domain>",
"PLAYLINK_OBS_USER": "playlink",
"PLAYLINK_OBS_PASSWORD": "<OBS_PASSWORD>"
```

### Checking the connection

Restart the assistant and ask it to run `check_platform_health`. Every configured region should report `reachable`.

| Symptom | Likely cause |
| --- | --- |
| No PlayLink tools in the assistant | Wrong absolute path in `--directory`, `uv` not found (use its full path), or the app was not restarted fully |
| Local: regions unreachable | Containers not running (`docker compose ls`) |
| Remote: regions unreachable | The VMs are stopped, or `PLAYLINK_DOMAIN` is wrong |
| `search_logs` says "not configured" | The four `PLAYLINK_*` log variables are missing from `env` |

## Project Organization

- `backend/` — FastAPI service, SQLModel schemas, Alembic migrations, authentication, rooms logic, and `mcp_server`.
- `frontend/` — SvelteKit application, identity management UI, and the region chooser.
- `deploy/` — `deploy.sh` (deploy a region), `update.sh` (pull-based rollout), `azure-vm.sh` and `cloud-init.yaml` (region VMs), `config.env` (shared settings), `site.env.example`.
- `compose.yaml` — one regional stack (no host-exposed ports by default).
- `compose.build.yaml` — builds images from the working tree.
- `compose.ports.yaml` — publishes ports on localhost (local mode).
- `docs/` — System documentation, data models, realtime protocols, and runbooks.
- `prezentacje/` — Project documentation and presentation materials.
- `CONTRIBUTING.md` — Workflow, branching, and quality standards.
