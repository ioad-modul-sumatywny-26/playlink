# F4 — eksperyment porównawczy (1 vs 2 regiony)

Cel z dokumentu wizji (tydzień 7): zmierzyć, czy dwa regiony są szybsze niż jeden.

| Wariant | Ruch | Sens |
| --- | --- | --- |
| **A** | 100% → EU | baseline „jeden region” |
| **B** | naprzemiennie EU / US | „gracz blisko swojego regionu” |

## Scenariusze

1. `list_rooms` — `GET /rooms`
2. `create_room` — `POST /rooms`
3. `join_room` / `leave_room`
4. `chat_roundtrip` — WebSocket chat: wyślij wiadomość → odbierz własny broadcast
5. `rooms_ws_update` — WebSocket `/ws/rooms`: czas od utworzenia pokoju do pusha listy

Dla każdego: **n, OK, error rate, p50, p95, mean** (ms).

Klient jest w pełni async (`httpx.AsyncClient` + `asyncio.gather`). Błędy (w tym **429**) trafiają do raportu i **nie przerywają** przebiegu.

## Wymagania

- Dwa lokalne stacki: `bash scripts/local-up.sh --both`
  - EU API `http://127.0.0.1:8000`
  - US API `http://127.0.0.1:8001`
- Python 3.11+
- Podniesiony rate limit na czas testu (domyślnie backend ma `10/minute` — za mało):  
  `bash scripts/local-up.sh --both --lab-limits`

## Szybki start

```bash
bash scripts/local-up.sh --both --lab-limits

cd experiments/f4
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows (Git Bash): source .venv/Scripts/activate
pip install -r requirements.txt
python run.py --variant both --users 4 --iterations 3 --pace 1.5
```

Wyniki: `experiments/f4/results/run-*.json` oraz `run-*.md`.

## Publiczny deploy

```bash
python run.py --variant both \
  --eu https://playlink-eu-api.EXAMPLE \
  --us https://playlink-us-api.EXAMPLE \
  --users 4 --pace 2
```

## Interpretacja (hipotezy z wizji)

- **H1** — dla „USA” wariant A jest wyraźnie gorszy niż B (p95).
- **H2** — dla „EU” wariant B nie psuje wyników względem A.
- Na **localhost** obie hipotezy będą słabo widoczne (prawie ten sam RTT) — to dry-run metody; właściwy wniosek wymaga publicznych regionów.

## Pliki

| Plik | Rola |
| --- | --- |
| `client.py` | async auth/REST/WS, próbki (bez abortu na 429) |
| `run.py` | orchestration A/B |
| `report.py` | markdown z tabelami |
