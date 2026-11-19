# Librus → plan lekcji na Carrd Pro

Gotowy widżet osadzany w Carrd. Jest wyświetlany **wewnątrz** Twojej strony Carrd (przez IFRAME), ale bezpieczna synchronizacja z Librusem odbywa się w GitHub Actions. Sam Carrd nie przechowuje loginu ani hasła.

**Wymagania:** konto Librus Synergia, Carrd Pro Standard/Plus, darmowe konto GitHub. Nie musisz trzymać komputera włączonego.

## Konfiguracja

1. Załóż na https://github.com/new repozytorium o nazwie np. `moj-plan-librus` (najprościej **Public**). Gałąź główna: `main`.
2. Wgraj **zawartość rozpakowanego folderu**, wraz z ukrytym katalogiem `.github` (czyli `fetch.py`, `site/index.html`, `.github/workflows/plan.yml`, `README.md`). Najłatwiej zrobić to z GitHub Desktop lub przez `git`.
3. W repozytorium przejdź do **Settings → Secrets and variables → Actions → New repository secret**. Dodaj dwa sekrety: `LIBRUS_LOGIN` i `LIBRUS_PASSWORD`. Wartości wpisz **wyłącznie tam**. Nie wysyłaj ich do czatu, nie wpisuj do kodu ani nie publikuj.
4. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
5. **Actions → Odśwież plan z Librusa → Run workflow**. Po sukcesie strona będzie pod adresem zbliżonym do `https://TWOJ-LOGIN.github.io/moj-plan-librus/`.
6. W edytorze Carrd: **+ → Embed → Type: IFRAME → URL**: adres z kroku 5. Wybierz szerokość 100%, wysokość np. **750 px**, zapisz i opublikuj stronę. W razie potrzeby dostosuj wysokość, by uniknąć przewijania wewnątrz ramki.

## Wariant zamiast IFRAME

Możesz osadzić w Carrd element `Embed → Code → Inline` z kodem `<iframe src="https://TWOJ-LOGIN.github.io/moj-plan-librus/" title="Plan lekcji" style="border:0;width:100%;height:750px;border-radius:18px;"></iframe>`.

## Automatyzacja

GitHub Actions uruchamia pobieranie co około 30 minut od 05:07 do 20:37 UTC (plus na żądanie). Harmonogram GitHub może się opóźniać, a Librus może zmienić sposób logowania. Przy błędzie poprzednio opublikowana wersja pozostaje widoczna i może być nieaktualna — sprawdź datę aktualizacji widżetu.

Widżet pokazuje dzień dzisiejszy, jutrzejszy i następne 7 dni oraz status lekcji odwołanych/zastępstw. Bezpośrednio z Librusa pobiera dwa tygodnie planu. **Nie pobiera ocen, wiadomości ani danych osobowych** do publicznej strony.

## Prywatność

Strona GitHub Pages jest publiczna. Każdy, kto zna jej adres lub widzi Twoją witrynę Carrd, może zobaczyć opublikowane lekcje. **Sale są domyślnie ukryte**, tak samo jak imiona nauczycieli. Jeśli świadomie chcesz ujawniać numery sal, w `.github/workflows/plan.yml` zmień `SHOW_ROOMS: 'false'` na `'true'`.

### Problemy

- `LIBRUS_LOGIN` lub `LIBRUS_PASSWORD` missing: sprawdź repo secrets.
- Błąd logowania / CAPTCHA: nieoficjalna biblioteka zależy od zmian w Librusie, więc może potrzebować aktualizacji albo zmiany hostingu.
- Brak nowego planu: GitHub Actions czasem opóźnia harmonogram; uruchom workflow ręcznie, sprawdź status.
- Nic nie widać w edytorze Carrd: element IFRAME wyświetla się na opublikowanej stronie, nie zawsze w edytorze.

Źródła: https://carrd.com/docs/building/embedding-iframes oraz https://pypi.org/project/librus-synergia/
