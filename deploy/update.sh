#!/usr/bin/env bash
# Pull-based rollout, run every few minutes by a systemd timer on each region
# VM (see cloud-init.yaml). Deploys the latest GitHub Release (or PLAYLINK_TAG
# from site.env); the US region waits until EU reports that version, so a
# broken release stops at EU.
#   deploy/update.sh <eu|us>
set -euo pipefail

main() {
	local region="${1:?usage: update.sh <eu|us>}"
	cd "$(dirname "$0")/.."
	if [ ! -f deploy/site.env ]; then
		echo "deploy/site.env is missing; nothing to deploy yet"
		return 0
	fi
	# shellcheck disable=SC1091
	. deploy/lib.sh
	load_config
	check_region "$region"

	local latest current failed
	latest="${PLAYLINK_TAG:-}"
	if [ -z "$latest" ]; then
		latest="$(curl -fsS "https://api.github.com/repos/$GITHUB_REPO/releases/latest" | jq -r .tag_name)"
	fi
	current="$(cat ".run/$region.tag" 2>/dev/null || true)"
	failed="$(cat ".run/$region.failed" 2>/dev/null || true)"
	if [ -z "$latest" ] || [ "$latest" = null ] || [ "$latest" = "$current" ] || [ "$latest" = "$failed" ]; then
		return 0
	fi

	if [ "$region" != eu ]; then
		local eu_version
		eu_version="$(curl -fsS "$(api_url eu)/healthz" | jq -r .version || true)"
		if [ "$eu_version" != "$latest" ]; then
			echo "Waiting for EU to run $latest (EU reports: ${eu_version:-unreachable})"
			return 0
		fi
	fi

	echo "Updating $region: ${current:-none} -> $latest"
	git fetch --quiet --tags --force origin
	git -c advice.detachedHead=false checkout --quiet "$latest"
	if bash deploy/deploy.sh "$region" "$latest"; then
		rm -f ".run/$region.failed"
	else
		echo "$latest" >".run/$region.failed"
		return 1
	fi
}

# Everything runs inside main() so the checkout above cannot change the lines
# bash has not read yet.
main "$@"
exit $?
