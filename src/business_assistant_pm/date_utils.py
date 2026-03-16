"""Date utilities for resolving relative due dates to absolute ISO dates.

When drafts are scheduled via Thunderbird Send Later, relative dates
like "tomorrow" would be interpreted relative to the *send* time, not
the *draft* time.  Converting to absolute ISO dates (``YYYY-MM-DD``)
ensures RTM Smart Add always receives the correct due date.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

WEEKDAY_NAMES: dict[str, int] = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def resolve_due_to_absolute(due: str, user_tz: str = "Europe/Berlin") -> str:
    """Convert a relative due-date string to an absolute ``YYYY-MM-DD``.

    Supported inputs:

    * ``"today"``  → current date
    * ``"tomorrow"`` → current date + 1
    * ``"monday"`` … ``"sunday"`` → next occurrence (today if it matches)
    * ``"next monday"`` … ``"next sunday"`` → occurrence in the coming week
    * ``"YYYY-MM-DD"`` → passthrough
    * anything else → passthrough (let RTM handle it)
    """
    today = datetime.now(ZoneInfo(user_tz)).date()
    lower = due.strip().lower()

    if lower == "today":
        return today.isoformat()

    if lower == "tomorrow":
        return (today + timedelta(days=1)).isoformat()

    # "next <weekday>"
    if lower.startswith("next ") and lower[5:] in WEEKDAY_NAMES:
        target_wd = WEEKDAY_NAMES[lower[5:]]
        days_ahead = (target_wd - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return (today + timedelta(days=days_ahead)).isoformat()

    # Bare weekday name — next occurrence, including today.
    if lower in WEEKDAY_NAMES:
        target_wd = WEEKDAY_NAMES[lower]
        days_ahead = (target_wd - today.weekday()) % 7
        return (today + timedelta(days=days_ahead)).isoformat()

    # Already an ISO date or something we don't recognise → passthrough.
    return due
