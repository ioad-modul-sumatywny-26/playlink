#!/usr/bin/env bash
# Day-to-day control of the region VMs from any machine with `az login`.
#   deploy/azure.sh status            power state and deployed version
#   deploy/azure.sh stop [eu|us]      deallocate (stops VM billing)
#   deploy/azure.sh start [eu|us]     start; the stack comes back on boot
#   deploy/azure.sh logs <eu|us>      last updater runs and containers
#   deploy/azure.sh site-env <eu|us>  print the VM's site.env (to restore
#                                     deploy/site.env on a new machine)
set -euo pipefail

ACTION="${1:?usage: azure.sh <status|start|stop|logs|site-env> [eu|us]}"
REGIONS="${2:-eu us}"

on_vm() { # region script
	az vm run-command invoke -g "playlink-$1" -n "playlink-$1" --command-id RunShellScript \
		--scripts "$2" --query 'value[0].message' -o tsv
}

for region in $REGIONS; do
	case "$ACTION" in
	status)
		state="$(az vm get-instance-view -g "playlink-$region" -n "playlink-$region" \
			--query "instanceView.statuses[?starts_with(code,'PowerState/')].displayStatus | [0]" -o tsv)"
		echo "$region: $state"
		if [ "$state" = "VM running" ]; then
			on_vm "$region" 'cat /opt/playlink/.run/*.tag; docker ps --format "{{.Names}} {{.Status}}"'
		fi
		;;
	stop) az vm deallocate -g "playlink-$region" -n "playlink-$region" --no-wait && echo "$region: stopping" ;;
	start) az vm start -g "playlink-$region" -n "playlink-$region" --no-wait && echo "$region: starting" ;;
	logs) on_vm "$region" 'journalctl -u playlink-update -n 30 --no-pager; docker ps -a' ;;
	site-env) on_vm "$region" 'cat /opt/playlink/deploy/site.env' ;;
	*)
		echo "unknown action: $ACTION" >&2
		exit 1
		;;
	esac
done
