# Logs and metrics

One place to see logs and resource usage of every region: **Grafana** (dashboards), **VictoriaLogs** (logs) and **VictoriaMetrics** (metrics). Each region runs two small containers next to the app: **Vector** ships logs and metrics, **cAdvisor** measures every container.

```
region EU  vector ──┐                          ┌─ VictoriaMetrics ─┐
                    ├── HTTPS (basic auth) ────┤                   ├─ Grafana
region US  vector ──┘   via Cloudflare Tunnel  └─ VictoriaLogs ────┘
                                                     ops VM or any laptop
```

Regions only make outbound connections, so they still expose no port. The central stack (the "ops" side) runs on any machine with Docker: a laptop for a demo, a small Azure VM for permanent use.

## Run it locally

Put `OBS_PASSWORD` (any password) in `deploy/site.env`, then:

```bash
bash deploy/observability.sh up     # Grafana on http://127.0.0.1:3300, user admin
bash deploy/deploy.sh eu            # regions ship automatically once OBS_PASSWORD is set
bash deploy/deploy.sh us
```

Open the **PlayLink regions** dashboard. Regions on the same machine reach the stack through `host.docker.internal`; both share the host's CPU and memory charts. `bash deploy/observability.sh down` stops the stack; data stays in Docker volumes (14 days).

## Public mode (regions and ops VM on Azure)

1. **Cloudflare**: one more tunnel, `playlink-ops`, with three public hostnames: `playlink-metrics.<domain>` → `http://victoriametrics:8428`, `playlink-logs.<domain>` → `http://victorialogs:9428`, `playlink-grafana.<domain>` → `http://grafana:3000`. Its token is `TUNNEL_TOKEN_OBS`.
2. **`deploy/site.env`**: `OBS_PASSWORD` (long, random, `openssl rand -hex 16`), `OBS_USER` (default `playlink`) and `TUNNEL_TOKEN_OBS`. The regions ship once `OBS_PASSWORD` is set and push to the `playlink-metrics` / `playlink-logs` hostnames (`OBS_METRICS_URL` / `OBS_LOGS_URL` override them).
3. **Ops VM**: `bash deploy/azure-vm.sh ops polandcentral` creates `playlink-ops` (same size as the regions, no inbound port), starts the stack and the tunnel connector, and keeps it up to date from the `main` branch (`PLAYLINK_OPS_REF` follows another branch). Grafana is then at `https://playlink-grafana.<domain>`, user `admin`, password `OBS_PASSWORD`.
4. **Regions**: push the new settings with `bash deploy/azure-env.sh eu` and `us`. The next release deploy starts the two containers on the VM; they are not part of any older release.

`deploy/azure.sh status|start|stop` includes the ops VM once it exists. If the stack is down, agents keep up to 256 MB of logs on disk and send them when it returns.

## What is collected

| Data | Source | Where to look |
| --- | --- | --- |
| Container logs (backend, frontend, db); the backend writes JSON | Vector `docker_logs` | Logs panels; fields `service`, `region`, `level`, `event`, `request_id` |
| Business events `login`, `room_created`, `room_joined`, `room_left`, `room_closed`, `member_kicked` | backend `log_event` | field `event`, counter `playlink_events_total` |
| Request id on every backend log line and as `X-Request-ID` response header | backend middleware | field `request_id` |
| Server errors of the frontend (`server_error`) and errors in the visitor's browser (`client_error`) | `hooks.server.ts`, `hooks.client.ts` → `POST /api/client-errors` | `level:ERROR service:frontend` |
| Host CPU, memory, network, disk, load | Vector `host_metrics` | `host_*` |
| CPU, memory and network of each container | cAdvisor | `container_*`, label `container_label_com_docker_compose_service` |
| Requests, status codes, latency, open WebSockets | backend `/metrics` | `playlink_*` |

`/metrics` answers only on the compose network: a request that came through Cloudflare (it has `CF-Connecting-IP`) gets a 404. `/api/client-errors` keeps at most 1.5 KB of stack per report, five reports per page load and 20 per minute per address.

Queries to try in Grafana → Explore → Logs:

```
level:ERROR                      errors of all regions
service:backend level:WARNING    rate limits and warnings
event:room_created region:us     rooms created in US
request_id:a1be49ec35a04a5e      everything one request did
```

## Ask the logs through MCP

The local MCP server (`backend/mcp_server`) has two more tools, `search_logs` (LogsQL) and `query_metrics` (PromQL). They work once the endpoints are set where the MCP server runs:

```
PLAYLINK_LOGS_URL=https://playlink-logs.<domain>
PLAYLINK_METRICS_URL=https://playlink-metrics.<domain>
PLAYLINK_OBS_USER=playlink
PLAYLINK_OBS_PASSWORD=<OBS_PASSWORD>
```

Without them those two tools answer that they are not configured; the room tools keep working without any login.

## Resource use (measured locally, per container)

| Component | Memory |
| --- | --- |
| backend / db / frontend | ~90 / ~30 / ~13 MB |
| Vector (agent) / cAdvisor | ~65 / ~15 MB |
| Grafana / VictoriaMetrics / VictoriaLogs | ~200 / ~100 / ~12 MB |

A region with the agent needs about 0.25 GB, the central stack about 0.35 GB, so both fit a 1 GB VM with the swap file.

## Limits and security

- Vector and cAdvisor read container data through the Docker socket and `/var/lib/docker` (read-only mounts), which is root-equivalent on that host. Vector gets only the `OBS_*` settings, never the app secrets.
- Push and read endpoints (`playlink-metrics`, `playlink-logs`) share one basic-auth user: use a long random `OBS_PASSWORD`. `playlink-grafana` sits behind Cloudflare Access (Zero Trust Free, application "PlayLink Grafana", policy "Team emails"): add a teammate's address to that policy to let them in, then they sign in to Grafana as `admin`.
- Log lines carry shortened wallet addresses (`0x1234…abcd`) and no tokens or message contents.
- **Cloudflare edge analytics** (traffic, countries, requests blocked before they reach a server) are not collected: that needs an API token and an extra exporter. The dashboards show what reaches the servers.
