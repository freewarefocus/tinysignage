"""Tests for evaluate_schedule_for_device() from app/api/schedules.py.

Feature tree refs: [FT-7.12]-[FT-7.19]

Strategy: Create schedules with known time windows and mock datetime.now to
control the "current time". The function calls
datetime.now(timezone.utc).replace(tzinfo=None) internally.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

from app.api.schedules import evaluate_schedule_for_device
from tests.factories import (
    create_device, create_device_group, add_device_to_group,
    create_playlist, create_schedule,
)


def _make_now(year=2026, month=3, day=29, hour=10, minute=0):
    """Create a naive datetime matching how the app strips tzinfo."""
    return datetime(year, month, day, hour, minute, 0)


def _mock_datetime(target_now):
    """Create a mock datetime class that returns target_now for .now() but
    preserves normal datetime construction and other methods."""
    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = target_now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
    return mock_dt


@patch("app.api.schedules.datetime")
async def test_no_schedules_returns_none(mock_dt, session):
    mock_dt.now.return_value = _make_now()
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    result = await evaluate_schedule_for_device(device.id, session)
    assert result == (None, None)


@patch("app.api.schedules.datetime")
async def test_single_matching_schedule(mock_dt, session):
    """One active schedule within time window returns its playlist_id."""
    now = _make_now(hour=10)  # Sunday 10:00
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    playlist = await create_playlist(session, name="Scheduled")
    await create_schedule(
        session, playlist_id=playlist.id, target_type="all",
        start_time="09:00", end_time="11:00",
    )
    await session.commit()

    pid, tid = await evaluate_schedule_for_device(device.id, session)
    assert pid == playlist.id
    assert tid is None


@patch("app.api.schedules.datetime")
async def test_schedule_outside_time_window(mock_dt, session):
    now = _make_now(hour=12)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id, target_type="all",
        start_time="09:00", end_time="11:00",
    )
    await session.commit()

    result = await evaluate_schedule_for_device(device.id, session)
    assert result == (None, None)


@patch("app.api.schedules.datetime")
async def test_schedule_overnight_time_window(mock_dt, session):
    """start_time='22:00', end_time='06:00', current=23:00 -> matches."""
    now = _make_now(hour=23)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id, target_type="all",
        start_time="22:00", end_time="06:00",
    )
    await session.commit()

    pid, _ = await evaluate_schedule_for_device(device.id, session)
    assert pid == playlist.id


@patch("app.api.schedules.datetime")
async def test_schedule_overnight_not_matching(mock_dt, session):
    """start_time='22:00', end_time='06:00', current=12:00 -> no match."""
    now = _make_now(hour=12)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id, target_type="all",
        start_time="22:00", end_time="06:00",
    )
    await session.commit()

    result = await evaluate_schedule_for_device(device.id, session)
    assert result == (None, None)


@patch("app.api.schedules.datetime")
async def test_schedule_day_of_week_match(mock_dt, session):
    """days_of_week includes current day -> matches."""
    # 2026-03-29 is Sunday = weekday 6
    now = _make_now(year=2026, month=3, day=29, hour=10)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id, target_type="all",
        days_of_week="6",  # Sunday
    )
    await session.commit()

    pid, _ = await evaluate_schedule_for_device(device.id, session)
    assert pid == playlist.id


@patch("app.api.schedules.datetime")
async def test_schedule_day_of_week_no_match(mock_dt, session):
    """days_of_week excludes current day -> no match."""
    # 2026-03-29 is Sunday = weekday 6
    now = _make_now(year=2026, month=3, day=29, hour=10)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id, target_type="all",
        days_of_week="0,1,2,3,4",  # Mon-Fri only
    )
    await session.commit()

    result = await evaluate_schedule_for_device(device.id, session)
    assert result == (None, None)


@patch("app.api.schedules.datetime")
async def test_schedule_date_range_match(mock_dt, session):
    """start_date < now < end_date -> matches."""
    now = _make_now(year=2026, month=3, day=15, hour=10)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id, target_type="all",
        start_date=datetime(2026, 3, 1),
        end_date=datetime(2026, 3, 31),
    )
    await session.commit()

    pid, _ = await evaluate_schedule_for_device(device.id, session)
    assert pid == playlist.id


@patch("app.api.schedules.datetime")
async def test_schedule_before_start_date(mock_dt, session):
    """now < start_date -> no match."""
    now = _make_now(year=2026, month=2, day=15, hour=10)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id, target_type="all",
        start_date=datetime(2026, 3, 1),
    )
    await session.commit()

    result = await evaluate_schedule_for_device(device.id, session)
    assert result == (None, None)


@patch("app.api.schedules.datetime")
async def test_schedule_after_end_date(mock_dt, session):
    """now > end_date -> no match."""
    now = _make_now(year=2026, month=4, day=15, hour=10)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id, target_type="all",
        end_date=datetime(2026, 3, 31),
    )
    await session.commit()

    result = await evaluate_schedule_for_device(device.id, session)
    assert result == (None, None)


@patch("app.api.schedules.datetime")
async def test_schedule_inactive_ignored(mock_dt, session):
    """is_active=False -> ignored."""
    now = _make_now(hour=10)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id, target_type="all",
        is_active=False,
    )
    await session.commit()

    result = await evaluate_schedule_for_device(device.id, session)
    assert result == (None, None)


@patch("app.api.schedules.datetime")
async def test_highest_priority_wins(mock_dt, session):
    """Two schedules match, priority 10 vs 5 -> priority 10 wins."""
    now = _make_now(hour=10)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    low_playlist = await create_playlist(session, name="Low")
    high_playlist = await create_playlist(session, name="High")

    await create_schedule(
        session, playlist_id=low_playlist.id, target_type="all", priority=5,
    )
    await create_schedule(
        session, playlist_id=high_playlist.id, target_type="all", priority=10,
    )
    await session.commit()

    pid, _ = await evaluate_schedule_for_device(device.id, session)
    assert pid == high_playlist.id


@patch("app.api.schedules.datetime")
async def test_target_specificity_tiebreaker(mock_dt, session):
    """Same priority: device-target beats group-target."""
    now = _make_now(hour=10)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    group = await create_device_group(session)
    await add_device_to_group(session, device.id, group.id)

    group_playlist = await create_playlist(session, name="Group PL")
    device_playlist = await create_playlist(session, name="Device PL")

    await create_schedule(
        session, playlist_id=group_playlist.id,
        target_type="group", target_id=group.id, priority=5,
    )
    await create_schedule(
        session, playlist_id=device_playlist.id,
        target_type="device", target_id=device.id, priority=5,
    )
    await session.commit()

    pid, _ = await evaluate_schedule_for_device(device.id, session)
    assert pid == device_playlist.id


@patch("app.api.schedules.datetime")
async def test_group_target_matches_member(mock_dt, session):
    """Schedule targets group, device is member -> matches."""
    now = _make_now(hour=10)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    group = await create_device_group(session)
    await add_device_to_group(session, device.id, group.id)

    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id,
        target_type="group", target_id=group.id,
    )
    await session.commit()

    pid, _ = await evaluate_schedule_for_device(device.id, session)
    assert pid == playlist.id


@patch("app.api.schedules.datetime")
async def test_group_target_non_member_excluded(mock_dt, session):
    """Schedule targets group, device NOT member -> no match."""
    now = _make_now(hour=10)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    group = await create_device_group(session)
    # device is NOT added to the group

    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id,
        target_type="group", target_id=group.id,
    )
    await session.commit()

    result = await evaluate_schedule_for_device(device.id, session)
    assert result == (None, None)


@patch("app.api.schedules.datetime")
async def test_device_target_matches_only_that_device(mock_dt, session):
    """Schedule targets device A, query for device B -> no match."""
    now = _make_now(hour=10)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device_a = await create_device(session, name="Device A")
    device_b = await create_device(session, name="Device B")

    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id,
        target_type="device", target_id=device_a.id,
    )
    await session.commit()

    result = await evaluate_schedule_for_device(device_b.id, session)
    assert result == (None, None)


@patch("app.api.schedules.datetime")
async def test_all_target_matches_any_device(mock_dt, session):
    """Schedule target_type='all' -> matches any device."""
    now = _make_now(hour=10)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id, target_type="all",
    )
    await session.commit()

    pid, _ = await evaluate_schedule_for_device(device.id, session)
    assert pid == playlist.id


@patch("app.api.schedules.datetime")
async def test_transition_playlist_returned(mock_dt, session):
    """Matching schedule has transition_playlist_id -> returned in tuple."""
    now = _make_now(hour=10)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    main_playlist = await create_playlist(session, name="Main")
    trans_playlist = await create_playlist(session, name="Transition")
    await create_schedule(
        session, playlist_id=main_playlist.id, target_type="all",
        transition_playlist_id=trans_playlist.id,
    )
    await session.commit()

    pid, tid = await evaluate_schedule_for_device(device.id, session)
    assert pid == main_playlist.id
    assert tid == trans_playlist.id


@patch("app.api.schedules.datetime")
async def test_start_time_only(mock_dt, session):
    """start_time set, no end_time: match when current >= start_time."""
    now = _make_now(hour=14)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id, target_type="all",
        start_time="09:00", end_time=None,
    )
    await session.commit()

    pid, _ = await evaluate_schedule_for_device(device.id, session)
    assert pid == playlist.id


@patch("app.api.schedules.datetime")
async def test_end_time_only(mock_dt, session):
    """end_time set, no start_time: match when current < end_time."""
    now = _make_now(hour=8)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    playlist = await create_playlist(session)
    await create_schedule(
        session, playlist_id=playlist.id, target_type="all",
        start_time=None, end_time="12:00",
    )
    await session.commit()

    pid, _ = await evaluate_schedule_for_device(device.id, session)
    assert pid == playlist.id
