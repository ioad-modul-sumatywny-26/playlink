# PlayLink MCP Server

Serwer Model Context Protocol (MCP) do inspekcji platformy PlayLink w trybie read-only (Issue #95).

## Narzedzia (Tools)

- `list_games(region: str = "eu")`: Lista obslugiwanych gier retro.
- `list_rooms(region: str = "eu", game: str | None = None)`: Aktywne pokoje LFG z opcjonalnym filtrem po grze.
- `get_room_details(room_name: str, region: str = "eu")`: Szczegoly pokoju (gracze, komunikator, opis, eventy).
- `check_platform_health()`: Status endpointow `/healthz` i `/readyz` oraz latencja dla regionow EU i US.

## Zasoby (Resources)

- `playlink://games`: Lista gier w formacie tekstowym.
- `playlink://rooms`: Podsumowanie aktywnych pokojow w EU.
- `playlink://rooms/{room_name}`: Szczegoly pokoju w formacie JSON.
- `playlink://status`: Stan zdrowia i dostepnosci bazy w JSON.

## Uruchomienie

### stdio (domyslny dla asystentow AI)
```bash
uv run --project backend python -m mcp_server
```

### sse / streamable-http (sieciowy)
```bash
uv run --project backend python backend/mcp_server/server.py --transport sse --port 8080
```

## Zmienne srodowiskowe

- `PLAYLINK_EU_API` (domyslnie: `http://localhost:8000`)
- `PLAYLINK_US_API` (domyslnie: `http://localhost:8001`)

## Konfiguracja w asystentach AI

### Claude Desktop / Cursor / Antigravity

```json
{
  "mcpServers": {
    "playlink": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "C:\\x\\y\\z\\playlink\\backend",
        "python",
        "-m",
        "mcp_server"
      ]
    }
  }
}
```
