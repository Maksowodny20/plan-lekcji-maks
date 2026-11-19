"""Normal Librus form login in an ephemeral Chromium context on the CI runner.

No traces, screenshots, persistent browser profile or authentication files.
Session values stay in memory and are never included in public output.
"""
import asyncio
import time
from urllib.parse import urlsplit, urljoin

from librus_synergia.client import LibrusSessionData
from librus_synergia.const import PERSISTED_COOKIE_NAMES, SYNERGIA_PORTAL_LOGIN_URL, USER_AGENT
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


def is_authorization_url(url):
    try:
        target = urlsplit(url)
        return (target.scheme == "https" and target.hostname == "api.librus.pl"
                and target.port in (None, 443) and target.username is None
                and target.password is None and target.path == "/OAuth/Authorization")
    except ValueError:
        return False


async def browser_session(username, password):
    from playwright.async_api import async_playwright, Error as BrowserError

    print("Etap: zwykły formularz logowania w Chromium na serwerze.", flush=True)
    phase = "start"
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel="chrome", headless=True)
            try:
                context = await browser.new_context(accept_downloads=False, user_agent=USER_AGENT)
                page = await context.new_page()
                page.set_default_timeout(12000)
                # Bootstrap the documented OAuth entry point as an API request.
                # context.request shares cookies with the real Chrome page.
                # This avoids the unrelated portal home-page SPA redirect.
                phase = "oauth_bootstrap"
                bootstrap_url = SYNERGIA_PORTAL_LOGIN_URL + "?layout_version=2"
                bootstrap = await context.request.get(bootstrap_url,
                    max_redirects=0, timeout=20000)
                print(f"Chrome: inicjalizacja OAuth HTTP={bootstrap.status}.", flush=True)
                location = bootstrap.headers.get("location")
                if not location:
                    raise LibrusConnectionError("OAuth entry point did not redirect")
                authorization_url = urljoin(SYNERGIA_PORTAL_LOGIN_URL, location)
                if not is_authorization_url(authorization_url):
                    raise LibrusAuthError("Unexpected OAuth destination")
                await bootstrap.dispose()
                phase = "authorization_page"
                response = await page.goto(authorization_url, wait_until="domcontentloaded", timeout=25000)
                target = urlsplit(page.url)
                allowed = {"api.librus.pl", "synergia.librus.pl"}
                origin = target.hostname if target.hostname in allowed else "other"
                print(f"Chromium: dokument logowania gotowy, host={origin}, HTTP={response.status if response else 0}.", flush=True)
                if target.scheme != "https" or target.hostname not in allowed:
                    raise LibrusAuthError("Unexpected login origin")
                frame = None
                phase = "school_frame"
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
                    current = urlsplit(page.url).hostname
                    current = current if current in {"api.librus.pl", "synergia.librus.pl", "portal.librus.pl"} else "other"
                    print(f"Chromium: brak formularza na dozwolonej domenie API, aktualny_host={current}.", flush=True)
                    raise LibrusAuthError("No login form on approved origin")
                print("Chromium: znaleziono formularz na domenie API.", flush=True)
                phase = "school_form"
                await frame.locator("#Login").fill(username)
                await frame.locator("#Pass").fill(password)
                # A real, visible challenge needs user interaction. Never solve,
                # suppress or bypass it. The hidden empty placeholder is inert.
                for widget in await frame.locator('[data-sitekey], iframe[src*="recaptcha"], iframe[src*="hcaptcha"]').all():
                    if await widget.is_visible():
                        raise LibrusCaptchaRequiredError("Interactive challenge required")
                phase = "form_submit"
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
                phase = "authenticated_session"
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
    except BrowserError as error:
        # Playwright exceptions can contain form values in action call logs.
        print(f"Chromium: niedokończony etap={phase}, typ={type(error).__name__}.", flush=True)
        raise LibrusConnectionError("Browser sign-in could not finish") from None
