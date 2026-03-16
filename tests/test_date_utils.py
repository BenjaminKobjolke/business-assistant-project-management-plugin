"""Tests for date_utils — relative-to-absolute due date resolution."""

from __future__ import annotations

from unittest.mock import patch

from business_assistant_pm.date_utils import resolve_due_to_absolute


def _mock_today(year: int, month: int, day: int):
    """Patch datetime.now to return a fixed date in Europe/Berlin."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    fixed = datetime(year, month, day, 12, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    return patch(
        "business_assistant_pm.date_utils.datetime",
        wraps=__import__("datetime").datetime,
        **{"now.return_value": fixed},
    )


class TestResolveDueToAbsolute:
    """Tests for resolve_due_to_absolute."""

    def test_today(self) -> None:
        with _mock_today(2026, 3, 15):  # Sunday
            assert resolve_due_to_absolute("today") == "2026-03-15"

    def test_today_case_insensitive(self) -> None:
        with _mock_today(2026, 3, 15):
            assert resolve_due_to_absolute("Today") == "2026-03-15"

    def test_tomorrow(self) -> None:
        with _mock_today(2026, 3, 15):  # Sunday
            assert resolve_due_to_absolute("tomorrow") == "2026-03-16"

    def test_weekday_same_day(self) -> None:
        # 2026-03-16 is Monday (weekday=0)
        with _mock_today(2026, 3, 16):
            assert resolve_due_to_absolute("monday") == "2026-03-16"

    def test_weekday_future(self) -> None:
        # 2026-03-18 is Wednesday (weekday=2), next Friday is 2026-03-20
        with _mock_today(2026, 3, 18):
            assert resolve_due_to_absolute("friday") == "2026-03-20"

    def test_weekday_past_wraps_to_next_week(self) -> None:
        # 2026-03-18 is Wednesday (weekday=2), next Monday is 2026-03-23
        with _mock_today(2026, 3, 18):
            assert resolve_due_to_absolute("monday") == "2026-03-23"

    def test_next_weekday(self) -> None:
        # 2026-03-16 is Monday, "next monday" → 2026-03-23 (skip this week)
        with _mock_today(2026, 3, 16):
            assert resolve_due_to_absolute("next monday") == "2026-03-23"

    def test_next_weekday_different_day(self) -> None:
        # 2026-03-18 is Wednesday, "next friday" → 2026-03-20 (coming this week)
        with _mock_today(2026, 3, 18):
            assert resolve_due_to_absolute("next friday") == "2026-03-20"

    def test_next_weekday_past_day(self) -> None:
        # 2026-03-20 is Friday, "next wednesday" → 2026-03-25
        with _mock_today(2026, 3, 20):
            assert resolve_due_to_absolute("next wednesday") == "2026-03-25"

    def test_iso_date_passthrough(self) -> None:
        assert resolve_due_to_absolute("2026-03-20") == "2026-03-20"

    def test_unknown_passthrough(self) -> None:
        assert resolve_due_to_absolute("in 3 days") == "in 3 days"

    def test_whitespace_trimmed(self) -> None:
        with _mock_today(2026, 3, 15):
            assert resolve_due_to_absolute("  today  ") == "2026-03-15"

    def test_all_weekday_names(self) -> None:
        # 2026-03-16 is Monday
        with _mock_today(2026, 3, 16):
            assert resolve_due_to_absolute("monday") == "2026-03-16"
            assert resolve_due_to_absolute("tuesday") == "2026-03-17"
            assert resolve_due_to_absolute("wednesday") == "2026-03-18"
            assert resolve_due_to_absolute("thursday") == "2026-03-19"
            assert resolve_due_to_absolute("friday") == "2026-03-20"
            assert resolve_due_to_absolute("saturday") == "2026-03-21"
            assert resolve_due_to_absolute("sunday") == "2026-03-22"

    def test_sunday_tomorrow_gives_monday(self) -> None:
        """The key use case: Sunday, due 'tomorrow' → Monday ISO date."""
        with _mock_today(2026, 3, 15):  # Sunday
            result = resolve_due_to_absolute("tomorrow")
            assert result == "2026-03-16"  # Monday
