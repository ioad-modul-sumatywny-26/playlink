#!/usr/bin/env bash
# Start Playlink locally (no Cloudflare): deploy.sh + idempotent seed.
#
#   bash scripts/local-up.sh           # EU only
#   bash scripts/local-up.sh --both    # EU + US
#   bash scripts/local-up.sh --both --lab-limits   # also raise rate limits for F4
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BOTH=0
LAB_LIMITS=0
for arg in "$@"; do
	case "$arg" in
	--both) BOTH=1 ;;
	--lab-limits) LAB_LIMITS=1 ;;
	-h | --help)
		sed -n '2,8p' "$0"
		exit 0
		;;
	*)
		echo "unknown arg: $arg (use --both and/or --lab-limits)" >&2
		exit 1
		;;
	esac
done

step() { printf '\n==> %s\n' "$*"; }

wait_health() {
	local url="$1"
	for _ in $(seq 1 60); do
		if curl -fsS "$url" >/dev/null 2>&1; then
			return 0
		fi
		sleep 2
	done
	echo "backend did not become healthy: $url" >&2
	return 1
}

# Patch .run/<region>.env rate limits and recreate backend (needs APP_ENV_FILE).
raise_limits() {
	local region="$1"
	local env_file=".run/${region}.env"
	local proj="playlink-${region}"
	if [[ ! -f "$env_file" ]]; then
		echo "  skip limits: missing $env_file"
		return 0
	fi
	if grep -q '^DEFAULT_RATE_LIMIT=' "$env_file"; then
		sed -i.bak 's|^DEFAULT_RATE_LIMIT=.*|DEFAULT_RATE_LIMIT=1000/minute|' "$env_file"
	else
		printf '\nDEFAULT_RATE_LIMIT=1000/minute\n' >>"$env_file"
	fi
	if grep -q '^WS_RATE_LIMIT_MAX_MESSAGES=' "$env_file"; then
		sed -i.bak 's|^WS_RATE_LIMIT_MAX_MESSAGES=.*|WS_RATE_LIMIT_MAX_MESSAGES=100|' "$env_file"
	else
		printf 'WS_RATE_LIMIT_MAX_MESSAGES=100\n' >>"$env_file"
	fi
	rm -f "${env_file}.bak"
	echo "  patched $env_file"

	export APP_ENV_FILE="$env_file"
	export IMAGE_TAG="${IMAGE_TAG:-local}"
	if [[ "$region" == eu ]]; then
		export FRONTEND_PORT=3000 BACKEND_PORT=8000
	else
		export FRONTEND_PORT=3001 BACKEND_PORT=8001
	fi
	if docker compose -p "$proj" -f compose.yaml ps -q backend >/dev/null 2>&1; then
		step "Recreating $proj backend (lab limits)"
		docker compose -p "$proj" -f compose.yaml -f compose.build.yaml -f compose.ports.yaml \
			up -d --no-deps --force-recreate backend
	fi
}

seed_region() {
	local region="$1"
	local proj="playlink-${region}"
	local env_file=".run/${region}.env"
	local api_port
	api_port="$( [[ "$region" == eu ]] && echo 8000 || echo 8001 )"

	step "Seeding demo data on $region (skip if rooms already exist)"
	export APP_ENV_FILE="$env_file"
	export IMAGE_TAG="${IMAGE_TAG:-local}"
	if [[ "$region" == eu ]]; then
		export FRONTEND_PORT=3000 BACKEND_PORT=8000
	else
		export FRONTEND_PORT=3001 BACKEND_PORT=8001
	fi

	# APP_ENV_FILE must be set — compose.yaml interpolates it even for exec.
	docker compose -p "$proj" -f compose.yaml exec -T \
		-e PLAYLINK_BASE_URL="http://localhost:8000" \
		backend python - <scripts/seed_local.py

	docker compose -p "$proj" -f compose.yaml exec -T db \
		psql -U playlink -d playlink -c \
		"UPDATE room SET expires_at = NOW() + INTERVAL '7 days'
		 WHERE name IN ('q3-fragfest', 'd2-baal-runs', 'sc-broodwar');" \
		>/dev/null || true
	echo "  seed done ($region api :$api_port)"
}

step "Checking Docker"
docker version >/dev/null

step "Starting region eu (deploy/deploy.sh eu)"
bash deploy/deploy.sh eu

if [[ "$BOTH" -eq 1 ]]; then
	step "Starting region us (deploy/deploy.sh us)"
	bash deploy/deploy.sh us
fi

step "Waiting for EU backend health"
wait_health "http://localhost:8000/healthz"
echo "  EU backend healthy"

if [[ "$BOTH" -eq 1 ]]; then
	step "Waiting for US backend health"
	wait_health "http://localhost:8001/healthz"
	echo "  US backend healthy"
fi

if [[ "$LAB_LIMITS" -eq 1 ]]; then
	step "Raising lab rate limits"
	raise_limits eu
	[[ "$BOTH" -eq 1 ]] && raise_limits us
	sleep 5
	wait_health "http://localhost:8000/healthz"
fi

seed_region eu

cat <<EOF

Playlink is up (local mode, no Cloudflare).
  Chooser : http://127.0.0.1:3000
  EU app  : http://localhost:3000/rooms
  EU API  : http://localhost:8000/docs
EOF
if [[ "$BOTH" -eq 1 ]]; then
	cat <<EOF
  US app  : http://localhost:3001/rooms
  US API  : http://localhost:8001/docs
EOF
fi
cat <<'EOF'

Demo login (IDENTITY) — paste this mnemonic:
  test test test test test test test test test test test junk

F4 experiment:
  cd experiments/f4 && python -m venv .venv && . .venv/bin/activate
  pip install -r requirements.txt && python run.py

Stop EU:  docker compose -p playlink-eu -f compose.yaml down
Stop US:  docker compose -p playlink-us -f compose.yaml down
EOF
