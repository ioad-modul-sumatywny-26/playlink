#!/bin/sh
set -e

echo "[frontend] Preparing SvelteKit frontend service..."

cd /app/frontend

export HOST="0.0.0.0"
export PORT="3000"
export NODE_ENV="production"
export BACKEND_INTERNAL_URL="${BACKEND_INTERNAL_URL:-http://127.0.0.1:8000}"
export ORIGIN="${ORIGIN:-http://localhost:3000}"
export PUBLIC_BACKEND_URL="${PUBLIC_BACKEND_URL:-http://localhost:8000}"
export PUBLIC_WS_URL="${PUBLIC_WS_URL:-ws://localhost:8000}"

echo "[frontend] ORIGIN: $ORIGIN"
echo "[frontend] PUBLIC_BACKEND_URL: $PUBLIC_BACKEND_URL"
echo "[frontend] PUBLIC_WS_URL: $PUBLIC_WS_URL"
echo "[frontend] Starting SvelteKit server on 0.0.0.0:3000..."

exec bun run build/index.js
