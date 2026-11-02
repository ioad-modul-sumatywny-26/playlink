from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

load_dotenv()


def get_configured_regions() -> dict[str, str]:
    """Resolve configured regions mapping (region_id -> api_base_url) dynamically.

    Sources checked in order of priority:
    1. PLAYLINK_REGIONS:
       - JSON dict string, e.g. '{"eu": "http://...", "us": "http://..."}'
       - Comma-separated region names, e.g. 'eu,us,asia'
    2. Environment variables:
       - PLAYLINK_<REGION>_API (e.g. PLAYLINK_EU_API, PLAYLINK_US_API)
       - PUBLIC_REGION_<REGION>_API (e.g. PUBLIC_REGION_EU_API)
    3. PLAYLINK_DOMAIN:
       - If set, derives https://playlink-<reg>-api.<domain> for each region
    4. Defaults:
       - eu: http://localhost:8000
       - us: http://localhost:8001
    """
    regions: dict[str, str] = {}
    env_regions = os.getenv("PLAYLINK_REGIONS", "").strip()
    explicit_names: set[str] = set()

    if env_regions:
        if env_regions.startswith("{"):
            try:
                parsed = json.loads(env_regions)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        regions[str(k).strip().lower()] = str(v).strip().rstrip("/")
            except Exception:  # noqa: BLE001
                pass
        else:
            explicit_names = {
                name.strip().lower() for name in env_regions.split(",") if name.strip()
            }

    for key, value in os.environ.items():
        val = value.strip().rstrip("/")
        if not val:
            continue
        k_upper = key.upper()
        if k_upper.startswith("PLAYLINK_") and k_upper.endswith("_API"):
            reg = k_upper[len("PLAYLINK_") : -len("_API")].lower()
            if reg and reg not in ("backend", "public", "ws"):
                regions[reg] = val
        elif k_upper.startswith("PUBLIC_REGION_") and k_upper.endswith("_API"):
            reg = k_upper[len("PUBLIC_REGION_") : -len("_API")].lower()
            if reg:
                regions[reg] = val

    domain = os.getenv("PLAYLINK_DOMAIN", "").strip().strip(".")
    if domain:
        target_names = explicit_names or (set(regions.keys()) | {"eu", "us"})
        for reg in target_names:
            if reg not in regions:
                regions[reg] = f"https://playlink-{reg}-api.{domain}"

    if "eu" not in regions:
        regions["eu"] = os.getenv("PLAYLINK_EU_API", "http://localhost:8000")
    if "us" not in regions:
        regions["us"] = os.getenv("PLAYLINK_US_API", "http://localhost:8001")

    return regions


class _RegionsDict(dict):
    """Dynamic backward-compatible dict proxy reflecting configured regions."""

    def __getitem__(self, key: str) -> str:
        return get_configured_regions()[key.strip().lower()]

    def __contains__(self, key: object) -> bool:
        if isinstance(key, str):
            return key.strip().lower() in get_configured_regions()
        return False

    def __iter__(self):
        return iter(get_configured_regions())

    def items(self):
        return get_configured_regions().items()

    def keys(self):
        return get_configured_regions().keys()

    def values(self):
        return get_configured_regions().values()

    def get(self, key: str, default: Any = None) -> Any:
        return get_configured_regions().get(key.strip().lower(), default)


DEFAULT_REGIONS = _RegionsDict()


def get_base_url(region: str) -> str:
    """Resolve a region identifier (e.g. 'eu' or 'us') to its API base URL."""
    regions = get_configured_regions()
    key = region.strip().lower()
    if key in regions:
        return regions[key].rstrip("/")
    valid = ", ".join(sorted(regions.keys()))
    raise ValueError(f"Unknown region '{region}', use {valid}")


def _raise_tool_error(
    exc: Exception,
    region: str,
    base_url: str | None = None,
    entity: str | None = None,
) -> None:
    """Translate lower-level exceptions into descriptive ToolError for AI clients."""
    url_desc = base_url or "unknown URL"
    if isinstance(exc, ValueError):
        raise ToolError(str(exc)) from exc
    if isinstance(exc, httpx.TimeoutException):
        raise ToolError(
            f"Request to region '{region}' ({url_desc}) timed out after 5.0s."
        ) from exc
    if isinstance(exc, httpx.ConnectError):
        raise ToolError(
            f"Cannot connect to region '{region}' at {url_desc}: connection refused. "
            "The regional backend may be offline or unreachable."
        ) from exc
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 404:
            if entity:
                raise ToolError(
                    f"Room '{entity}' was not found in region '{region}' (HTTP 404)."
                ) from exc
            raise ToolError(
                f"Requested resource not found in region '{region}' (HTTP 404)."
            ) from exc
        snippet = exc.response.text[:200]
        raise ToolError(
            f"HTTP {status} error from region '{region}' ({url_desc}): {snippet}"
        ) from exc
    raise ToolError(f"Network error while querying region '{region}': {exc}") from exc


@contextlib.asynccontextmanager
async def _safe_http_client(region: str, entity: str | None = None):
    try:
        base_url = get_base_url(region)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            yield client, base_url
        except ToolError:
            raise
        except Exception as exc:
            _raise_tool_error(exc, region, base_url, entity)


def create_server() -> MCPServer:
    """Create and configure the PlayLink MCPServer instance."""
    server = MCPServer(
        name="playlink-inspector",
        description=(
            "Safe inspection tools and resources for PlayLink retro gaming "
            "LFG platform."
        ),
    )

    @server.tool()
    async def list_games(region: str = "eu") -> list[str]:
        """List supported retro games on the PlayLink platform.

        Args:
            region: Region identifier (e.g. 'eu', 'us' or configured region).
        """
        async with _safe_http_client(region) as (client, base_url):
            resp = await client.get(f"{base_url}/games")
            resp.raise_for_status()
            return resp.json()

    @server.tool()
    async def list_rooms(
        region: str = "eu", game: str | None = None
    ) -> list[dict[str, Any]]:
        """List active LFG rooms, optionally filtered by game title.

        Args:
            region: Region identifier (e.g. 'eu', 'us' or configured region).
            game: Optional game name to filter by (case-insensitive).
        """
        async with _safe_http_client(region) as (client, base_url):
            resp = await client.get(f"{base_url}/rooms")
            resp.raise_for_status()
            rooms: list[dict[str, Any]] = resp.json()
            if game:
                filter_game = game.strip().lower()
                rooms = [
                    r for r in rooms if r.get("game", "").strip().lower() == filter_game
                ]
            return rooms

    @server.tool()
    async def get_room_details(room_name: str, region: str = "eu") -> dict[str, Any]:
        """Fetch complete details for a specific room.

        Includes active players, communicator link, requirements, and events.

        Args:
            room_name: The unique room identifier / name.
            region: Region identifier (e.g. 'eu', 'us' or configured region).
        """
        async with _safe_http_client(region, entity=room_name) as (client, base_url):
            resp = await client.get(f"{base_url}/rooms/{room_name}")
            resp.raise_for_status()
            return resp.json()

    @server.tool()
    async def check_platform_health() -> dict[str, Any]:
        """Probe liveness (/healthz), git commit version, and readiness (/readyz)."""
        results: dict[str, Any] = {}
        regions = get_configured_regions()
        async with httpx.AsyncClient(timeout=3.0) as client:
            for reg, base_url in regions.items():
                start_time = time.perf_counter()
                try:
                    hz = await client.get(f"{base_url}/healthz")
                    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    rz = await client.get(f"{base_url}/readyz")
                    results[reg] = {
                        "reachable": True,
                        "url": base_url,
                        "latency_ms": latency_ms,
                        "health": (
                            hz.json()
                            if hz.is_success
                            else {"status_code": hz.status_code}
                        ),
                        "ready": (
                            rz.json()
                            if rz.is_success
                            else {"status_code": rz.status_code}
                        ),
                    }
                except Exception as exc:  # noqa: BLE001
                    results[reg] = {
                        "reachable": False,
                        "url": base_url,
                        "error": str(exc),
                    }
        return results

    # --- Specific Region Resource Templates ---

    @server.resource("playlink://{region}/games")
    async def resource_region_games(region: str) -> str:
        """Supported retro games catalog for a specific region."""
        try:
            games = await list_games(region)
            return "\n".join(games)
        except Exception as exc:  # noqa: BLE001
            return f"Error retrieving games for region '{region}': {exc}"

    @server.resource("playlink://{region}/rooms")
    async def resource_region_rooms(region: str) -> str:
        """Active LFG rooms summary for a specific region."""
        try:
            rooms = await list_rooms(region)
            reg_upper = region.upper()
            if not rooms:
                return f"No active rooms found in {reg_upper} region."
            lines = []
            for r in rooms:
                max_p = r.get("players_max")
                loc = r.get("lobby_location", "N/A")
                lines.append(
                    f"- [{r.get('name')}] {r.get('game')} | "
                    f"Max players: {max_p} | Location: {loc}"
                )
            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return f"Error retrieving rooms for region '{region}': {exc}"

    @server.resource("playlink://{region}/rooms/{room_name}")
    async def resource_region_room_details(region: str, room_name: str) -> str:
        """Detailed information for a specific room in a specific region."""
        try:
            details = await get_room_details(room_name, region)
            return json.dumps(details, indent=2)
        except Exception as exc:  # noqa: BLE001
            return f"Error retrieving room '{room_name}' in region '{region}': {exc}"

    # --- Multi-Region Aggregated / Convenience Resources ---

    @server.resource("playlink://games")
    async def resource_games() -> str:
        """Supported retro games catalog across available PlayLink regions."""
        regions = get_configured_regions()
        last_err: Exception | None = None
        for reg in regions:
            try:
                games = await list_games(reg)
                return "\n".join(games)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
        return f"Error retrieving games: {last_err}"

    @server.resource("playlink://rooms")
    async def resource_rooms() -> str:
        """Active LFG rooms summary across all configured PlayLink regions."""
        regions = get_configured_regions()
        all_lines: list[str] = []
        total_rooms = 0

        for reg in regions:
            reg_upper = reg.upper()
            try:
                rooms = await list_rooms(reg)
                if rooms:
                    all_lines.append(f"[{reg_upper}]")
                    for r in rooms:
                        max_p = r.get("players_max")
                        loc = r.get("lobby_location", "N/A")
                        all_lines.append(
                            f"- [{r.get('name')}] {r.get('game')} | "
                            f"Max players: {max_p} | Location: {loc}"
                        )
                    total_rooms += len(rooms)
            except Exception:  # noqa: BLE001
                continue

        if not total_rooms:
            reg_list = ", ".join(regions.keys())
            return f"No active rooms found across configured regions ({reg_list})."

        return "\n".join(all_lines)

    @server.resource("playlink://rooms/{room_name}")
    async def resource_room_details(room_name: str) -> str:
        """Detailed information for a specific room across any configured region."""
        regions = get_configured_regions()
        for reg in regions:
            try:
                details = await get_room_details(room_name, reg)
                if isinstance(details, dict):
                    return json.dumps(details, indent=2)
            except Exception:  # noqa: BLE001
                continue
        reg_list = ", ".join(regions.keys())
        return f"Room '{room_name}' not found across configured regions ({reg_list})."

    @server.resource("playlink://status")
    async def resource_status() -> str:
        """Health and readiness status across all configured PlayLink regions."""
        status = await check_platform_health()
        return json.dumps(status, indent=2)

    return server


mcp = create_server()


def main() -> None:
    """CLI entrypoint for running the PlayLink MCP server."""
    parser = argparse.ArgumentParser(
        description="PlayLink Model Context Protocol (MCP) server"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address for network transports (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port number for network transports (default: 8080)",
    )

    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    elif args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        sys.exit(f"Unknown transport: {args.transport}")


if __name__ == "__main__":
    main()
