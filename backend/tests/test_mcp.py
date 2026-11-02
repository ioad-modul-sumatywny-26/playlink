from __future__ import annotations

import json

import httpx
import pytest
import respx

pytest.importorskip("mcp")

from mcp_server.server import create_server, get_base_url


def test_get_base_url():
    assert get_base_url("eu") == "http://localhost:8000"
    assert get_base_url("EU") == "http://localhost:8000"
    assert get_base_url("us") == "http://localhost:8001"
    assert get_base_url("US") == "http://localhost:8001"
    assert get_base_url("http://example.com/api/") == "http://example.com/api"
    assert get_base_url("https://playlink-eu-api.monster") == (
        "https://playlink-eu-api.monster"
    )


@pytest.mark.anyio
@respx.mock
async def test_list_games():
    server = create_server()
    respx.get("http://localhost:8000/games").mock(
        return_value=httpx.Response(200, json=["Quake III Arena", "Diablo II"])
    )

    res = await server.call_tool("list_games", {"region": "eu"})
    assert not res.is_error
    assert res.structured_content == {"result": ["Quake III Arena", "Diablo II"]}


@pytest.mark.anyio
@respx.mock
async def test_list_rooms_all_and_filtered():
    server = create_server()
    mock_rooms = [
        {"name": "q3-frag", "game": "Quake III Arena", "players_max": 8},
        {"name": "sc-bnet", "game": "StarCraft", "players_max": 4},
        {"name": "d2-baal", "game": "Diablo II", "players_max": 8},
    ]
    respx.get("http://localhost:8000/rooms").mock(
        return_value=httpx.Response(200, json=mock_rooms)
    )

    # Without filter
    all_rooms = await server.call_tool("list_rooms", {"region": "eu"})
    assert not all_rooms.is_error
    assert len(all_rooms.structured_content["result"]) == 3

    # With case-insensitive filter
    filtered = await server.call_tool(
        "list_rooms", {"region": "eu", "game": "starcraft"}
    )
    assert not filtered.is_error
    result = filtered.structured_content["result"]
    assert len(result) == 1
    assert result[0]["name"] == "sc-bnet"


@pytest.mark.anyio
@respx.mock
async def test_get_room_details():
    server = create_server()
    room_data = {
        "name": "q3-duel",
        "game": "Quake III Arena",
        "lobby_location": "q3a://127.0.0.1:27960",
        "players_max": 2,
        "players_active": 1,
        "members": [{"identity_address": "0x123", "username": "ranger"}],
    }
    respx.get("http://localhost:8000/rooms/q3-duel").mock(
        return_value=httpx.Response(200, json=room_data)
    )

    res = await server.call_tool(
        "get_room_details", {"room_name": "q3-duel", "region": "eu"}
    )
    assert not res.is_error
    result = json.loads(res.content[0].text)
    assert result["name"] == "q3-duel"
    assert result["players_active"] == 1


@pytest.mark.anyio
@respx.mock
async def test_check_platform_health_success():
    server = create_server()
    respx.get("http://localhost:8000/healthz").mock(
        return_value=httpx.Response(
            200, json={"status": "ok", "region": "eu", "version": "0.1.0"}
        )
    )
    respx.get("http://localhost:8000/readyz").mock(
        return_value=httpx.Response(200, json={"status": "ready", "region": "eu"})
    )
    respx.get("http://localhost:8001/healthz").mock(
        return_value=httpx.Response(
            200, json={"status": "ok", "region": "us", "version": "0.1.0"}
        )
    )
    respx.get("http://localhost:8001/readyz").mock(
        return_value=httpx.Response(200, json={"status": "ready", "region": "us"})
    )

    res = await server.call_tool("check_platform_health", {})
    assert not res.is_error
    result = json.loads(res.content[0].text)
    eu = result["eu"]
    us = result["us"]
    assert eu["reachable"] is True
    assert eu["health"]["status"] == "ok"
    assert eu["ready"]["status"] == "ready"
    assert us["reachable"] is True
    assert us["health"]["region"] == "us"


@pytest.mark.anyio
@respx.mock
async def test_check_platform_health_partial_failure():
    server = create_server()
    respx.get("http://localhost:8000/healthz").mock(
        return_value=httpx.Response(200, json={"status": "ok", "region": "eu"})
    )
    respx.get("http://localhost:8000/readyz").mock(
        return_value=httpx.Response(200, json={"status": "ready", "region": "eu"})
    )
    respx.get("http://localhost:8001/healthz").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    res = await server.call_tool("check_platform_health", {})
    assert not res.is_error
    result = json.loads(res.content[0].text)
    assert result["eu"]["reachable"] is True
    assert result["us"]["reachable"] is False
    assert "Connection refused" in result["us"]["error"]


@pytest.mark.anyio
@respx.mock
async def test_resources():
    server = create_server()
    respx.get("http://localhost:8000/games").mock(
        return_value=httpx.Response(200, json=["Quake III Arena", "Half-Life"])
    )
    respx.get("http://localhost:8000/rooms").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "hl-deathmatch",
                    "game": "Half-Life",
                    "players_max": 16,
                    "players_active": 4,
                    "lobby_location": "valve://127.0.0.1:27015",
                }
            ],
        )
    )
    respx.get("http://localhost:8000/rooms/hl-deathmatch").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "hl-deathmatch",
                "game": "Half-Life",
                "players_max": 16,
            },
        )
    )
    respx.get("http://localhost:8000/healthz").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    respx.get("http://localhost:8000/readyz").mock(
        return_value=httpx.Response(200, json={"status": "ready"})
    )
    respx.get("http://localhost:8001/healthz").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    respx.get("http://localhost:8001/readyz").mock(
        return_value=httpx.Response(200, json={"status": "ready"})
    )

    # Read playlink://games
    games_res = await server.read_resource("playlink://games")
    assert "Quake III Arena" in games_res[0].content
    assert "Half-Life" in games_res[0].content

    # Read playlink://rooms
    rooms_res = await server.read_resource("playlink://rooms")
    assert "hl-deathmatch" in rooms_res[0].content

    # Read playlink://rooms/{name}
    room_detail_res = await server.read_resource("playlink://rooms/hl-deathmatch")
    assert '"name": "hl-deathmatch"' in room_detail_res[0].content

    # Read playlink://status
    status_res = await server.read_resource("playlink://status")
    assert '"reachable": true' in status_res[0].content
