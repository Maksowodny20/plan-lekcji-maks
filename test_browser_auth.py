import time
import unittest
from types import SimpleNamespace

from browser_auth import is_login_response, session_from_cookies
from librus_synergia.exceptions import LibrusAuthError


class BrowserPrivacyTests(unittest.TestCase):
    def test_only_librus_authentication_cookies_are_transferred(self):
        cookies = [
            {"name": "oauth_token", "domain": ".synergia.librus.pl", "value": "PRIVATE_SESSION", "path": "/", "expires": -1},
            {"name": "DeviceCookie", "domain": "api.librus.pl", "value": "PRIVATE_DEVICE", "path": "/OAuth", "expires": time.time() + 100},
            {"name": "teacher_name", "domain": "synergia.librus.pl", "value": "PRIVATE_PERSON"},
            {"name": "oauth_token", "domain": "untrusted.example", "value": "UNTRUSTED"},
        ]
        data = session_from_cookies(cookies)
        self.assertEqual([row["name"] for row in data.cookies], ["oauth_token", "DeviceCookie"])
        self.assertTrue(all(set(row) == {"name", "value", "domain", "path"} for row in data.cookies))

    def test_missing_or_expired_session_is_never_accepted(self):
        for cookies in ([], [{"name": "oauth_token", "domain": "synergia.librus.pl", "value": "expired", "expires": time.time() - 30}]):
            with self.assertRaises(LibrusAuthError):
                session_from_cookies(cookies)

    def test_login_response_requires_exact_secure_origin(self):
        def response(url, method="POST"):
            return SimpleNamespace(url=url, request=SimpleNamespace(method=method))
        self.assertTrue(is_login_response(response("https://api.librus.pl/OAuth/Authorization?client_id=46")))
        for url in ("http://api.librus.pl/OAuth/Authorization", "https://api.librus.pl.evil.example/OAuth/Authorization", "https://api.librus.pl/other"):
            self.assertFalse(is_login_response(response(url)))
        self.assertFalse(is_login_response(response("https://api.librus.pl/OAuth/Authorization", "GET")))


if __name__ == "__main__":
    unittest.main()
