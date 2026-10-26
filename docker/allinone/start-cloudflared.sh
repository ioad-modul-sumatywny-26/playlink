#!/bin/sh
set -e

if [ -z "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
    echo "[cloudflared] No CLOUDFLARE_TUNNEL_TOKEN provided."
    echo "[cloudflared] Cloudflare Tunnel is dormant. Services can be reached directly via exposed ports."
    exec sleep infinity
fi

# Clean token (strip quotes, whitespace, or command wrapper if passed)
TOKEN=$(python3 - "$CLOUDFLARE_TUNNEL_TOKEN" <<'PY'
import sys

raw = sys.argv[1] if len(sys.argv) > 1 else ""
t = raw.strip().strip("'\"").strip()
if "--token" in t:
    t = t.split("--token")[-1].strip().strip("'\"").strip()
elif "service install" in t:
    t = t.split("service install")[-1].strip().strip("'\"").strip()

if len(t) == 36 and t.count("-") == 4:
    sys.stderr.write(
        "\n[cloudflared] ERROR: Provided token looks like a Tunnel UUID (" + t + "), NOT a Tunnel Token!\n"
        "[cloudflared] In Cloudflare Zero Trust (Networks -> Tunnels), copy the base64 token string (starts with 'eyJh...').\n\n"
    )
elif not t.startswith("eyJh"):
    sys.stderr.write(
        f"\n[cloudflared] WARNING: Token prefix is '{t[:6]}...', expected 'eyJh...'.\n"
        "[cloudflared] Cloudflare Tunnel tokens are base64-encoded strings starting with 'eyJh'.\n\n"
    )

sys.stdout.write(t)
PY
)

if [ -z "$TOKEN" ]; then
    echo "[cloudflared] ERROR: Token is empty after parsing."
    sleep 15
    exit 1
fi

TOKEN_PREFIX=$(echo "$TOKEN" | cut -c 1-6)
TOKEN_LEN=${#TOKEN}
echo "[cloudflared] Starting Cloudflare Tunnel agent (token length: $TOKEN_LEN, prefix: ${TOKEN_PREFIX}...)..."

set +e
cloudflared tunnel --no-autoupdate run --token "$TOKEN"
err=$?
set -e

if [ $err -ne 0 ]; then
    echo "[cloudflared] ERROR: cloudflared exited with status $err."
    echo "[cloudflared] Please check that CLOUDFLARE_TUNNEL_TOKEN is a valid active tunnel token from Cloudflare Zero Trust."
    echo "[cloudflared] (If testing locally without a tunnel, do not provide a token and pass --expose-ports)."
    sleep 15
    exit $err
fi
