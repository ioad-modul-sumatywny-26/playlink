from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

DEFAULT_REGIONS = {
    "eu": os.getenv("PLAYLINK_EU_API", "http://localhost:8000"),
    "us": os.getenv("PLAYLINK_US_API", "http://localhost:8001"),
}


def get_base_url(region: str) -> str:
    """Resolve a region identifier ('eu' or 'us') to its API base URL."""
    try:
        return DEFAULT_REGIONS[region.strip().lower()].rstrip("/")
    except KeyError:
        raise ValueError(f"Unknown region '{region}', use 'eu' or 'us'") from None


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
            region: Region identifier ('eu' or 'us').
        """
        base_url = get_base_url(region)
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/games")
            resp.raise_for_status()
            return resp.json()

    @server.tool()
    async def list_rooms(
        region: str = "eu", game: str | None = None
    ) -> list[dict[str, Any]]:
        """List active LFG rooms, optionally filtered by game title.

        Args:
            region: Region identifier ('eu' or 'us').
            game: Optional game name to filter by (case-insensitive).
        """
        base_url = get_base_url(region)
        async with httpx.AsyncClient(timeout=5.0) as client:
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
            region: Region identifier ('eu' or 'us').
        """
        base_url = get_base_url(region)
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/rooms/{room_name}")
            resp.raise_for_status()
            return resp.json()

    @server.tool()
    async def check_platform_health() -> dict[str, Any]:
        """Probe liveness (/healthz), git commit version, and readiness (/readyz)."""
        results: dict[str, Any] = {}
        async with httpx.AsyncClient(timeout=3.0) as client:
            for reg, base_url in DEFAULT_REGIONS.items():
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

    @server.resource("playlink://games")
    async def resource_games() -> str:
        """Supported retro games catalog on PlayLink."""
        try:
            games = await list_games("eu")
            return "\n".join(games)
        except Exception as exc:  # noqa: BLE001
            return f"Error retrieving games: {exc}"

    @server.resource("playlink://rooms")
    async def resource_rooms() -> str:
        """Active LFG rooms summary on PlayLink."""
        try:
            rooms = await list_rooms("eu")
            if not rooms:
                return "No active rooms found in EU region."
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
            return f"Error retrieving rooms: {exc}"

    @server.resource("playlink://rooms/{room_name}")
    async def resource_room_details(room_name: str) -> str:
        """Detailed information for a specific room."""
        try:
            details = await get_room_details(room_name, "eu")
            return json.dumps(details, indent=2)
        except Exception as exc:  # noqa: BLE001
            return f"Error retrieving room '{room_name}': {exc}"

    @server.resource("playlink://status")
    async def resource_status() -> str:
        """Health and readiness status across PlayLink regions."""
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
