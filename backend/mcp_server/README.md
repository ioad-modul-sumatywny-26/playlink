# PlayLink MCP Server

Serwer Model Context Protocol (MCP) do inspekcji platformy PlayLink w trybie read-only (Issue #95).

## Narzedzia (Tools)

- `list_games(region: str = "eu")`: Lista obslugiwanych gier retro.
- `list_rooms(region: str = "eu", game: str | None = None)`: Aktywne pokoje LFG z opcjonalnym filtrem po grze.
- `get_room_details(room_name: str, region: str = "eu")`: Szczegoly pokoju (gracze, komunikator, opis, eventy).
- `check_platform_health()`: Status endpointow `/healthz` i `/readyz` oraz latencja dla wszystkich skonfigurowanych regionow.
- `search_logs(query: str = "level:ERROR", minutes: int = 60, limit: int = 50)`: Logi wszystkich regionow (VictoriaLogs, LogsQL), od najnowszych.
- `query_metrics(query: str)`: Zapytanie PromQL do metryk (CPU, pamiec, zadania HTTP).

## Zasoby (Resources)

### Sparametryzowane per region
- `playlink://{region}/games`: Lista gier dla wybranego regionu (np. `playlink://eu/games`, `playlink://us/games`).
- `playlink://{region}/rooms`: Aktywne pokoje w wybranym regionie (np. `playlink://eu/rooms`).
- `playlink://{region}/rooms/{room_name}`: Szczegoly pokoju w wybranym regionie.

### Zbiorcze / Multi-region
- `playlink://games`: Lista gier ze sprawdzonych, dostepnych regionow.
- `playlink://rooms`: Zagregowane podsumowanie aktywnych pokojow ze wszystkich skonfigurowanych regionow.
- `playlink://rooms/{room_name}`: Wyszukiwanie pokoju we wszystkich skonfigurowanych regionach.
- `playlink://status`: Stan zdrowia i dostepnosci bazy dla wszystkich regionow w JSON.

## Uruchomienie

### stdio (domyslny dla asystentow AI)
```bash
uv run --project backend python -m mcp_server
```

### sse / streamable-http (sieciowy)
```bash
uv run --project backend python backend/mcp_server/server.py --transport sse --port 8080
```

## Zmienne srodowiskowe i konfiguracja regionow

Regiony i adresy API sa wykrywane dynamicznie w nastepujacej kolejnosci:
1. `PLAYLINK_REGIONS`: mapa JSON (np. `{"eu": "http://localhost:8000", "us": "http://localhost:8001"}`) lub lista po przecinku (`eu,us,asia`).
2. Zmienne per region: `PLAYLINK_<REGION>_API` oraz `PUBLIC_REGION_<REGION>_API` (np. `PLAYLINK_EU_API`, `PUBLIC_REGION_US_API`).
3. `PLAYLINK_DOMAIN`: w przypadku ustawienia domeny, serwer automatycznie wyprowadza adresy w formacie `https://playlink-<region>-api.<PLAYLINK_DOMAIN>`.
4. Wartosci domyslne: EU (`http://localhost:8000`), US (`http://localhost:8001`).

### Logi i metryki (opcjonalnie)

`search_logs` i `query_metrics` dzialaja po ustawieniu `PLAYLINK_LOGS_URL`, `PLAYLINK_METRICS_URL`, `PLAYLINK_OBS_USER` (domyslnie `playlink`) i `PLAYLINK_OBS_PASSWORD`, patrz `docs/operations/observability.md`. Bez nich odpowiadaja, ze nie sa skonfigurowane; pozostale narzedzia nie wymagaja logowania.

## Konfiguracja w asystentach AI

### Claude Desktop / Cursor / Antigravity

```json
{
  "mcpServers": {
    "playlink": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "C:\\x\\y\\z\\playlink\\backend",
        "python",
        "-m",
        "mcp_server"
      ],
      "env": {
        "PLAYLINK_DOMAIN": "<domena>",
        "PLAYLINK_REGIONS": "eu,us"
      }
    }
  }
}
```

`env` wskazuje wdrozone regiony (produkcja); bez niego serwer laczy sie z `localhost`. Pelna instrukcja podlaczenia do produkcji: sekcje "Case 1" (lokalnie) i "Case 2" (zdalnie) w glownym `README.md`.
