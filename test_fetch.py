import asyncio
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import fetch
from librus_synergia.models import LessonData, OriginalLessonData
from librus_synergia.exceptions import LibrusCaptchaRequiredError


class PublicationTests(unittest.TestCase):
    def test_empty_hidden_captcha_placeholder_is_not_a_challenge(self):
        fetch.check_captcha('<input type="password"><div id="login-limit-exceeded-recaptcha-view" class="d-none"></div>', "fixture")
        fetch.check_captcha('<button onclick="loginLimitExceededReCaptchaView()">Back</button><div class="d-none" id="login-limit-exceeded-recaptcha-view"></div>', "fixture")

    def test_real_or_unknown_captcha_is_still_rejected(self):
        for html in (
            '<div id="login-limit-exceeded-recaptcha-view"></div>',
            '<div id="login-limit-exceeded-recaptcha-view" class="d-none"><iframe src="recaptcha"></iframe></div>',
            '<div class="g-recaptcha" data-sitekey="public"></div>',
            '{"error":"captcha_required"}',
            '<div class="d-none" id="some-other-captcha"></div>',
            '<button onclick="captchaRequired()"></button>',
        ):
            with self.assertRaises(LibrusCaptchaRequiredError):
                fetch.check_captcha(html, "fixture")

    def lesson(self, **changes):
        args = dict(lesson_no=0, hour_from="08:00:00", hour_to="08:45:00",
                    subject_id=7, teacher_id="PRIVATE_TEACHER", classroom_id="PRIVATE_ROOM",
                    is_canceled=False, is_substitution=True,
                    original=OriginalLessonData(None, 0, None, None, 8, "PRIVATE", "PRIVATE"),
                    substitution_note="PRIVATE_STUDENT")
        args.update(changes)
        return LessonData(**args)

    def payload(self):
        return dict(schema_version=1, updated_at=datetime.now(fetch.TZ).isoformat(),
                    timezone="Europe/Warsaw", days={datetime.now(fetch.TZ).date().isoformat(): [
                        fetch.public_lesson(self.lesson(), {"7": "Matematyka", "8": "Fizyka"})]})

    def test_current_library_types_and_substitution(self):
        payload = self.payload()
        fetch.validate_payload(payload)
        row = next(iter(payload["days"].values()))[0]
        self.assertEqual((row["number"], row["start"], row["end"]), (0, "08:00", "08:45"))
        self.assertTrue(row["substitution"])
        self.assertEqual(row["original_subject"], "Fizyka")
        self.assertNotIn("PRIVATE", json.dumps(payload))

    def test_cancellation_and_private_subject(self):
        row = fetch.public_lesson(self.lesson(is_canceled=True), {"7": "Zajęcia z Jan Kowalski"})
        self.assertTrue(row["cancelled"])
        self.assertEqual(row["subject"], "Zajęcia")

    def test_reject_private_fields_and_bad_hours(self):
        payload = self.payload()
        for key, value in [("teacher", "PRIVATE"), ("subject", "PRIVATE"), ("start", "password")]:
            dirty = copy.deepcopy(payload)
            next(iter(dirty["days"].values()))[0][key] = value
            with self.assertRaises(ValueError):
                fetch.validate_payload(dirty)
        with self.assertRaises(ValueError):
            fetch.public_lesson(self.lesson(hour_from=None), {})

    def test_week_boundary_uses_only_required_weeks(self):
        class Sunday(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 11, 22, 23, 59, tzinfo=fetch.TZ)
        seen = []
        class FakeLibrus:
            def __init__(self, *args, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def login(self): pass
            async def subjects(self): return {}
            async def timetable(self, week):
                seen.append(week)
                return {week: []}
        with patch.object(fetch, "datetime", Sunday), patch.object(fetch, "Librus", FakeLibrus):
            result = asyncio.run(fetch.collect("placeholder", "placeholder"))
        self.assertEqual(len(seen), 2)
        self.assertEqual(set(result["days"]), {"2026-11-22", "2026-11-23"})

    def test_errors_never_log_exception_or_credentials(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(fetch, "SITE_DIR", Path(folder)), \
             patch.dict("os.environ", {"LIBRUS_LOGIN": "PRIVATE_LOGIN", "LIBRUS_PASSWORD": "PRIVATE_PASSWORD", "GITHUB_REPOSITORY": ""}):
            for error in [LibrusCaptchaRequiredError("PRIVATE_RESPONSE"), TimeoutError("PRIVATE_RESPONSE")]:
                output = io.StringIO()
                with patch.object(fetch, "collect", side_effect=error), redirect_stdout(output):
                    self.assertEqual(asyncio.run(fetch.main()), 1)
                self.assertNotIn("PRIVATE", output.getvalue())
                status = json.loads((Path(folder) / "status.json").read_text())
                self.assertFalse(status["ok"])
                self.assertFalse((Path(folder) / "plan.json").exists())

    def test_missing_secrets_fail_before_login(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(fetch, "SITE_DIR", Path(folder)), \
             patch.dict("os.environ", {"LIBRUS_LOGIN": "", "LIBRUS_PASSWORD": "", "GITHUB_REPOSITORY": ""}), \
             patch.object(fetch, "collect") as collect, redirect_stdout(io.StringIO()):
            self.assertEqual(asyncio.run(fetch.main()), 1)
            collect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
