"""Tests for evaluate_override_for_device() from app/api/overrides.py.

Feature tree refs: [FT-8.9]-[FT-8.13]
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.api.overrides import evaluate_override_for_device
from tests.factories import (
    create_device, create_device_group, add_device_to_group,
    create_override, create_playlist,
)


def _make_now(year=2026, month=3, day=29, hour=10, minute=0):
    return datetime(year, month, day, hour, minute, 0)


@patch("app.api.overrides.datetime")
async def test_no_overrides_returns_none(mock_dt, session):
    mock_dt.now.return_value = _make_now()
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    result = await evaluate_override_for_device(device.id, session)
    assert result is None


@patch("app.api.overrides.datetime")
async def test_active_override_matches(mock_dt, session):
    """Active override targeting 'all' -> returned."""
    mock_dt.now.return_value = _make_now()
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    override = await create_override(session, target_type="all")
    await session.commit()

    result = await evaluate_override_for_device(device.id, session)
    assert result is not None
    assert result.id == override.id


@patch("app.api.overrides.datetime")
async def test_inactive_override_ignored(mock_dt, session):
    """is_active=False -> None."""
    mock_dt.now.return_value = _make_now()
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    await create_override(session, target_type="all", is_active=False)
    await session.commit()

    result = await evaluate_override_for_device(device.id, session)
    assert result is None


@patch("app.api.overrides.datetime")
async def test_expired_override_ignored(mock_dt, session):
    """expires_at in past -> None."""
    now = _make_now()
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    await create_override(
        session, target_type="all",
        expires_at=now - timedelta(hours=1),
    )
    await session.commit()

    result = await evaluate_override_for_device(device.id, session)
    assert result is None


@patch("app.api.overrides.datetime")
async def test_not_yet_expired_matches(mock_dt, session):
    """expires_at in future -> returned."""
    now = _make_now()
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    override = await create_override(
        session, target_type="all",
        expires_at=now + timedelta(hours=1),
    )
    await session.commit()

    result = await evaluate_override_for_device(device.id, session)
    assert result is not None
    assert result.id == override.id


@patch("app.api.overrides.datetime")
async def test_no_expiry_matches(mock_dt, session):
    """expires_at=None -> returned."""
    mock_dt.now.return_value = _make_now()
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    override = await create_override(session, target_type="all", expires_at=None)
    await session.commit()

    result = await evaluate_override_for_device(device.id, session)
    assert result is not None
    assert result.id == override.id


@patch("app.api.overrides.datetime")
async def test_device_target_matches(mock_dt, session):
    """target_type='device', target_id=device_id -> returned."""
    mock_dt.now.return_value = _make_now()
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    override = await create_override(
        session, target_type="device", target_id=device.id,
    )
    await session.commit()

    result = await evaluate_override_for_device(device.id, session)
    assert result is not None
    assert result.id == override.id


@patch("app.api.overrides.datetime")
async def test_device_target_wrong_device(mock_dt, session):
    """target_type='device', target_id=other_device -> None."""
    mock_dt.now.return_value = _make_now()
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session, name="My Device")
    other_device = await create_device(session, name="Other Device")
    await create_override(
        session, target_type="device", target_id=other_device.id,
    )
    await session.commit()

    result = await evaluate_override_for_device(device.id, session)
    assert result is None


@patch("app.api.overrides.datetime")
async def test_group_target_matches_member(mock_dt, session):
    """target_type='group', device is member -> returned."""
    mock_dt.now.return_value = _make_now()
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    group = await create_device_group(session)
    await add_device_to_group(session, device.id, group.id)

    override = await create_override(
        session, target_type="group", target_id=group.id,
    )
    await session.commit()

    result = await evaluate_override_for_device(device.id, session)
    assert result is not None
    assert result.id == override.id


@patch("app.api.overrides.datetime")
async def test_group_target_non_member(mock_dt, session):
    """target_type='group', device not member -> None."""
    mock_dt.now.return_value = _make_now()
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    group = await create_device_group(session)
    # device NOT added to group

    await create_override(
        session, target_type="group", target_id=group.id,
    )
    await session.commit()

    result = await evaluate_override_for_device(device.id, session)
    assert result is None


@patch("app.api.overrides.datetime")
async def test_specificity_device_beats_group(mock_dt, session):
    """Both device + group overrides active -> device override returned."""
    now = _make_now()
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    group = await create_device_group(session)
    await add_device_to_group(session, device.id, group.id)

    group_override = await create_override(
        session, name="Group OVR",
        target_type="group", target_id=group.id,
        created_at=now - timedelta(minutes=10),
    )
    device_override = await create_override(
        session, name="Device OVR",
        target_type="device", target_id=device.id,
        created_at=now - timedelta(minutes=5),
    )
    await session.commit()

    result = await evaluate_override_for_device(device.id, session)
    assert result is not None
    assert result.id == device_override.id


@patch("app.api.overrides.datetime")
async def test_specificity_group_beats_all(mock_dt, session):
    """Both group + all overrides -> group override returned."""
    now = _make_now()
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    group = await create_device_group(session)
    await add_device_to_group(session, device.id, group.id)

    all_override = await create_override(
        session, name="All OVR", target_type="all",
        created_at=now - timedelta(minutes=10),
    )
    group_override = await create_override(
        session, name="Group OVR",
        target_type="group", target_id=group.id,
        created_at=now - timedelta(minutes=5),
    )
    await session.commit()

    result = await evaluate_override_for_device(device.id, session)
    assert result is not None
    assert result.id == group_override.id


@patch("app.api.overrides.datetime")
async def test_most_recent_tiebreaker(mock_dt, session):
    """Two 'all' overrides -> most recently created wins."""
    now = _make_now()
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    older = await create_override(
        session, name="Older", target_type="all",
        created_at=now - timedelta(hours=2),
    )
    newer = await create_override(
        session, name="Newer", target_type="all",
        created_at=now - timedelta(hours=1),
    )
    await session.commit()

    result = await evaluate_override_for_device(device.id, session)
    assert result is not None
    assert result.id == newer.id


@patch("app.api.overrides.datetime")
async def test_message_override_type(mock_dt, session):
    """content_type='message' -> Override with message content."""
    mock_dt.now.return_value = _make_now()
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    override = await create_override(
        session, target_type="all",
        content_type="message", content="Fire drill!",
    )
    await session.commit()

    result = await evaluate_override_for_device(device.id, session)
    assert result is not None
    assert result.content_type == "message"
    assert result.content == "Fire drill!"


@patch("app.api.overrides.datetime")
async def test_playlist_override_type(mock_dt, session):
    """content_type='playlist' -> Override with playlist_id content."""
    mock_dt.now.return_value = _make_now()
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    device = await create_device(session)
    playlist = await create_playlist(session, name="Emergency PL")
    override = await create_override(
        session, target_type="all",
        content_type="playlist", content=playlist.id,
    )
    await session.commit()

    result = await evaluate_override_for_device(device.id, session)
    assert result is not None
    assert result.content_type == "playlist"
    assert result.content == playlist.id
