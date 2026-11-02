from __future__ import annotations

import json

import httpx
import pytest
import respx

pytest.importorskip("mcp")

from mcp_server.server import create_server, get_base_url, get_configured_regions


def test_get_base_url():
    assert get_base_url("eu") == "http://localhost:8000"
    assert get_base_url("EU") == "http://localhost:8000"
    assert get_base_url("us") == "http://localhost:8001"
    assert get_base_url("US") == "http://localhost:8001"
    with pytest.raises(ValueError, match="Unknown region"):
        get_base_url("http://example.com")


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
    assert "Max players: 16" in rooms_res[0].content

    # Read playlink://rooms/{name}
    room_detail_res = await server.read_resource("playlink://rooms/hl-deathmatch")
    assert '"name": "hl-deathmatch"' in room_detail_res[0].content

    # Read playlink://status
    status_res = await server.read_resource("playlink://status")
    assert '"reachable": true' in status_res[0].content


def test_dynamic_region_discovery(monkeypatch):
    # Default regions
    monkeypatch.delenv("PLAYLINK_REGIONS", raising=False)
    monkeypatch.delenv("PLAYLINK_DOMAIN", raising=False)
    monkeypatch.delenv("PLAYLINK_ASIA_API", raising=False)
    regions = get_configured_regions()
    assert regions["eu"] == "http://localhost:8000"
    assert regions["us"] == "http://localhost:8001"

    # PLAYLINK_REGIONS JSON dict
    monkeypatch.setenv(
        "PLAYLINK_REGIONS",
        '{"eu": "http://eu:8000", "us": "http://us:8001", "asia": "http://asia:8002"}',
    )
    regions = get_configured_regions()
    assert regions["asia"] == "http://asia:8002"
    assert get_base_url("asia") == "http://asia:8002"

    # PLAYLINK_DOMAIN derivation
    monkeypatch.delenv("PLAYLINK_REGIONS", raising=False)
    monkeypatch.setenv("PLAYLINK_DOMAIN", "playlink.test")
    regions = get_configured_regions()
    assert regions["eu"] == "https://playlink-eu-api.playlink.test"
    assert regions["us"] == "https://playlink-us-api.playlink.test"

    # Environment variable scanning
    monkeypatch.setenv("PLAYLINK_SA_API", "http://sa-api:8000")
    regions = get_configured_regions()
    assert regions["sa"] == "http://sa-api:8000"
    assert get_base_url("sa") == "http://sa-api:8000"


@pytest.mark.anyio
@respx.mock
async def test_parameterized_and_cross_region_resources():
    server = create_server()
    respx.get("http://localhost:8000/games").mock(
        return_value=httpx.Response(200, json=["Quake III Arena"])
    )
    respx.get("http://localhost:8001/games").mock(
        return_value=httpx.Response(200, json=["StarCraft"])
    )
    respx.get("http://localhost:8000/rooms").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "eu-frag",
                    "game": "Quake III Arena",
                    "players_max": 8,
                    "lobby_location": "eu-central",
                }
            ],
        )
    )
    respx.get("http://localhost:8001/rooms").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "us-rush",
                    "game": "StarCraft",
                    "players_max": 4,
                    "lobby_location": "na-east",
                }
            ],
        )
    )
    respx.get("http://localhost:8000/rooms/us-rush").mock(
        return_value=httpx.Response(404, json={"detail": "Room not found"})
    )
    respx.get("http://localhost:8001/rooms/us-rush").mock(
        return_value=httpx.Response(
            200,
            json={"name": "us-rush", "game": "StarCraft", "players_max": 4},
        )
    )

    # 1. Parameterized games per region
    eu_games = await server.read_resource("playlink://eu/games")
    assert "Quake III Arena" in eu_games[0].content
    us_games = await server.read_resource("playlink://us/games")
    assert "StarCraft" in us_games[0].content

    # 2. Parameterized rooms per region
    eu_rooms = await server.read_resource("playlink://eu/rooms")
    assert "eu-frag" in eu_rooms[0].content
    assert "us-rush" not in eu_rooms[0].content

    us_rooms = await server.read_resource("playlink://us/rooms")
    assert "us-rush" in us_rooms[0].content
    assert "eu-frag" not in us_rooms[0].content

    # 3. Multi-region aggregated rooms (playlink://rooms)
    all_rooms = await server.read_resource("playlink://rooms")
    assert "[EU]" in all_rooms[0].content
    assert "eu-frag" in all_rooms[0].content
    assert "[US]" in all_rooms[0].content
    assert "us-rush" in all_rooms[0].content

    # 4. Cross-region room detail resolution (found in US even without region in URI)
    room_detail = await server.read_resource("playlink://rooms/us-rush")
    assert '"name": "us-rush"' in room_detail[0].content

    # 5. Parameterized specific room detail
    us_room_detail = await server.read_resource("playlink://us/rooms/us-rush")
    assert '"name": "us-rush"' in us_room_detail[0].content
