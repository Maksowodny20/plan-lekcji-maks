"""Bezpieczna publikacja samego planu lekcji z Librusa do statycznej strony.

Login i hasło: wyłącznie zmienne środowiskowe, nigdy w plikach strony.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from librus_synergia import Librus

TZ = ZoneInfo("Europe/Warsaw")
SITE_DIR = Path(__file__).resolve().parent / "site"


def lookup(table, key, fallback=""):
    return str(table.get(str(key), fallback)) if key is not None else fallback


def clean_time(value):
    return str(value)[:5] if value else ""


async def main():
    username = os.environ.get("LIBRUS_LOGIN")
    password = os.environ.get("LIBRUS_PASSWORD")    
    print("Login dostępny:", bool(username))
    print("Hasło dostępne:", bool(password))
    if not username or not password:
        raise RuntimeError("Skonfiguruj sekrety LIBRUS_LOGIN i LIBRUS_PASSWORD")

    now = datetime.now(TZ)
    monday = now.date() - timedelta(days=now.weekday())
    show_rooms = os.environ.get("SHOW_ROOMS", "false").lower() == "true"
    data = {}

    async with Librus(username, password, cache_reference_data=True) as librus:
        subjects = {str(k): str(v) for k, v in (await librus.subjects()).items()}
        classrooms = (
            {str(k): str(v) for k, v in (await librus.classrooms()).items()}
            if show_rooms else {}
        )

        for week in (monday, monday + timedelta(days=7)):
            fetched = await librus.timetable(week)
            for day, entries in fetched.items():
                day_key = day.isoformat() if hasattr(day, "isoformat") else str(day)[:10]
                lessons = []
                for lesson in entries:
                    original_subject = None
                    if lesson.original is not None:
                        original_subject = lookup(subjects, lesson.original.subject_id, "")
                    lessons.append({
                        "number": lesson.lesson_no,
                        "start": clean_time(lesson.hour_from),
                        "end": clean_time(lesson.hour_to),
                        "subject": lookup(subjects, lesson.subject_id, "Nieznany przedmiot"),
                        "room": lookup(classrooms, lesson.classroom_id, "") if show_rooms else "",
                        "cancelled": bool(lesson.is_canceled),
                        "substitution": bool(lesson.is_substitution),
                        "original_subject": original_subject,
                    })
                lessons.sort(key=lambda it: (it["start"] or "99:99", it["number"] or 999))
                data[day_key] = lessons

    payload = {
        "updated_at": now.isoformat(timespec="minutes"),
        "timezone": "Europe/Warsaw",
        "days": data,
    }
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "plan.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Zapisano plan: {len(data)} dni, aktualizacja {now:%Y-%m-%d %H:%M}")


if __name__ == "__main__":
    asyncio.run(main())
