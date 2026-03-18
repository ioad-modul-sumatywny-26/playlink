# Backend — FastAPI

FastAPI-based backend for the Playlink project.

## Requirements

- **Python 3.14+**
- **uv** (Package manager)
- **Docker** (Optional, for containerized deployment)
- Windows, macOS, or Linux

## Technologies Used

- **FastAPI** `0.135.1`
- **Uvicorn** `0.41.0`
- **uv** `0.10.x`

## Getting Started

### 1. Installation

Using `uv`:

```bash
uv sync
```

### 2. Running the Server

#### Using `uv` directly:

```bash
uv run uvicorn main:app --reload
```

#### Using Docker:

```bash
docker build -t backend-playlink .
docker run -p 8000:8000 backend-playlink
```

The API will be available at `http://127.0.0.1:8000`

### 3. API Documentation

Once the server is running, you can access:

- **Interactive API docs (Swagger UI)**: http://127.0.0.1:8000/docs
- **Alternative API docs (ReDoc)**: http://127.0.0.1:8000/redoc

## Available Endpoints

- `GET /` - Hello World endpoint
- `GET /items/{item_id}` - Get item by ID with optional query parameter

## Project Structure

```
backend/
├── main.py           # FastAPI application entry point
├── pyproject.toml    # uv project configuration and dependencies
├── uv.lock           # uv lockfile for deterministic builds
├── Dockerfile        # Container configuration
└── README.md         # This file
```
