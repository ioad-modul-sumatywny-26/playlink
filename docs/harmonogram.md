# Harmonogram realizacji projektu Playlink

Czas realizacji: 15 tygodni | Zespół: 5 osób | Stos technologiczny: FastAPI, SvelteKit, PostgreSQL, Docker Compose

Realizacja projektu Playlink obejmowała 15 tygodni pracy podzielonej na sześć faz: analizę i planowanie, projektowanie rozwiązania, implementację MVP, rozwój funkcji czasu rzeczywistego, bezpieczeństwo i stabilizację oraz testowanie, wdrożenie i finalizację. Prace nad testami, dokumentacją i automatyzacją CI/CD prowadzono iteracyjnie przez cały czas trwania projektu — w harmonogramie przypisano je do tygodni, w których stanowiły główny obszar prac lub podlegały finalizacji.

Wersja PDF: [project implementation schedule.pdf](project%20implementation%20schedule.pdf).

## Harmonogram tygodniowy

| Faza | Tydzień | Zadania |
| --- | --- | --- |
| **Faza 1** Analiza i planowanie | Tydzień 1 | Określenie celu i zakresu projektu; analiza istniejących platform LFG; identyfikacja potrzeb użytkowników oraz ograniczeń dostępnych rozwiązań. |
| | Tydzień 2 | Opracowanie wymagań funkcjonalnych i niefunkcjonalnych; określenie zakresu MVP; podział ról i odpowiedzialności w pięcioosobowym zespole. |
| | Tydzień 3 | Przygotowanie backlogu i GitHub Issues; wybór technologii; opracowanie harmonogramu, kryteriów akceptacji i zasad pracy z repozytorium. **Kamień milowy: zatwierdzenie założeń projektu.** |
| **Faza 2** Projektowanie rozwiązania | Tydzień 4 | Zaprojektowanie architektury FastAPI–SvelteKit–PostgreSQL; określenie komunikacji REST i WebSocket; przygotowanie struktury repozytorium i środowiska Docker Compose. |
| | Tydzień 5 | Projekt modelu danych, przepływu uwierzytelniania BIP39/ECDSA i sesji JWT; projekt głównych widoków, ścieżek użytkownika oraz stylistyki interfejsu. **Kamień milowy: gotowość projektu do implementacji.** |
| **Faza 3** Implementacja MVP | Tydzień 6 | Utworzenie szkieletu backendu FastAPI i frontendu SvelteKit; konfiguracja zależności, formatowania, kontroli jakości, podstawowego CI/CD oraz uruchamiania usług w kontenerach. |
| | Tydzień 7 | Implementacja bazy danych, migracji Alembic i uwierzytelniania bezhasłowego; obsługa użytkowników, nonce, podpisu ECDSA i bezpiecznej sesji JWT. |
| | Tydzień 8 | Implementacja tworzenia, przeglądania, dołączania i opuszczania pokoi; integracja frontendu z API; dynamiczny katalog gier. **Kamień milowy: działająca wersja MVP.** |
| **Faza 4** Realtime i rozwój funkcjonalności | Tydzień 9 | Implementacja aktualizowanej w czasie rzeczywistym listy pokoi oraz obsługi połączeń WebSocket, ponawiania połączenia i synchronizacji stanu. |
| | Tydzień 10 | Implementacja czatu pokojowego, historii wiadomości i listy uczestników; walidacja dostępu użytkownika do pokoju i obsługa rozłączeń. |
| | Tydzień 11 | Rozszerzenie pokoi o metadane, lokalizację lobby, ping, filtrowanie, harmonogram wydarzeń i RSVP; dopracowanie responsywnego interfejsu w stylistyce retro. **Kamień milowy: pełna wersja funkcjonalna.** |
| **Faza 5** Bezpieczeństwo, administracja i stabilizacja | Tydzień 12 | Implementacja roli administratora, zarządzania pokojami i katalogiem gier, podglądu administracyjnego oraz usuwania uczestników; zabezpieczenie operacji po stronie backendu. |
| | Tydzień 13 | Dodanie podpisów kryptograficznych wiadomości, rate limitingu i automatycznego usuwania wygasłych pokoi; poprawki UX, obsługi błędów i stabilności realtime. **Kamień milowy: zamknięcie zakresu funkcjonalnego.** |
| **Faza 6** Testowanie, wdrożenie i finalizacja | Tydzień 14 | Testy backendu i frontendu, testy integracyjne oraz walidacja migracji PostgreSQL; usuwanie regresji; rozbudowa CI/CD o automatyczne testy i końcową walidację procesu wdrożenia. |
| | Tydzień 15 | Testy akceptacyjne, końcowy przegląd jakości i bezpieczeństwa; uzupełnienie dokumentacji technicznej i użytkowej; uporządkowanie repozytorium oraz przygotowanie prezentacji. **Kamień milowy: oddanie i wdrożenie projektu.** |

## Kamienie milowe i kluczowe wskaźniki efektywności

### Faza 1: Analiza i planowanie (tygodnie 1–3)

- **Kompletność wymagań** — opisanie minimum 10 wymagań funkcjonalnych i 5 niefunkcjonalnych.
- **Analiza rynku** — porównanie co najmniej 3 istniejących rozwiązań LFG.
- **Gotowość organizacyjna** — przypisanie ról wszystkim członkom zespołu i utworzenie backlogu prac.

**KPI:** wymagania, zakres MVP, podział ról i harmonogram zostały opisane oraz zaakceptowane przez zespół.

**Kamień milowy:** zakończenie analizy i zatwierdzenie planu realizacji.

### Faza 2: Projektowanie rozwiązania (tygodnie 4–5)

- **Kompletność projektu technicznego** — opis architektury, modelu danych, komunikacji i mechanizmu uwierzytelniania.
- **Zgodność z założeniami projektu** — architektura i zakres rozwiązania odpowiadają wymaganiom projektowym oraz wytycznym prowadzącego.
- **Gotowość implementacyjna** — działające szkielety usług i lokalne środowisko kontenerowe.

**KPI:** wszystkie główne komponenty mają zdefiniowane odpowiedzialności i interfejsy; brak nierozstrzygniętych blokad architektonicznych.

**Kamień milowy:** zaakceptowana architektura i gotowość do rozpoczęcia implementacji.

### Faza 3: Implementacja MVP (tygodnie 6–8)

- **Realizacja MVP** — ukończenie funkcji zakwalifikowanych do podstawowej wersji aplikacji.
- **Funkcje podstawowe** — działające logowanie, tworzenie, przeglądanie, dołączanie i opuszczanie pokoi.
- **Jakość integracji** — poprawna komunikacja frontendu, backendu i bazy danych w środowisku Docker Compose.

**KPI:** działająca wersja demonstracyjna obejmuje logowanie oraz pełny podstawowy cykl obsługi pokoi.

**Kamień milowy:** uruchomiona i możliwa do demonstracji wersja MVP.

### Faza 4: Realtime i rozwój funkcjonalności (tygodnie 9–11)

- **Funkcje realtime** — działająca synchronizacja listy pokoi, czat i aktualizacja listy uczestników.
- **Czas aktualizacji** — manualne testy w standardowych warunkach oraz w obciążonej sieci uczelnianej eduroam potwierdziły czas aktualizacji poniżej założonego limitu 1000 ms.
- **Rozszerzenie domeny** — działające wydarzenia, RSVP, metadane pokoi, lokalizacja lobby i filtrowanie.

**KPI:** zaplanowane funkcje realtime zostały zaimplementowane, a wyniki testów manualnych spełniły wymaganie czasu aktualizacji poniżej 1000 ms.

**Kamień milowy:** zakończenie implementacji pełnej wersji funkcjonalnej.

### Faza 5: Bezpieczeństwo, administracja i stabilizacja (tygodnie 12–13)

- **Bezpieczeństwo** — uwierzytelnione operacje administracyjne, rate limiting i weryfikacja podpisów wiadomości.
- **Stabilność** — prawidłowa obsługa rozłączeń, ponownych połączeń, wygasania pokoi i błędów transmisji.
- **Użyteczność** — brak elementów niedostępnych na typowych rozdzielczościach; zachowanie funkcjonalnego czatu przy rozbudowanym widoku pokoju.

**KPI:** wszystkie operacje administracyjne są chronione autoryzacją po stronie backendu; na zakończenie projektu w repozytorium nie pozostały otwarte zgłoszenia błędów krytycznych ani blokujących.

**Kamień milowy:** zamrożenie zakresu i gotowość do testów końcowych.

### Faza 6: Testowanie, wdrożenie i finalizacja (tygodnie 14–15)

- **Pokrycie kodu** — pokrycie linii kodu backendu przekracza próg 80% egzekwowany przez CI.
- **Testy automatyczne** — zestaw testów backendu zakończył się powodzeniem; CI obejmuje również testy frontendu, linting, budowanie obrazów i walidację migracji PostgreSQL.
- **Jakość wydania** — 100% zaplanowanych GitHub Issues zostało zrealizowanych; w chwili finalizacji nie pozostały otwarte zgłoszenia.
- **Wdrożenie** — aplikacja jest automatycznie budowana i wdrażana po zmianach w gałęzi `main`.
- **Dokumentacja** — kompletna dokumentacja architektury, API, modelu danych, konfiguracji, testów i wdrożenia.

**KPI:** 100% zaplanowanych GitHub Issues zrealizowanych; wymagana dokumentacja ukończona; wersja produkcyjna dostępna i możliwa do zaprezentowania.

**Kamień milowy:** odbiór końcowy, akceptacja przez prowadzącego, wdrożenie i zakończenie projektu.

## Podsumowanie kamieni milowych

| Tydzień | Kamień milowy |
| --- | --- |
| Tydzień 3 | Zatwierdzone wymagania, zakres MVP i plan realizacji. |
| Tydzień 5 | Zakończone projektowanie architektury i interfejsu. |
| Tydzień 8 | Działająca wersja MVP. |
| Tydzień 11 | Pełna wersja funkcjonalna z komunikacją realtime. |
| Tydzień 13 | Zamknięcie zakresu, stabilizacja i gotowość do testów końcowych. |
| Tydzień 15 | Wdrożenie, kompletna dokumentacja i oddanie projektu. |

## Osiągnięte KPI projektu

- **Realizacja zadań:** zrealizowano 100% zaplanowanych GitHub Issues.
- **Jakość wydania:** w chwili oddania nie pozostały otwarte zgłoszenia błędów krytycznych ani blokujących.
- **Realtime:** manualne testy w różnych warunkach sieciowych potwierdziły czas aktualizacji poniżej wymaganego limitu 1000 ms.
- **Testy backendu:** zestaw testów zakończył się powodzeniem, a pokrycie linii kodu przekracza wymagany próg 80%.
- **Dokumentacja i odbiór:** wymagana dokumentacja została ukończona, a finalna wersja projektu zaakceptowana przez prowadzącego.
- **Wdrożenie:** działająca wersja produkcyjna oraz dokumentacja API są publicznie dostępne; proces budowania, testowania i wdrażania jest obsługiwany przez CI/CD.
