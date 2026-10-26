#!/bin/sh
set -e

if [ -z "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
    echo "[cloudflared] No CLOUDFLARE_TUNNEL_TOKEN provided."
    echo "[cloudflared] Cloudflare Tunnel is dormant. Services can be reached directly via exposed ports."
    exec sleep infinity
fi

echo "[cloudflared] Starting Cloudflare Tunnel agent..."
if ! cloudflared tunnel --no-autoupdate run --token "$CLOUDFLARE_TUNNEL_TOKEN"; then
    err=$?
    echo "[cloudflared] ERROR: cloudflared exited with status $err."
    echo "[cloudflared] Check that CLOUDFLARE_TUNNEL_TOKEN is a valid active tunnel token from Cloudflare Zero Trust."
    echo "[cloudflared] (If testing locally without a tunnel, do not provide a token and pass --expose-ports)."
    sleep 5
    exit $err
fi
