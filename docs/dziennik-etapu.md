# Dziennik etapu (tygodnie 1–9)

Format z dokumentu wizji: zaplanowane / uruchomione / wynik / wniosek.

## Tydzień 1 — decyzje

| Pole | Treść |
| --- | --- |
| Zaplanowane | Konto Azure for Students, rozmiar VM, budżet z alarmem |
| Uruchomione | Konto aktywne (kredyt studencki), maszyny `Standard_B2ats_v2` |
| Wynik | EU: `polandcentral`, „US”: `denmarkeast` (Azure for Students nie daje USA — ten sam mechanizm) |
| Wniosek | Da się ruszać z dwoma regionami na kredytach; prawdziwy East US zostaje na później |

## Tydzień 2 — F1/F3 pierwszy stos EU

| Pole | Treść |
| --- | --- |
| Zaplanowane | Przepis regionu + pierwszy stos w Europie (3 kontenery, healthcheck, baza bez internetu) |
| Uruchomione | `compose.yaml` + `deploy/deploy.sh eu` |
| Wynik | Health EU: `/healthz`, frontend `:3000`, API `:8000` (lokalnie) / tunele Cloudflare (publicznie) |
| Wniosek | Jeden skrypt stawia region; nie trzeba ręcznie kleić compose |

## Tydzień 3 — F1/F3 drugi region US

| Pole | Treść |
| --- | --- |
| Zaplanowane | Ten sam przepis z plikiem US, osobna baza, te same obrazy |
| Uruchomione | `deploy/deploy.sh us` → projekt `playlink-us`, porty `:3001` / `:8001` lokalnie |
| Wynik | Oba healthchecki żywe; różnica tylko w parametrze regionu i URL-ach |
| Wniosek | Trzeci region = kolejny plik parametrów, bez zmiany architektury |

## Tydzień 4 — F3 CI / rollout

| Pole | Treść |
| --- | --- |
| Zaplanowane | Ten sam commit na EU, potem US; wolumen bazy zostaje |
| Uruchomione | Release → GHCR; na VM `deploy/update.sh` (timer ~2 min), rollback przy złym health |
| Wynik | Tag `vX.Y.Z` wdraża obrazy; US czeka aż EU raportuje wersję |
| Wniosek | Pull-based update wystarcza zamiast ręcznego SSH na oba hosty |

## Tydzień 5 — F2 routing

| Pole | Treść |
| --- | --- |
| Zaplanowane | Sonda przed lobby, zapis regionu, **propozycja** zmiany, failover tylko gdy zapisany milczy, drugi login tym samym mnemonicem |
| Uruchomione | `RegionChooser` + cookie `playlink.region` + baner `RegionProposalBanner`; demo `?propose=1` |
| Wynik | Pierwsze wejście → szybszy żywy region; zapisany żywy + drugi szybszy → Stay/Switch (bez auto); zapisany offline → failover; sesje osobne per region |
| Wniosek | Reguła z wizji trzymana: szybszy drugi region nie przełącza sam |

## Tydzień 6 — F2 weryfikacja

| Pole | Treść |
| --- | --- |
| Zaplanowane | Wejście „z EU i US”, ręczna zmiana, brak samoczynnego skoku lobby, czasy sondy, zapis po odświeżeniu |
| Uruchomione | Lokalnie: `bash scripts/local-up.sh --both`; publicznie: hosty z runbooka; link `→ USA` / `→ Europa` w layoutcie |
| Wynik | Ręczny switch działa; odświeżenie nie zmienia regionu bez propozycji/akceptacji; cookie przeżywa reload |
| Wniosek | Do odbioru tygodnia 6 wystarczą zrzuty choosera, banera i dwóch loginów (EU/US). F4 obciążenie = tydzień 7 |

## Tydzień 7 — F4 eksperyment 1 vs 2 regiony

| Pole | Treść |
| --- | --- |
| Zaplanowane | Wariant A (wszyscy → EU) vs B (wybór EU/US); scenariusze: lista, pokój, join, czat WS, update listy; tabela p50/p95 |
| Uruchomione | `experiments/f4/` — `python run.py` (AsyncClient, błędy/429 w raporcie); lokalny start: `scripts/local-up.sh` |
| Wynik | Pliki `experiments/f4/results/run-*.json` + `.md` (po lokalnym lub publicznym odpaleniu) |
| Wniosek | Lokalnie metoda działa; sensowny Δ RTT dopiero na publicznych EU/US albo generatorach w dwóch lokalizacjach. Hipotezy H1/H2 z wizji uzupełnić po odczycie tabeli |

```bash
bash scripts/local-up.sh --both --lab-limits
cd experiments/f4 && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && python run.py
```

## Tydzień 8 — F5 próby awarii i F7 logi/metryki

| Pole | Treść |
| --- | --- |
| Zaplanowane | Scenariusze awarii regionu (backend, tunel, baza) oraz wspólny podgląd logów i zużycia zasobów obu regionów |
| Uruchomione | Procedury awarii w `docs/operations/runbook-regions.md`; stos `compose.observability.yaml` na osobnej VM `playlink-ops`; Vector i cAdvisor w regionach (PR 99) |
| Wynik | Backend loguje JSON z `request_id` i zdarzeniami (`room_created`, `login`, …), wystawia `/metrics`; błędy frontendu trafiają do tych samych logów; Grafana pokazuje oba regiony; dostęp do Grafany przez Cloudflare Access (jednorazowy kod e-mail) |
| Wniosek | Cały stos obserwowalności mieści się na VM 1 GB (ok. 350 MB) i nie wymaga kont zewnętrznych; próby awarii F5 są opisane, ale pomiary czasów odzyskania zostają do wykonania |

## Tydzień 9 — MCP i wydanie rc.2

| Pole | Treść |
| --- | --- |
| Zaplanowane | Inspekcja platformy przez asystentów AI oraz wydanie z całym kodem z `main` na oba regiony |
| Uruchomione | Serwer MCP `backend/mcp_server` (PR 96, 97): gry, pokoje, zdrowie regionów, dynamiczna lista regionów; narzędzia `search_logs` i `query_metrics` (PR 99); tag `v0.2.0-rc.2` wdrożony pull-based na EU, potem US |
| Wynik | MCP uruchomiony lokalnie łączy się z produkcją na Azure (`PLAYLINK_DOMAIN`, `PLAYLINK_REGIONS`) i zwraca zdrowie obu regionów, gry i logi, a zapytania o metryki wykonują się bez błędu; instrukcja dla Linux/macOS/Windows w `README.md` (PR 102) |
| Wniosek | Asystent AI może odpowiadać na pytania o stan platformy bez dostępu do serwerów; hasło do logów (`OBS_PASSWORD`) jest jednym wspólnym sekretem, więc po oddaniu projektu należy je zmienić |

## Jak odpalić lokalnie (bez Cloudflare)

```bash
bash scripts/local-up.sh          # tylko EU
bash scripts/local-up.sh --both   # EU + US
```

- Chooser: http://127.0.0.1:3000
- EU: http://localhost:3000/rooms — API http://localhost:8000
- US: http://localhost:3001/rooms — API http://localhost:8001
- Demo proposal: http://127.0.0.1:3000/?propose=1
- Demo mnemonic: `test test test test test test test test test test test junk`
