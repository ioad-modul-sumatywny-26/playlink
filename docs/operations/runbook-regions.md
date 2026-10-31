# Multi-region runbook (EU / US)

## Current test deployment

| Region | Azure location | Resource group / VM | Public names |
| --- | --- | --- | --- |
| EU | `polandcentral` | `playlink-eu` | `playlink.nikodemnowak.pl`, `playlink-eu.nikodemnowak.pl`, `playlink-eu-api.nikodemnowak.pl` |
| US | `denmarkeast` (stand-in) | `playlink-us` | `playlink-us.nikodemnowak.pl`, `playlink-us-api.nikodemnowak.pl` |

- Subscription: Azure for Students. It only allows EU regions, so the "US" stack runs in Denmark until a US machine is funded; the mechanism is identical.
- Tunnels `playlink-eu` / `playlink-us` live in the Cloudflare account that owns `nikodemnowak.pl`.
- VMs are pinned to `PLAYLINK_TAG=v0.1.0-rc.4`. Remove the pin (and run `deploy/azure-env.sh eu` / `us`) before the first non-rc release, otherwise they stay on rc.4.
- Images are private in GHCR; VMs pull with a `read:packages` token in `site.env`. Making the packages public removes the need for it.

### Daily operations (any machine)

Install the Azure CLI, clone the repository, then:

```bash
az login                      # account with the Azure for Students subscription
deploy/azure.sh status        # power state, deployed version, containers
deploy/azure.sh stop          # deallocate both VMs (no compute billing)
deploy/azure.sh start         # start both; the stack is up ~2 minutes later
deploy/azure.sh logs eu       # updater log and containers of one region
```

`stop` / `start` / `logs` accept a region (`eu` or `us`). Data survives a stop: Postgres lives on the OS disk.

`deploy/site.env` (secrets, tunnel tokens) exists only on the machine that created the VMs and on the VMs themselves. To work from another machine, rebuild it from both VMs:

```bash
deploy/azure.sh site-env eu   # PLAYLINK_DOMAIN, TUNNEL_TOKEN_EU, JWT_SECRET, ...
deploy/azure.sh site-env us   # adds TUNNEL_TOKEN_US
```

## Topology

Hostnames are derived from `PLAYLINK_DOMAIN` and stay one level below the domain, because Cloudflare's free Universal SSL covers `*.<domain>` only.

| Hostname | Tunnel | Compose service |
| --- | --- | --- |
| `playlink.<domain>` | EU | `frontend:3000` (entry + chooser) |
| `playlink-eu.<domain>` | EU | `frontend:3000` |
| `playlink-eu-api.<domain>` | EU | `backend:8000` |
| `playlink-us.<domain>` | US | `frontend:3000` |
| `playlink-us-api.<domain>` | US | `backend:8000` |

Each region runs `db`, `backend`, `frontend`, and `cloudflared` as its own compose project (`playlink-eu`, `playlink-us`). The tunnel is the only ingress; no port is published in public mode.

`playlink.<domain>` points at the EU stack and serves the region chooser. If EU is completely down the entry host is down too; `playlink-us.<domain>` remains directly reachable.

## 1. One command

`deploy/deploy.sh <eu|us> [tag]` is the only deploy command; it runs the same way on a laptop and on a region VM.

| Invocation | Effect |
| --- | --- |
| `deploy/deploy.sh eu` | Build images from the working tree |
| `deploy/deploy.sh us v0.2.0` | Pull `ghcr.io` images for that tag |

It reads `deploy/config.env` (shared, non-secret) and `deploy/site.env` (machine-specific, gitignored; template in `deploy/site.env.example`), writes the container env to `.run/<region>.env`, starts the stack with `up --wait`, and rolls back to the previous tag (`.run/<region>.tag`) if the stack does not become healthy.

### Local mode

Without `PLAYLINK_DOMAIN` in `deploy/site.env` the stack runs on localhost with dev secrets and no tunnel:

| Region | Frontend | API |
| --- | --- | --- |
| EU | `http://localhost:3000` | `http://localhost:8000` |
| US | `http://localhost:3001` | `http://localhost:8001` |

The chooser is at `http://127.0.0.1:3000`. Both regions can run on one machine (`deploy/deploy.sh eu` and `deploy/deploy.sh us`).

### Public mode

Set `PLAYLINK_DOMAIN`, `TUNNEL_TOKEN_<REGION>`, `JWT_SECRET`, and `POSTGRES_PASSWORD` in `deploy/site.env`. `JWT_SECRET` must be identical in every region (`openssl rand -hex 32`). The script generates `CORS_ORIGINS` (entry host plus both frontends) and the `PUBLIC_*` URLs from the domain.

## 2. Cloudflare

1. Create one **remotely-managed** tunnel per region in Zero Trust (for example `playlink-eu`, `playlink-us`).
2. Add the public hostnames from the topology table. Service URLs must be Docker service names, not `localhost`:
   - frontend hosts -> `http://frontend:3000`
   - API hosts -> `http://backend:8000`
3. Put each tunnel token (starts with `eyJh...`) in `deploy/site.env` as `TUNNEL_TOKEN_EU` / `TUNNEL_TOKEN_US`.
4. DNS must be proxied. SSL/TLS: **Full**, Always Use HTTPS, minimum TLS 1.2. Disable Rocket Loader.
5. Cache: bypass the `-api` hosts, `/ws/*`, `/healthz`, `/readyz`; static assets may cache.
6. WebSockets are supported through the tunnel; keep the existing 30 s heartbeat.

A tunnel token identifies exactly one tunnel. Do **not** use one token on both regions expecting region selection: that creates HA replicas of the same hostname and Cloudflare load-balances them randomly.

Switching to another domain (for example a teammate's) means changing `PLAYLINK_DOMAIN` and creating new tunnels; nothing else changes.

## 3. Azure VMs

Prerequisites: `az login`, and `PLAYLINK_DOMAIN`, the region's tunnel token, `JWT_SECRET`, and `POSTGRES_PASSWORD` in local `deploy/site.env`.

```bash
deploy/azure-vm.sh eu polandcentral
deploy/azure-vm.sh us denmarkeast
```

Azure for Students restricts deployments to `polandcentral`, `germanywestcentral`, `francecentral`, `denmarkeast` and `spaincentral` (policy "Allowed resource deployment regions"), so the second region is a distant EU region rather than the US. `Standard_B2ats_v2` has run out of capacity for this subscription in Germany West Central, France Central and later Spain Central; check before creating a VM:

```bash
az vm list-skus -l <location> --size Standard_B2ats_v2 --all --query "[].restrictions[].type"
```

A `Location` restriction means unavailable; `Zone` only rules out some zones (the script creates non-zonal VMs).

Per region the script creates resource group `playlink-<region>` with one `Standard_B2ats_v2` VM (Ubuntu 24.04, 64 GB Premium P6 disk) and **no inbound NSG rules at all**. `cloud-init.yaml` installs Docker, adds a 2 GB swap file, clones the repository to `/opt/playlink`, and enables `playlink-update.timer`. The script then pushes `site.env` to the VM with `az vm run-command` and triggers the first update.

Administration also goes through `az vm run-command`; no SSH is needed. After changing `deploy/site.env` (secrets, `PLAYLINK_TAG`, `GHCR_TOKEN`) run `deploy/azure-env.sh <region>`: it pushes the file, clears a failed-release marker and triggers an update.

Logs:

```bash
az vm run-command invoke -g playlink-eu -n playlink-eu --command-id RunShellScript \
  --scripts 'journalctl -u playlink-update -n 50 --no-pager'
```

Delete a region: `az group delete -n playlink-<region>`.

If the 1 GiB VM OOMs under four containers, resize to `Standard_B1ms` (2 GiB) and record the cost.

## 4. Release and rollout

```bash
git tag -a v0.1.0 -m "multi-region deploy"
git push origin v0.1.0
```

1. `release.yml` runs CI, pushes `playlink-backend` and `playlink-frontend` images to GHCR, and creates the GitHub Release.
2. VMs are pull-based. A systemd timer (every 2 minutes) runs `deploy/update.sh <region>`, which deploys the latest release, or `PLAYLINK_TAG` from `site.env` if set.
3. Staged rollout: US waits until EU's `/healthz` reports that version. A release that fails its health check stops at EU; the tag is recorded in `.run/<region>.failed` and not retried. A release whose images cannot be pulled yet is retried on the next run.
4. No GitHub secrets are needed for deploys. GHCR packages must be public, or set `GHCR_USER` / `GHCR_TOKEN` (token with `read:packages`) in `site.env`.

Verify:

```bash
curl -fsS https://playlink-eu-api.<domain>/healthz
curl -fsS https://playlink-us-api.<domain>/healthz
curl -I https://playlink-eu.<domain>/
curl -I https://playlink-us.<domain>/
curl -I https://playlink.<domain>/
```

Open the entry host in a browser. On a clean profile it probes both regions and redirects to the faster live one. Use `?region=us` or `?region=eu` to force a region.

## 5. Rollback

Automatic: if `up --wait` fails, `deploy.sh` redeploys the previous tag. The backend runs `alembic upgrade head` on start, so this only works when the failed release added no migration; otherwise downgrade the database first (`docker compose -p playlink-<region> run --rm backend alembic downgrade <revision>`) or roll forward. Keep migrations backward compatible so the previous image can run on the new schema.

Manual: set `PLAYLINK_TAG=<previous tag>` in the region's `deploy/site.env` (the timer then deploys it), or run on the VM:

```bash
cd /opt/playlink
bash deploy/deploy.sh eu v0.1.0
```

## 6. Failure drills

Run on the region's machine. Project names are `playlink-eu` / `playlink-us`.

| Drill | Command | Expected |
| --- | --- | --- |
| Backend dies (EU) | `docker compose -p playlink-eu stop backend` | `playlink-eu-api/healthz` fails; the entry probe picks US; `playlink-us` stays healthy |
| Tunnel dies (EU) | `docker compose -p playlink-eu stop cloudflared` | EU hosts return Cloudflare 1033/502; US works |
| DB dies (EU) | `docker compose -p playlink-eu stop db` | `/readyz` returns 503 and the backend reports unhealthy (it is not restarted); US unaffected |
| Region recovers | `docker compose -p playlink-eu start db backend cloudflared` | health returns; expired rooms are cleaned by TTL |

Record detection time, switch time, and recovery time for the F5 report. The entry host is EU-backed; a complete EU outage also takes the entry down. Document that `playlink-us.<domain>` is the direct fallback.

## 7. Troubleshooting

- **Cloudflare 1033** — no healthy connector. Check `docker compose -p playlink-<region> logs cloudflared` for `Registered tunnel connection`; verify the token starts with `eyJh...` and belongs to the tunnel that owns the DNS hostname. A UUID or API key is not a tunnel token.
- **Cloudflare 502** — the connector is up but the service URL is wrong. Use `http://frontend:3000` / `http://backend:8000`, not `localhost`.
- **403 CSRF on form posts** — the frontend must receive `X-Forwarded-Proto` and the original `Host` header; do not set `ORIGIN` on a container that serves both the entry and regional hostnames.
- **429 for everyone** — the backend is seeing the connector/frontend as one client. Check that `TRUSTED_PROXY_HOSTS` (IPs or CIDR ranges) covers the Docker network, and that SSR forwards `CF-Connecting-IP`.
- **`password authentication failed` after recreating the DB** — the Postgres volume was initialized with a different password. Reuse the same `POSTGRES_PASSWORD` or recreate the volume deliberately.
- **OOM / restart loop** — check `docker stats` and `dmesg`; reduce `mem_limit`, add swap, or resize to `Standard_B1ms`.
- **GHCR denied** — the package is private; make it public or set `GHCR_USER` / `GHCR_TOKEN` in `site.env`.
- **US stays on the old version** — expected while EU does not report the new version on `/healthz`, or after a failed EU release; check the update log.

## 8. Cost and maintenance

- The 750 free `Standard_B2ats_v2` hours are one pool per month, not per VM: one VM running all month uses it, the second is paid from the student credit (roughly 7-8 USD/month). Two 64 GB P6 disks are free; the two Standard public IPs cost about 3-4 USD/month each if not covered. Check the real amount in Cost Management.
- Deallocate the VMs when not testing (`deploy/azure.sh stop`); a deallocated VM uses no compute hours.
- `Standard_B2ats_v2` capacity changes over time (Germany West Central, France Central and Spain Central have refused it); Poland Central and Denmark East work at the moment.
- Rotate tunnel tokens if they leak; the token can start a connector for that tunnel.
