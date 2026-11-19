"""Normal Librus form login in an ephemeral Chromium context on the CI runner.

No traces, screenshots, persistent browser profile or authentication files.
Session values stay in memory and are never included in public output.
"""
import asyncio
import time
from urllib.parse import urlsplit

from librus_synergia.client import LibrusSessionData
from librus_synergia.const import PERSISTED_COOKIE_NAMES
from librus_synergia.exceptions import (
    LibrusAccountActionRequiredError, LibrusAuthError, LibrusCaptchaRequiredError,
    LibrusConnectionError,
)


def session_from_cookies(cookies):
    selected = []
    has_session = False
    for cookie in cookies:
        domain = cookie.get("domain", "").lstrip(".")
        name = cookie.get("name")
        if name not in PERSISTED_COOKIE_NAMES.get(domain, ()):
            continue
        if cookie.get("expires", -1) not in (-1, 0) and cookie["expires"] <= time.time():
            continue
        selected.append({"name": name, "value": cookie["value"],
                         "domain": domain, "path": cookie.get("path", "/")})
        has_session |= domain == "synergia.librus.pl" and name == "oauth_token"
    if not has_session:
        raise LibrusAuthError("No authenticated browser session")
    return LibrusSessionData(cookies=selected, logged_in_at=time.time())


def is_login_response(response):
    target = urlsplit(response.url)
    return (target.scheme == "https" and target.hostname == "api.librus.pl"
            and target.path == "/OAuth/Authorization" and response.request.method == "POST")


async def browser_session(username, password):
    from playwright.async_api import async_playwright, Error as BrowserError, TimeoutError as BrowserTimeoutError

    print("Etap: zwykły formularz logowania w Chromium na serwerze.", flush=True)
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                context = await browser.new_context(accept_downloads=False, service_workers="block")
                page = await context.new_page()
                page.set_default_timeout(12000)
                # The current portal is a client-side app: its Synergia link
                # creates an iframe with layout_version=2. Navigating directly
                # to the legacy URL returns to the home page in a real browser.
                await page.goto("https://portal.librus.pl/rodzina", wait_until="domcontentloaded", timeout=25000)
                target = urlsplit(page.url)
                allowed = {"api.librus.pl", "synergia.librus.pl", "portal.librus.pl"}
                origin = target.hostname if target.hostname in allowed else "other"
                print(f"Chromium: dokument logowania gotowy, host={origin}.", flush=True)
                if target.scheme != "https" or target.hostname not in allowed:
                    raise LibrusAuthError("Unexpected login origin")
                try:
                    advanced = page.get_by_role("button", name="Ustawienia zaawansowane", exact=True)
                    await advanced.wait_for(state="visible", timeout=6000)
                except BrowserTimeoutError:
                    pass
                else:
                    await advanced.click()
                    await page.get_by_role("button", name="Zapisz", exact=True).click()
                    print("Chromium: wybrano wyłącznie niezbędne cookies portalu.", flush=True)
                await page.get_by_role("button", name="LIBRUS Synergia", exact=True).click()
                await page.locator('a[href$="/rodzina/synergia/loguj"]').click()
                print("Chromium: otwarto szkolny formularz z menu portalu.", flush=True)
                frame = None
                deadline = time.monotonic() + 15
                while frame is None and time.monotonic() < deadline:
                    for candidate in page.frames:
                        location = urlsplit(candidate.url)
                        if location.scheme == "https" and location.hostname == "api.librus.pl":
                            if await candidate.locator("#Login").count():
                                frame = candidate
                                break
                    if frame is None:
                        await asyncio.sleep(0.5)
                if frame is None:
                    print("Chromium: brak formularza na dozwolonej domenie API.", flush=True)
                    raise LibrusAuthError("No login form on approved origin")
                print("Chromium: znaleziono formularz na domenie API.", flush=True)
                await frame.locator("#Login").fill(username)
                await frame.locator("#Pass").fill(password)
                # A real, visible challenge needs user interaction. Never solve,
                # suppress or bypass it. The hidden empty placeholder is inert.
                for widget in await frame.locator('[data-sitekey], iframe[src*="recaptcha"], iframe[src*="hcaptcha"]').all():
                    if await widget.is_visible():
                        raise LibrusCaptchaRequiredError("Interactive challenge required")
                async with page.expect_response(is_login_response, timeout=20000) as pending:
                    await frame.locator("#LoginBtn").click()
                response = await pending.value
                try:
                    result = await response.json()
                except ValueError:
                    raise LibrusAuthError("Unexpected form response") from None
                status = result.get("status") if isinstance(result, dict) else None
                safe_status = status if status in ("ok", "error", "actionRequired", "clientRestrictionsFailed") else "other"
                print(f"Chromium: odpowiedź formularza HTTP={response.status}, status={safe_status}.", flush=True)
                if status == "actionRequired":
                    raise LibrusAccountActionRequiredError("Account action required")
                if status != "ok":
                    raise LibrusAuthError("Login form did not accept sign-in")
                print("Chromium: formularz przyjął logowanie; oczekiwanie na sesję.", flush=True)
                deadline = time.monotonic() + 35
                while time.monotonic() < deadline:
                    try:
                        data = session_from_cookies(await context.cookies())
                        print("Chromium: sesja utworzona; przekazanie do API w pamięci.", flush=True)
                        return data, await page.evaluate("navigator.userAgent")
                    except LibrusAuthError:
                        await asyncio.sleep(0.5)
                raise LibrusAccountActionRequiredError("Browser verification did not complete")
            finally:
                await browser.close()
    except (LibrusAuthError, LibrusConnectionError):
        raise
    except BrowserError:
        # Playwright exceptions can contain form values in action call logs.
        raise LibrusConnectionError("Browser sign-in could not finish") from None
