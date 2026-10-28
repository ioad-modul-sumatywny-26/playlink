#!/usr/bin/env bash
# Push this region's part of deploy/site.env to its VM and trigger a deploy.
# Clears a failed-release marker so the next run retries.
#   deploy/azure-env.sh <eu|us>
set -euo pipefail

REGION="${1:?usage: azure-env.sh <eu|us>}"
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. deploy/lib.sh
load_config
check_region "$REGION"

token_var="TUNNEL_TOKEN_${REGION^^}"
site_env="$(
	cat <<EOF
PLAYLINK_DOMAIN=$PLAYLINK_DOMAIN
$token_var=${!token_var}
JWT_SECRET=$JWT_SECRET
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
ADMIN_ADDRESSES=${ADMIN_ADDRESSES:-}
PLAYLINK_TAG=${PLAYLINK_TAG:-}
GHCR_USER=${GHCR_USER:-}
GHCR_TOKEN=${GHCR_TOKEN:-}
EOF
)"

# Base64 keeps the secrets out of shell quoting on both ends.
site_b64="$(printf '%s\n' "$site_env" | base64 | tr -d '\n')"
az vm run-command invoke -g "playlink-$REGION" -n "playlink-$REGION" --command-id RunShellScript \
	--scripts "cloud-init status --wait >/dev/null; umask 077; echo $site_b64 | base64 -d > /opt/playlink/deploy/site.env; rm -f /opt/playlink/.run/$REGION.failed; systemctl start --no-block playlink-update.service; echo site.env written" \
	--query 'value[0].message' -o tsv
