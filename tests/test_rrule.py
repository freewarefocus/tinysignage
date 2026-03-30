"""Tests for _rrule_matches_date() from app/api/schedules.py.

Feature tree refs: [FT-7.16]
"""

from datetime import datetime

from app.api.schedules import _rrule_matches_date


def test_daily_matches_any_day():
    check = datetime(2026, 3, 29)  # Sunday
    assert _rrule_matches_date("FREQ=DAILY", check, None) is True


def test_daily_interval_2():
    start = datetime(2026, 1, 1)
    assert _rrule_matches_date("FREQ=DAILY;INTERVAL=2", datetime(2026, 1, 1), start) is True
    assert _rrule_matches_date("FREQ=DAILY;INTERVAL=2", datetime(2026, 1, 2), start) is False
    assert _rrule_matches_date("FREQ=DAILY;INTERVAL=2", datetime(2026, 1, 3), start) is True


def test_weekly_byday_match():
    # 2026-03-30 is a Monday
    monday = datetime(2026, 3, 30)
    assert _rrule_matches_date("FREQ=WEEKLY;BYDAY=MO,WE,FR", monday, None) is True


def test_weekly_byday_no_match():
    # 2026-03-31 is a Tuesday
    tuesday = datetime(2026, 3, 31)
    assert _rrule_matches_date("FREQ=WEEKLY;BYDAY=MO,WE,FR", tuesday, None) is False


def test_weekly_interval_2():
    start = datetime(2026, 1, 5)  # Monday, week 1
    week1_monday = datetime(2026, 1, 5)
    week2_monday = datetime(2026, 1, 12)
    week3_monday = datetime(2026, 1, 19)

    assert _rrule_matches_date("FREQ=WEEKLY;INTERVAL=2", week1_monday, start) is True
    assert _rrule_matches_date("FREQ=WEEKLY;INTERVAL=2", week2_monday, start) is False
    assert _rrule_matches_date("FREQ=WEEKLY;INTERVAL=2", week3_monday, start) is True


def test_monthly_bymonthday():
    assert _rrule_matches_date("FREQ=MONTHLY;BYMONTHDAY=15", datetime(2026, 3, 15), None) is True
    assert _rrule_matches_date("FREQ=MONTHLY;BYMONTHDAY=15", datetime(2026, 3, 16), None) is False


def test_monthly_inherits_start_day():
    start = datetime(2026, 1, 10)
    assert _rrule_matches_date("FREQ=MONTHLY", datetime(2026, 2, 10), start) is True
    assert _rrule_matches_date("FREQ=MONTHLY", datetime(2026, 2, 11), start) is False


def test_monthly_interval_2():
    start = datetime(2026, 1, 10)  # January
    assert _rrule_matches_date("FREQ=MONTHLY;INTERVAL=2", datetime(2026, 1, 10), start) is True
    assert _rrule_matches_date("FREQ=MONTHLY;INTERVAL=2", datetime(2026, 2, 10), start) is False
    assert _rrule_matches_date("FREQ=MONTHLY;INTERVAL=2", datetime(2026, 3, 10), start) is True


def test_yearly_matches_anniversary():
    start = datetime(2025, 3, 15)
    assert _rrule_matches_date("FREQ=YEARLY", datetime(2026, 3, 15), start) is True


def test_yearly_wrong_date():
    start = datetime(2025, 3, 15)
    assert _rrule_matches_date("FREQ=YEARLY", datetime(2026, 3, 16), start) is False


def test_yearly_interval_2():
    start = datetime(2024, 3, 15)
    assert _rrule_matches_date("FREQ=YEARLY;INTERVAL=2", datetime(2024, 3, 15), start) is True
    assert _rrule_matches_date("FREQ=YEARLY;INTERVAL=2", datetime(2025, 3, 15), start) is False
    assert _rrule_matches_date("FREQ=YEARLY;INTERVAL=2", datetime(2026, 3, 15), start) is True


def test_unknown_freq_returns_false():
    assert _rrule_matches_date("FREQ=SECONDLY", datetime(2026, 3, 29), None) is False


def test_no_schedule_start_daily():
    """FREQ=DAILY with no schedule_start — interval check skipped, always True."""
    assert _rrule_matches_date("FREQ=DAILY", datetime(2026, 5, 20), None) is True


def test_weekly_byday_multiple_days():
    """FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR — weekdays only."""
    rule = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
    # 2026-03-30 Mon, 31 Tue, Apr 1 Wed, 2 Thu, 3 Fri, 4 Sat, 5 Sun
    assert _rrule_matches_date(rule, datetime(2026, 3, 30), None) is True   # Mon
    assert _rrule_matches_date(rule, datetime(2026, 3, 31), None) is True   # Tue
    assert _rrule_matches_date(rule, datetime(2026, 4, 1), None) is True    # Wed
    assert _rrule_matches_date(rule, datetime(2026, 4, 2), None) is True    # Thu
    assert _rrule_matches_date(rule, datetime(2026, 4, 3), None) is True    # Fri
    assert _rrule_matches_date(rule, datetime(2026, 4, 4), None) is False   # Sat
    assert _rrule_matches_date(rule, datetime(2026, 4, 5), None) is False   # Sun
