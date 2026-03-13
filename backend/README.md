# Backend — FastAPI

FastAPI-based backend for the Playlink project.

## Requirements

- **Python 3.13+**
- **pip**
- Windows, macOS, or Linux

## Technologies Used

- **FastAPI** `0.135.1`
- **Uvicorn** `0.41.0`

## Getting Started

### 1. Installation

Install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Running the Server

Start the development server:

```bash
uvicorn main:app --reload
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