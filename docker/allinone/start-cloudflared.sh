#!/bin/sh
set -e

if [ -z "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
    echo "[cloudflared] No CLOUDFLARE_TUNNEL_TOKEN provided."
    echo "[cloudflared] Cloudflare Tunnel is dormant. Services can be reached directly via exposed ports."
    exec sleep infinity
fi

echo "[cloudflared] Starting Cloudflare Tunnel agent..."
exec cloudflared tunnel --no-autoupdate run --token "$CLOUDFLARE_TUNNEL_TOKEN"
