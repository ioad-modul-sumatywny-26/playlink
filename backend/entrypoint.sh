#!/bin/sh
set -e

for i in $(seq 1 30); do
  python - <<'PY' && break
import os, socket, sys
host = os.environ.get("POSTGRES_HOST", "db")
try:
    socket.getaddrinfo(host, 5432)
    s = socket.create_connection((host, 5432), timeout=2)
    s.close()
except Exception:
    sys.exit(1)
PY
  echo "DB not ready yet ($i/30)"
  sleep 2
done

alembic upgrade head
# ``--no-proxy-headers`` keeps ``request.client`` at the direct peer. The
# limiter resolves the real player from CF-Connecting-IP itself, trusting only
# explicit proxy addresses, so X-Forwarded-For cannot be spoofed into a
# separate rate-limit bucket.
exec uvicorn main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
