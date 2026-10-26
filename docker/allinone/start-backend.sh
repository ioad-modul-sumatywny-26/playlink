#!/bin/sh
set -e

echo "[backend] Preparing FastAPI service..."

export POSTGRES_USER="${POSTGRES_USER:-playlink}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-playlink}"
export POSTGRES_DB="${POSTGRES_DB:-playlink}"
export POSTGRES_HOST="127.0.0.1"
export POSTGRES_PORT="5432"

if [ -z "$DATABASE_URL" ]; then
    export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}"
fi

if [ -z "$JWT_SECRET" ]; then
    echo "[backend] WARNING: JWT_SECRET not set, using default development secret."
    export JWT_SECRET="default-development-jwt-secret-replace-in-production-min-32-chars"
fi

export PYTHONUNBUFFERED=1
export PATH="/app/.venv/bin:$PATH"

# Wait for local postgres to accept connections
echo "[backend] Waiting for PostgreSQL (127.0.0.1:5432)..."
for i in $(seq 1 30); do
    python3 - <<'PY' && break
import socket, sys
try:
    s = socket.create_connection(("127.0.0.1", 5432), timeout=2)
    s.close()
except Exception:
    sys.exit(1)
PY
    echo "[backend] PostgreSQL not ready yet ($i/30)..."
    sleep 1
done

cd /app/backend

echo "[backend] Running database migrations (alembic upgrade head)..."
alembic upgrade head

echo "[backend] Starting Uvicorn on 0.0.0.0:8000..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
