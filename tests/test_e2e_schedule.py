"""E2E tests for schedule → device polling integration.

Tests that schedules, overrides, and priority rules correctly affect
what a device receives when it polls for its playlist.

[FT-7.12, FT-8.9, FT-8.10, FT-20.5, FT-20.6]
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from tests.factories import (
    create_asset,
    create_device,
    create_override,
    create_playlist,
    create_playlist_item,
    create_schedule,
    create_settings,
    create_token,
)
from tests.helpers import auth_header


async def test_schedule_changes_device_playlist(client, session):
    """Active schedule → device poll returns scheduled playlist, not default."""
    settings = await create_settings(session)
    default_pl = await create_playlist(session, name="Default", is_default=True)
    default_asset = await create_asset(session, name="default.png", uri="default.png")
    await create_playlist_item(session, default_pl.id, default_asset.id, order=0)

    scheduled_pl = await create_playlist(session, name="Scheduled")
    sched_asset = await create_asset(session, name="scheduled.png", uri="scheduled.png")
    await create_playlist_item(session, scheduled_pl.id, sched_asset.id, order=0)

    device = await create_device(session, playlist_id=default_pl.id)
    _, dev_pt = await create_token(session, role="device", device_id=device.id)

    # Schedule with no time/day restrictions — always active
    await create_schedule(
        session, name="Always On", playlist_id=scheduled_pl.id,
        target_type="device", target_id=device.id,
    )
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_pt),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["asset"]["name"] == "scheduled.png"


async def test_schedule_with_override(client, session):
    """Active override beats any schedule — override wins."""
    settings = await create_settings(session)
    default_pl = await create_playlist(session, name="Default", is_default=True)
    scheduled_pl = await create_playlist(session, name="Scheduled")
    sched_asset = await create_asset(session, name="scheduled.png", uri="s.png")
    await create_playlist_item(session, scheduled_pl.id, sched_asset.id, order=0)

    device = await create_device(session, playlist_id=default_pl.id)
    _, dev_pt = await create_token(session, role="device", device_id=device.id)

    # Active schedule
    await create_schedule(
        session, name="Schedule", playlist_id=scheduled_pl.id,
        target_type="device", target_id=device.id,
    )
    # Active message override targeting this device
    future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    await create_override(
        session, name="Emergency", content_type="message",
        content="Fire drill!", target_type="device", target_id=device.id,
        is_active=True, expires_at=future,
    )
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_pt),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "override" in data
    assert data["override"]["type"] == "message"
    assert data["override"]["message"] == "Fire drill!"


async def test_schedule_expiry_reverts(client, session):
    """Schedule with end_date in the past → device gets default playlist."""
    settings = await create_settings(session)
    default_pl = await create_playlist(session, name="Default", is_default=True)
    default_asset = await create_asset(session, name="default.png", uri="default.png")
    await create_playlist_item(session, default_pl.id, default_asset.id, order=0)

    scheduled_pl = await create_playlist(session, name="Expired Sched")
    sched_asset = await create_asset(session, name="expired.png", uri="expired.png")
    await create_playlist_item(session, scheduled_pl.id, sched_asset.id, order=0)

    device = await create_device(session, playlist_id=default_pl.id)
    _, dev_pt = await create_token(session, role="device", device_id=device.id)

    # Schedule that already expired
    past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    await create_schedule(
        session, name="Expired", playlist_id=scheduled_pl.id,
        target_type="device", target_id=device.id,
        end_date=past,
    )
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_pt),
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should get default playlist, not the expired schedule
    assert len(data["items"]) == 1
    assert data["items"][0]["asset"]["name"] == "default.png"


async def test_schedule_timeline_matches_evaluation(client, session):
    """Timeline preview returns the same playlist as actual evaluation."""
    settings = await create_settings(session)
    default_pl = await create_playlist(session, name="Default", is_default=True)
    scheduled_pl = await create_playlist(session, name="Morning")
    sched_asset = await create_asset(session, name="morning.png", uri="m.png")
    await create_playlist_item(session, scheduled_pl.id, sched_asset.id, order=0)

    device = await create_device(session, playlist_id=default_pl.id)
    _, admin_pt = await create_token(session, role="admin")
    _, dev_pt = await create_token(session, role="device", device_id=device.id)

    # All-day schedule, always active
    await create_schedule(
        session, name="Always Morning", playlist_id=scheduled_pl.id,
        target_type="device", target_id=device.id, priority=10,
    )
    await session.commit()

    # Get timeline preview
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    resp = await client.get(
        f"/api/schedules/preview/timeline?device_id={device.id}&date={today}",
        headers=auth_header(admin_pt),
    )
    assert resp.status_code == 200
    timeline = resp.json()
    # All 48 slots should show the scheduled playlist
    for slot in timeline["slots"]:
        assert slot["playlist_id"] == scheduled_pl.id

    # Actual poll should also return the scheduled playlist
    resp2 = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_pt),
    )
    assert resp2.status_code == 200
    assert resp2.json()["items"][0]["asset"]["name"] == "morning.png"


async def test_multiple_schedules_priority(client, session):
    """Higher-priority schedule wins over lower-priority one."""
    settings = await create_settings(session)
    default_pl = await create_playlist(session, name="Default", is_default=True)
    low_pl = await create_playlist(session, name="Low Priority")
    low_asset = await create_asset(session, name="low.png", uri="low.png")
    await create_playlist_item(session, low_pl.id, low_asset.id, order=0)

    high_pl = await create_playlist(session, name="High Priority")
    high_asset = await create_asset(session, name="high.png", uri="high.png")
    await create_playlist_item(session, high_pl.id, high_asset.id, order=0)

    device = await create_device(session, playlist_id=default_pl.id)
    _, dev_pt = await create_token(session, role="device", device_id=device.id)

    # Low-priority schedule
    await create_schedule(
        session, name="Low", playlist_id=low_pl.id,
        target_type="device", target_id=device.id, priority=1,
    )
    # High-priority schedule
    await create_schedule(
        session, name="High", playlist_id=high_pl.id,
        target_type="device", target_id=device.id, priority=10,
    )
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_pt),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["asset"]["name"] == "high.png"
