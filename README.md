# Playlink — Moduł Sumatywny

Playlink is a full-stack **LFG (Looking For Group)** web application for finding players for niche, retro, and less popular multiplayer titles. Users create short-lived game sessions ("rooms") and browse open lobbies in real time. Authentication is non-custodial: identity is derived locally from a BIP39 mnemonic and verified against the backend with an ECDSA signature.

The system is built with a FastAPI backend, a SvelteKit frontend, and a PostgreSQL database, orchestrated via Docker Compose.

**Project Kanban:** [GitHub Project Board](https://github.com/orgs/ioad-modul-sumatywny-26/projects/2)

## Access

Frontend and backend are available at:

- [Frontend](https://playlink.bartek.monster/)
- [Backend documentation](https://playlink-backend.bartek.monster/docs)

## Deployment

Changes merged into the `main` branch are automatically deployed. The deployment process typically takes between 30 seconds and 5 minutes to complete, depending on the scope and complexity of the changes.

## Features

- **Identity authentication** — BIP39 mnemonic + ECDSA signature challenge, JWT session.
- **Rooms** — create, list, join, and leave game sessions through REST endpoints.
- **Realtime room list** — WebSocket broadcast pushes the current room list to all connected clients on every change.
- **Game catalog** — pre-seeded list of supported games (Quake III Arena, Diablo II, StarCraft, Half-Life, Unreal Tournament).

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
| Git Hooks      | prek                   | uv         |

### Identity Authentication Flow

The application utilizes a non-custodial challenge-response mechanism based on BIP39 and ECDSA signatures:

1. **Local Derivation:** The client derives a cryptographic identity from a 12-word mnemonic phrase locally; the private key never leaves the client environment.
2. **Challenge Generation:** The backend issues a unique, one-time random nonce (challenge).
3. **Cryptographic Proof:** The client signs the challenge using the derived private key.
4. **Session Verification:** The backend verifies the signature against the nonce and issues a JSON Web Token (JWT).

Detailed specifications are available in [`backend/docs/auth-flow.md`](backend/docs/auth-flow.md).

## Local Development

The fastest way to run the full stack locally:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
docker compose up --build
```

Services:

- Frontend — `http://localhost:3000`
- Backend (OpenAPI docs at `/docs`) — `http://localhost:8000`
- PostgreSQL — internal to Docker network (`app-network`)

For running each service outside Docker, see [`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md).

## All-in-One Appliance Container

In addition to Docker Compose, Playlink can be run as a self-contained, unified single container (`Dockerfile.allinone`) housing PostgreSQL, the FastAPI backend, SvelteKit frontend, and a Cloudflare Tunnel connector managed by Supervisord.

Use the launcher script [`run-playlink.sh`](run-playlink.sh):

```bash
# Make script executable (if needed)
chmod +x run-playlink.sh

# Run locally with exposed ports:
./run-playlink.sh --build --expose-ports

# Run with Cloudflare Zero Trust tunnel:
./run-playlink.sh -t "<CLOUDFLARE_TUNNEL_TOKEN>" -o "https://playlink.bartek.monster" -b "playlink-backend.bartek.monster"

# Common lifecycle commands:
./run-playlink.sh --logs      # Follow container logs
./run-playlink.sh --restart   # Restart appliance container
./run-playlink.sh --stop      # Stop and remove container
```

For detailed configuration flags and production multi-server architecture recommendations, see [`docs/operations/deployment.md`](docs/operations/deployment.md).

## Project Organization

- `backend/` — FastAPI service, SQLModel schemas, Alembic migrations, authentication and rooms logic.
- `frontend/` — SvelteKit application and identity management UI.
- `docker/allinone/` — Process startup scripts and Supervisord configuration for the unified container.
- `Dockerfile.allinone` — Unified multi-stage container build definition.
- `run-playlink.sh` — Parameterized launcher and lifecycle management script.
- `prezentacje/` — Project documentation and presentation materials.
- `docker-compose.yml` — Multi-container orchestration configuration.
- `CONTRIBUTING.md` — Workflow, branching, and quality standards.
