#!/usr/bin/env bash
# Create one VM on Azure and hand it deploy/site.env. Needs `az login`.
# Later secret changes: deploy/azure-env.sh <region|ops>.
#   deploy/azure-vm.sh eu polandcentral
#   deploy/azure-vm.sh us denmarkeast    # Azure for Students allows EU regions only
#   deploy/azure-vm.sh ops polandcentral # central logs and metrics (Grafana)
# Delete one with: az group delete -n playlink-<region|ops>
set -euo pipefail

REGION="${1:?usage: azure-vm.sh <eu|us|ops> <azure-location>}"
LOCATION="${2:?usage: azure-vm.sh <eu|us|ops> <azure-location>}"
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. deploy/lib.sh
load_config
[ "$REGION" = ops ] || check_region "$REGION"

token_var="TUNNEL_TOKEN_${REGION^^}"
if [ "$REGION" = ops ]; then
	: "${OBS_PASSWORD:?OBS_PASSWORD is required in deploy/site.env}"
	# The stack follows a branch (default main), not release tags.
	REF="${PLAYLINK_OPS_REF:-main}"
	UPDATE_CMD="/bin/bash -c 'cd /opt/playlink \&\& git pull -q --ff-only \&\& bash deploy/observability.sh up'"
else
	: "${PLAYLINK_DOMAIN:?PLAYLINK_DOMAIN is required in deploy/site.env}"
	: "${!token_var:?$token_var is required in deploy/site.env}"
	: "${JWT_SECRET:?JWT_SECRET is required in deploy/site.env}"
	: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required in deploy/site.env}"
	REF="${PLAYLINK_TAG:-main}"
	UPDATE_CMD="/bin/bash /opt/playlink/deploy/update.sh $REGION"
fi

GROUP="playlink-$REGION"
mkdir -p .run
sed -e "s/__REGION__/$REGION/g" -e "s#__REPO__#$GITHUB_REPO#g" -e "s#__REF__#$REF#g" 	-e "s#__UPDATE_CMD__#$UPDATE_CMD#g" deploy/cloud-init.yaml >".run/cloud-init-$REGION.yaml"

# Standard_B2ats_v2 and a 64 GB P6 disk are in the free-services allowance.
# --nsg-rule NONE: no inbound port at all; traffic arrives through the tunnel
# and administration goes through `az vm run-command`.
az group create -n "$GROUP" -l "$LOCATION" -o none
az vm create -g "$GROUP" -n "playlink-$REGION" \
	--image Canonical:ubuntu-24_04-lts:server:latest \
	--size Standard_B2ats_v2 \
	--os-disk-size-gb 64 --storage-sku Premium_LRS \
	--public-ip-sku Standard --nsg-rule NONE \
	--admin-username playlink --generate-ssh-keys \
	--custom-data ".run/cloud-init-$REGION.yaml" \
	-o table

bash deploy/azure-env.sh "$REGION"

echo "VM playlink-$REGION created; it starts within a few minutes."
echo "Logs: az vm run-command invoke -g $GROUP -n playlink-$REGION --command-id RunShellScript --scripts 'journalctl -u playlink-update -n 50 --no-pager'"
