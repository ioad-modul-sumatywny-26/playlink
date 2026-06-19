# Playlink Documentation

Playlink is a full-stack **LFG (Looking-For-Group)** web application for finding players for niche, retro, and less popular multiplayer titles. Users create short-lived game sessions ("rooms") and browse open lobbies in real time. Identity is non-custodial: it is derived locally from a BIP39 mnemonic and proven to the backend with an ECDSA signature.

This is the developer documentation set. Start with the [architecture overview](architecture.md), then drill into the area you need.

## Map

### Overview
| Document | Contents |
| -------- | -------- |
| [Architecture](architecture.md) | System topology, tech stack, domain concepts, core flows, security model. |

### Backend (FastAPI)
| Document | Contents |
| -------- | -------- |
| [API reference](backend/api-reference.md) | Every REST endpoint: auth, request/response shapes, status codes, side effects. |
| [Realtime reference](backend/realtime.md) | The `/ws/rooms` and `/ws/rooms/{name}/chat` WebSocket protocols and frame catalog. |
| [Data model](backend/data-model.md) | SQLModel tables, fields, relationships, constraints, and the entity diagram. |
| [Migrations](backend/migrations.md) | Alembic wiring, operator commands, and the ordered migration history. |
| [Configuration](backend/configuration.md) | Environment variables, admin model, rate limiting, CORS, username validation. |

### Frontend (SvelteKit)
| Document | Contents |
| -------- | -------- |
| [Library & stores](frontend/library.md) | Client logic: identity/signing, realtime stores, contexts, server hooks. |
| [Routes](frontend/routes.md) | Pages, server `load` functions, form actions, and the BFF auth model. |
| [Components](frontend/components.md) | Domain components and the Diablo-II-themed chrome UI kit (prop tables). |

### Operations
| Document | Contents |
| -------- | -------- |
| [Testing](operations/testing.md) | Backend pytest and frontend vitest suites, fixtures, and run commands. |
| [Deployment](operations/deployment.md) | Docker Compose services, Dockerfiles, container startup, and CI/CD. |

## Quick Start

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
docker compose up --build
```

Services:

- Frontend — `http://localhost:3000`
- Backend (OpenAPI docs at `/docs`) — `http://localhost:8000`
- PostgreSQL — internal to the Docker network (no host port mapping by design)

See [deployment](operations/deployment.md) for the full local and production setup, and the component READMEs (`backend/README.md`, `frontend/README.md`) for service-specific developer setup.

## Conventions in these docs

- Each document opens with a one-paragraph purpose and a `> **Source:**` line naming the files it covers.
- Endpoints, environment variables, model fields, component props, and WebSocket frames are documented as tables sourced directly from the code.
- Cross-references between documents use relative links; follow them to avoid duplication.
