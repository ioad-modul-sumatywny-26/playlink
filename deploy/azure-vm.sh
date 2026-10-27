#!/usr/bin/env bash
# Create one region VM on Azure and hand it deploy/site.env. Needs `az login`.
# Later secret changes: deploy/azure-env.sh <region>.
#   deploy/azure-vm.sh eu polandcentral
#   deploy/azure-vm.sh us denmarkeast    # Azure for Students allows EU regions only
# Delete a region with: az group delete -n playlink-<region>
set -euo pipefail

REGION="${1:?usage: azure-vm.sh <eu|us> <azure-location>}"
LOCATION="${2:?usage: azure-vm.sh <eu|us> <azure-location>}"
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. deploy/lib.sh
load_config
check_region "$REGION"

token_var="TUNNEL_TOKEN_${REGION^^}"
: "${PLAYLINK_DOMAIN:?PLAYLINK_DOMAIN is required in deploy/site.env}"
: "${!token_var:?$token_var is required in deploy/site.env}"
: "${JWT_SECRET:?JWT_SECRET is required in deploy/site.env}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required in deploy/site.env}"

GROUP="playlink-$REGION"
mkdir -p .run
sed -e "s/__REGION__/$REGION/g" -e "s#__REPO__#$GITHUB_REPO#g" -e "s#__REF__#${PLAYLINK_TAG:-main}#g" deploy/cloud-init.yaml >".run/cloud-init-$REGION.yaml"

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

echo "VM playlink-$REGION created; it deploys the latest release within a few minutes."
echo "Logs: az vm run-command invoke -g $GROUP -n playlink-$REGION --command-id RunShellScript --scripts 'journalctl -u playlink-update -n 50 --no-pager'"
