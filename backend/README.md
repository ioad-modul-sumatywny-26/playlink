# Playlink Backend (FastAPI)

FastAPI application handling identity authentication and room/session management.

## Tech Stack
- **Framework:** FastAPI
- **ORM:** SQLModel (SQLAlchemy + Pydantic)
- **Database:** PostgreSQL (Production/Docker) / SQLite (Testing)
- **Auth:** Identity Address (BIP39-compatible signatures) + JWT
- **Package Manager:** `uv`

## Core Authentication Flow
The backend implements a challenge-response authentication mechanism:
1. **Request Challenge:** Client sends their `identity_address` to `/auth/request-nonce`.
2. **Local Signing:** Client signs a message containing the nonce using their private key.
3. **Verification:** Client sends the signature back to `/auth/verify`.
4. **JWT Issuance:** If valid, the backend issues a JWT for secure sessions.

## Project Structure
- `main.py`: API endpoints and application lifecycle.
- `models.py`: SQLModel database schemas.
- `database.py`: Database engine and session management.
- `tests/`: Pytest suite.

## Development Setup

### 1. Prerequisites
- Install `uv`: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Python 3.14+

### 2. Environment Configuration
Create a `.env` file in the project root:
```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/playlink
JWT_SECRET=your-secure-secret-here
```

### 3. Install Dependencies
```bash
uv sync
```

### 4. Running the API
```bash
uv run uvicorn backend.main:app --reload
```

## Running Tests
Tests use an in-memory SQLite database and do not require PostgreSQL to be running.
```bash
uv run pytest
```

## Docker
The backend is designed to run via Docker Compose in the project root:
```bash
docker compose up --build backend
```
