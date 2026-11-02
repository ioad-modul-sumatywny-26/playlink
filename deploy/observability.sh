#!/usr/bin/env bash
# Central logs and metrics for all regions (Grafana + VictoriaMetrics +
# VictoriaLogs). Runs on any machine with Docker, including a laptop.
#   deploy/observability.sh up       start the stack (Grafana on 127.0.0.1:3300)
#   deploy/observability.sh down     stop it; data is kept in volumes
#   deploy/observability.sh logs     follow its logs
# Needs OBS_PASSWORD in deploy/site.env (CF_ACCESS_TEAM is optional). With TUNNEL_TOKEN_OBS set, the tunnel
# connector starts too, so regions on other machines can push to it.
set -euo pipefail

ACTION="${1:?usage: observability.sh <up|down|logs>}"
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. deploy/lib.sh
load_config
: "${OBS_PASSWORD:?OBS_PASSWORD is required in deploy/site.env}"
export OBS_USER="${OBS_USER:-playlink}" OBS_PASSWORD TUNNEL_TOKEN_OBS="${TUNNEL_TOKEN_OBS:-}"
# Team domain of Cloudflare Access (e.g. myteam.cloudflareaccess.com): Grafana
# then trusts the Access login instead of asking for its own password.
# CF_ACCESS_AUD is the Access application's audience tag; only its tokens count.
export CF_ACCESS_TEAM="${CF_ACCESS_TEAM:-}" CF_ACCESS_AUD="${CF_ACCESS_AUD:-}" GRAFANA_JWT=false
if [ -n "$CF_ACCESS_TEAM" ]; then
	: "${CF_ACCESS_AUD:?CF_ACCESS_AUD is required with CF_ACCESS_TEAM}"
	GRAFANA_JWT=true
fi

compose=(docker compose -f compose.observability.yaml)
[ -n "$TUNNEL_TOKEN_OBS" ] && compose+=(--profile tunnel)

case "$ACTION" in
up)
	"${compose[@]}" up -d --wait --wait-timeout 120
	echo "Grafana: http://127.0.0.1:3300 (user admin, password OBS_PASSWORD)"
	;;
down) "${compose[@]}" down ;;
logs) "${compose[@]}" logs -f --tail 50 ;;
*)
	echo "unknown action: $ACTION" >&2
	exit 1
	;;
esac
