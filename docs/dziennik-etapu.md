# Dziennik etapu (tygodnie 1–6)

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
| Uruchomione | Lokalnie: `.\start-local.ps1 -Both`; publicznie: hosty z runbooka; link `→ USA` / `→ Europa` w layoutcie |
| Wynik | Ręczny switch działa; odświeżenie nie zmienia regionu bez propozycji/akceptacji; cookie przeżywa reload |
| Wniosek | Do odbioru tygodnia 6 wystarczą zrzuty choosera, banera i dwóch loginów (EU/US). F4 obciążenie = tydzień 7 |

## Jak odpalić lokalnie (bez Cloudflare)

```powershell
.\start-local.ps1          # tylko EU
.\start-local.ps1 -Both    # EU + US
```

- Chooser: http://127.0.0.1:3000
- EU: http://localhost:3000/rooms — API http://localhost:8000
- US: http://localhost:3001/rooms — API http://localhost:8001
- Demo proposal: http://127.0.0.1:3000/?propose=1
- Demo mnemonic: `test test test test test test test test test test test junk`
