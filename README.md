# Automatyczny plan Librus → Carrd

Plan: https://maksowodny20.github.io/plan-lekcji-maks/

Workflow `.github/workflows/plan.yml` uruchamia się na `main`, ręcznie i o minutach 7 oraz 37 każdej godziny UTC, bez włączonego komputera. GitHub może opóźniać harmonogram oraz wyłączyć go po 60 dniach bez aktywności publicznego repozytorium.

Sekrety repozytorium: `LIBRUS_LOGIN`, `LIBRUS_PASSWORD`. Skrypt sprawdza tylko ich obecność. Pages: Source = GitHub Actions. Python 3.12+, `librus-synergia==0.3.33`; zweryfikowane API `login()`, `subjects()`, `timetable(date)`, `LessonData`, `OriginalLessonData`.

Plan pokazuje dzisiaj i jutro w Europe/Warsaw: godziny, numer lekcji, przedmiot, zastępstwa i odwołania. Pobierany jest tylko wymagany tydzień albo dwa przy granicy tygodni. Nieznany dzień różni się od dnia bez lekcji.

## Bezpieczeństwo i niezawodność

- Publiczne pliki wybierane jawnie: `index.html`, `plan.json`, `status.json`, `.nojekyll`.
- Bez nazwisk, identyfikatorów, sal i komentarzy. Nazwy przedmiotów pochodzą z zamkniętego słownika; nieznane nazwy zmieniane są na „Zajęcia”.
- Walidacja formatu przed publikacją. Zapis atomowy. Zero surowych obiektów biblioteki.
- Timeout żądania 20 s, połączenia 8 s, synchronizacji 120 s, jobów 6/5 minut. Bez automatycznego ponawiania CAPTCHA lub odrzuconych haseł.
- Przy błędzie zostaje poprzedni publiczny, zweryfikowany plan dla nadal aktualnych dat i widoczny komunikat. Workflow pozostaje czerwony, nawet jeśli udało się opublikować stronę ze stanem błędu.
- Bez logowania treści wyjątków lub odpowiedzi HTTP. Diagnostyka CAPTCHA pokazuje wyłącznie HTTP i wartości logiczne, bez ciał odpowiedzi, adresów przekierowań lub cookies. Nie przechowujemy danych sesji w plikach, cache ani artefaktach.
- Widżet odświeża dane co 5 minut i po powrocie do karty. Po 90 minutach oznacza dane jako nieaktualne.

## Carrd Pro Standard lub wyższy

Embed → Type: IFRAME → URL: `https://maksowodny20.github.io/plan-lekcji-maks/`, Width: 100%, Height: 850 px, Aspect Ratio: Ignore.

Albo Embed → Code → Inline:

```html
<iframe src="https://maksowodny20.github.io/plan-lekcji-maks/" title="Plan lekcji — dzisiaj i jutro" width="100%" height="850" loading="lazy" referrerpolicy="no-referrer" style="display:block;border:0;border-radius:18px;width:100%;max-width:720px;margin:auto;"></iframe>
```

Ramka działa na opublikowanej stronie; edytor może pokazać placeholder.

## Testy bez logowania

`python -m pip install -r requirements.txt`

`python -m unittest -v`

Źródła: https://pypi.org/project/librus-synergia/0.3.33/ oraz https://carrd.com/docs/building/embedding-iframes

## Zgodność logowania Librusa

Biblioteka 0.3.33 rozpoznaje CAPTCHA po dowolnym wystąpieniu tego słowa. Zwykła publiczna strona logowania zawiera pusty element `login-limit-exceeded-recaptcha-view` z klasą `d-none`. Lokalna poprawka usuwa z kontroli wyłącznie ten dokładny pusty, ukryty element. Pozostałe znaczniki CAPTCHA oraz wymaganie poprawnej sesji nadal są sprawdzane. Nie jest używana zewnętrzna usługa rozwiązywania CAPTCHA.
