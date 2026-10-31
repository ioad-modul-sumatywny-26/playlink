# F4 — eksperyment porównawczy (1 vs 2 regiony)

Cel z dokumentu wizji (tydzień 7): zmierzyć, czy dwa regiony są szybsze niż jeden.

| Wariant | Ruch | Sens |
| --- | --- | --- |
| **A** | 100% → EU | baseline „jeden region” |
| **B** | naprzemiennie EU / US | „gracz blisko swojego regionu” |

## Scenariusze

1. `list_rooms` — `GET /rooms`
2. `create_room` — `POST /rooms`
3. `leave_room` — `POST /rooms/{name}/leave`
4. `chat_roundtrip` — WebSocket chat: wyślij wiadomość → odbierz własny broadcast
5. `rooms_ws_update` — WebSocket `/ws/rooms`: czas od utworzenia pokoju do pusha listy

Dla każdego: **n, OK, error rate, p50, p95, mean** (ms).

## Wymagania

- Dwa lokalne stacki: `.\start-local.ps1 -Both`
  - EU API `http://127.0.0.1:8000`
  - US API `http://127.0.0.1:8001`
- Python 3.11+
- Podniesiony rate limit na czas testu (domyślnie backend ma `10/minute` — za mało)

## Szybki start (Windows)

```powershell
# 1) Stacki
.\start-local.ps1 -Both

# 2) Rate limity pod lab + venv + pomiar A i B
.\experiments\f4\run-f4.ps1
```

Sam Python:

```powershell
cd experiments\f4
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py --variant both --users 4 --iterations 3 --pace 1.5
```

Wyniki lądują w `experiments/f4/results/run-*.json` oraz `run-*.md`.

## Publiczny deploy

Podmień URL-e na hosty z runbooka:

```powershell
python run.py --variant both `
  --eu https://playlink-eu-api.EXAMPLE `
  --us https://playlink-us-api.EXAMPLE `
  --users 4 --pace 2
```

## Interpretacja (hipotezy z wizji)

- **H1** — dla „USA” wariant A jest wyraźnie gorszy niż B (p95).
- **H2** — dla „EU” wariant B nie psuje wyników względem A.
- Na **localhost** obie hipotezy będą słabo widoczne (prawie ten sam RTT) — to nadal poprawny dry-run metody; właściwy wniosek wymaga publicznych regionów albo generatorów w dwóch lokalizacjach.

## Pliki

| Plik | Rola |
| --- | --- |
| `client.py` | auth ECDSA, REST, WS, próbki |
| `run.py` | orchestration A/B |
| `report.py` | markdown z tabelami |
| `run-f4.ps1` | venv + opcjonalne poluzowanie rate limit + run |
| `prepare-lab-limits.ps1` | `DEFAULT_RATE_LIMIT=1000/minute` w `.run/*.env` + recreate backend |
