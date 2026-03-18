# Playlink - Fullstack Application

This project consists of a FastAPI backend and a SvelteKit frontend, both fully containerized.

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)

### Running the entire stack

To build and start both the backend and frontend:

```bash
docker compose up --build
```

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Individual Services

### Backend (Python/FastAPI)

Managed with `uv`. 
- **Location**: `/backend`
- **Port**: 8000

### Frontend (SvelteKit)

Managed with `bun`.
- **Location**: `/frontend`
- **Port**: 3000

## Development

See individual READMEs in `backend/` and `frontend/` for local development setup without Docker.
