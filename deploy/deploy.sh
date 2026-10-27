#!/usr/bin/env bash
# Start or update one regional stack. The same command runs on a laptop and on
# a region VM:
#   deploy/deploy.sh eu           build images from the working tree
#   deploy/deploy.sh us v0.2.0    pull release images from GHCR
# With PLAYLINK_DOMAIN and TUNNEL_TOKEN_<REGION> in deploy/site.env the region
# is public through Cloudflare Tunnel; otherwise it is published on localhost.
set -euo pipefail

REGION="${1:?usage: deploy.sh <eu|us> [tag]}"
TAG="${2:-local}"
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. deploy/lib.sh
load_config
check_region "$REGION"

token_var="TUNNEL_TOKEN_${REGION^^}"
export TUNNEL_TOKEN="${!token_var:-}"

if [ -n "$PLAYLINK_DOMAIN" ]; then
	: "${TUNNEL_TOKEN:?$token_var is required when PLAYLINK_DOMAIN is set}"
	: "${JWT_SECRET:?JWT_SECRET is required in deploy/site.env}"
	: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required in deploy/site.env}"
else
	JWT_SECRET="${JWT_SECRET:-local-dev-secret-at-least-32-characters}"
	POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-playlink}"
fi

mkdir -p .run
export APP_ENV_FILE=".run/$REGION.env"
export IMAGE_TAG="$TAG"
FRONTEND_PORT="$(frontend_port "$REGION")"
BACKEND_PORT="$(backend_port "$REGION")"
export FRONTEND_PORT BACKEND_PORT

# Container environment: shared settings, region URLs and secrets. The tunnel
# token is not included; only cloudflared receives it.
umask 077
{
	grep -v '^GITHUB_REPO=' deploy/config.env
	cat <<EOF
REGION=$REGION
PUBLIC_REGION=$REGION
PUBLIC_BACKEND_URL=$(api_url "$REGION")
PUBLIC_WS_URL=$(ws_url "$REGION")
PUBLIC_ENTRY_HOST=$(entry_origin | sed 's#^.*://##')
PUBLIC_REGION_EU_FRONTEND=$(frontend_url eu)
PUBLIC_REGION_EU_API=$(api_url eu)
PUBLIC_REGION_EU_WS=$(ws_url eu)
PUBLIC_REGION_US_FRONTEND=$(frontend_url us)
PUBLIC_REGION_US_API=$(api_url us)
PUBLIC_REGION_US_WS=$(ws_url us)
CORS_ORIGINS=$(entry_origin),$(frontend_url eu),$(frontend_url us)
JWT_SECRET=$JWT_SECRET
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
DATABASE_URL=postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@db:5432/$POSTGRES_DB
ADMIN_ADDRESSES=${ADMIN_ADDRESSES:-}
EOF
} >"$APP_ENV_FILE"

compose=(docker compose -p "playlink-$REGION" -f compose.yaml)
[ "$TAG" = local ] && compose+=(-f compose.build.yaml)
[ -z "$PLAYLINK_DOMAIN" ] && compose+=(-f compose.ports.yaml)
[ -n "$TUNNEL_TOKEN" ] && compose+=(--profile tunnel)

previous="$(cat ".run/$REGION.tag" 2>/dev/null || true)"

if [ "$TAG" = local ]; then
	"${compose[@]}" build
else
	if [ -n "${GHCR_TOKEN:-}" ]; then
		echo "$GHCR_TOKEN" | docker login ghcr.io -u "${GHCR_USER:-github}" --password-stdin
	fi
	"${compose[@]}" pull
fi

echo "Starting $REGION ($TAG)..."
if ! "${compose[@]}" up -d --remove-orphans --wait --wait-timeout 300; then
	echo "Region $REGION did not become healthy on $TAG" >&2
	"${compose[@]}" ps >&2
	if [ -n "$previous" ] && [ "$previous" != local ] && [ "$previous" != "$TAG" ]; then
		echo "Rolling back to $previous" >&2
		IMAGE_TAG="$previous" "${compose[@]}" up -d --remove-orphans --wait --wait-timeout 300 || true
	fi
	exit 1
fi

echo "$TAG" >".run/$REGION.tag"
echo "Region $REGION is up on $TAG"
echo "  frontend: $(frontend_url "$REGION")"
echo "  api:      $(api_url "$REGION")/healthz"
[ "$REGION" = eu ] && echo "  chooser:  $(entry_origin)"
exit 0
