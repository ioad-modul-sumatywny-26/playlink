# shellcheck shell=bash
# Helpers shared by deploy.sh and update.sh. Sourced, not executed.

load_config() {
	set -a
	# shellcheck disable=SC1091
	. deploy/config.env
	if [ -f deploy/site.env ]; then
		# shellcheck disable=SC1091
		. deploy/site.env
	fi
	set +a
	PLAYLINK_DOMAIN="${PLAYLINK_DOMAIN:-}"
}

check_region() {
	case "$1" in
	eu | us) ;;
	*)
		echo "unknown region: $1 (expected eu or us)" >&2
		exit 1
		;;
	esac
}

frontend_port() { [ "$1" = eu ] && echo 3000 || echo 3001; }
backend_port() { [ "$1" = eu ] && echo 8000 || echo 8001; }

# Public names stay one level below the domain: Cloudflare's free certificate
# covers *.<domain> only, not *.playlink.<domain>.
frontend_url() {
	if [ -n "$PLAYLINK_DOMAIN" ]; then
		echo "https://playlink-$1.$PLAYLINK_DOMAIN"
	else
		echo "http://localhost:$(frontend_port "$1")"
	fi
}

api_url() {
	if [ -n "$PLAYLINK_DOMAIN" ]; then
		echo "https://playlink-$1-api.$PLAYLINK_DOMAIN"
	else
		echo "http://localhost:$(backend_port "$1")"
	fi
}

ws_url() { api_url "$1" | sed 's/^http/ws/'; }

# Where regions push logs and metrics. Defaults follow the tunnel hostnames in
# public mode and the central stack on this machine in local mode.
metrics_url() {
	if [ -n "${OBS_METRICS_URL:-}" ]; then
		echo "$OBS_METRICS_URL"
	elif [ -n "$PLAYLINK_DOMAIN" ]; then
		echo "https://playlink-metrics.$PLAYLINK_DOMAIN"
	else
		echo "http://host.docker.internal:8428"
	fi
}

logs_url() {
	if [ -n "${OBS_LOGS_URL:-}" ]; then
		echo "$OBS_LOGS_URL"
	elif [ -n "$PLAYLINK_DOMAIN" ]; then
		echo "https://playlink-logs.$PLAYLINK_DOMAIN"
	else
		echo "http://host.docker.internal:9428"
	fi
}

# The entry host shows the region chooser. It is served by the EU stack; in
# local mode it is the EU port under a different host name.
entry_origin() {
	if [ -n "$PLAYLINK_DOMAIN" ]; then
		echo "https://playlink.$PLAYLINK_DOMAIN"
	else
		echo "http://127.0.0.1:$(frontend_port eu)"
	fi
}
