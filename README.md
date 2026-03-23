# Playlink - Moduł Sumatywny

Playlink is a full-stack application providing secure, non-custodial identity management. The system is built with a FastAPI backend, a SvelteKit frontend, and a PostgreSQL database, orchestrated via Docker Compose.

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.14+ (for local development)
- Bun 1.1+ (for local development)

### Configuration

1. Initialize the environment configuration:
   ```bash
   cp .env.example .env
   ```
2. Define a secure `JWT_SECRET` in the `.env` file (minimum 32 characters).
3. Optionally, create `frontend/.env` from `frontend/.env.example` to override frontend environment variables (required for local frontend development outside Docker; optional for Docker Compose, which uses the defaults from `frontend/.env.example`):
   ```bash
   cp frontend/.env.example frontend/.env
   ```

### Containerized Deployment

To build and deploy the entire stack using Docker Compose:

```bash
docker compose up --build
```

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs
- **Project Kanban:** [GitHub Project Board](https://github.com/orgs/ioad-modul-sumatywny-26/projects/2)

## Technical Architecture

| Component | Technology | Management |
|-----------|------------|------------|
| Frontend | SvelteKit (TypeScript) | Bun |
| Backend | FastAPI (Python) | uv |
| Database | PostgreSQL 18 | Docker |
| ORM | SQLModel | — |
| Authentication | BIP39 Identity / ECDSA | ethers.js |
| Git Hooks | prek | uv |

### Identity Authentication Flow

The application utilizes a non-custodial challenge-response mechanism based on BIP39 and ECDSA signatures:

1. **Local Derivation:** The client derives a cryptographic identity from a 12-word mnemonic phrase locally; the private key never leaves the client environment.
2. **Challenge Generation:** The backend issues a unique, one-time random nonce (challenge).
3. **Cryptographic Proof:** The client signs the challenge using the derived private key.
4. **Session Verification:** The backend verifies the signature against the nonce and issues a JSON Web Token (JWT).

Detailed specifications are available in `backend/docs/auth-flow.md`.

## Local Development Workflow

For optimal development speed and debugging capabilities, a hybrid workflow is recommended:

### 1. Database Service
Run the persistent storage layer in the background:
```bash
docker compose up -d db
```

### 2. Backend Service
Run the FastAPI application with hot-reloading:
```bash
cd backend
uv sync
uv run uvicorn main:app --reload
```

### 3. Frontend Service
Run the SvelteKit application in development mode:
```bash
cd frontend
bun install
bun dev
```

### 4. Testing
Execute the backend test suite:
```bash
cd backend
uv run pytest
```

Run all code quality hooks manually:
```bash
prek run --all-files
```

## Project Organization
- `backend/`: API services, database models, and authentication logic.
- `frontend/`: SvelteKit application and identity management UI.
- `prezentacje/`: Project documentation and presentation materials.
- `docker-compose.yml`: Multi-container orchestration configuration.
