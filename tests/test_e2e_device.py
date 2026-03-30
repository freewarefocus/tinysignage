"""E2E tests for device lifecycle.

Tests: create → pair → poll → heartbeat → watchdog offline detection,
plus layout zones and override payloads in device polling.

[FT-4.7]-[FT-4.12], [FT-20.7]-[FT-20.9]
"""

from datetime import datetime, timedelta, timezone

from tests.factories import (
    create_asset,
    create_device,
    create_layout,
    create_override,
    create_playlist,
    create_playlist_item,
    create_settings,
    create_token,
    create_zone,
)
from tests.helpers import auth_header, seed_defaults


async def test_device_lifecycle(client, session):
    """Full lifecycle: create → pair → poll → heartbeat → verify online."""
    await seed_defaults(session)
    _, admin_pt = await create_token(session, role="admin")
    await session.commit()
    headers = auth_header(admin_pt)

    # Step 1: Create device
    resp = await client.post("/api/devices", json={"name": "Lobby TV"}, headers=headers)
    assert resp.status_code == 201
    device_data = resp.json()
    device_id = device_data["id"]
    pairing_code = device_data["pairing_code"]

    # Step 2: Register with pairing code (public)
    resp = await client.post("/api/devices/register", json={"code": pairing_code})
    assert resp.status_code == 200
    reg_data = resp.json()
    assert reg_data["device_id"] == device_id
    device_token = reg_data["token"]

    # Step 3: Poll for playlist
    resp = await client.get(
        f"/api/devices/{device_id}/playlist",
        headers=auth_header(device_token),
    )
    assert resp.status_code == 200
    assert "hash" in resp.json()
    assert "items" in resp.json()

    # Step 4: Send heartbeat
    resp = await client.post(
        "/api/player/heartbeat",
        json={"device_id": device_id},
        headers=auth_header(device_token),
    )
    assert resp.status_code == 200

    # Step 5: Verify device is online
    resp = await client.get(f"/api/devices/{device_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "online"


async def test_device_goes_online_on_poll(client, session):
    """Polling updates status to 'online' and sets last_seen."""
    settings = await create_settings(session)
    playlist = await create_playlist(session, name="Default", is_default=True)
    device = await create_device(session, playlist_id=playlist.id)
    _, admin_pt = await create_token(session, role="admin")
    _, dev_pt = await create_token(session, role="device", device_id=device.id)
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_pt),
    )
    assert resp.status_code == 200

    resp2 = await client.get(
        f"/api/devices/{device.id}", headers=auth_header(admin_pt),
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["status"] == "online"
    assert data["last_seen"] is not None


async def test_device_goes_offline_via_watchdog(client, session, engine):
    """Device with stale last_seen is marked offline by watchdog logic."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.models import Device

    settings = await create_settings(session)
    playlist = await create_playlist(session, name="Default", is_default=True)
    device = await create_device(session, playlist_id=playlist.id)

    # Simulate: device was online 5 minutes ago
    stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=300)
    device.last_seen = stale_time
    device.last_heartbeat = stale_time
    device.status = "online"
    await session.commit()
    device_id = device.id

    # Run watchdog check logic directly against test DB
    test_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with test_session_factory() as wd_session:
        from sqlalchemy import select
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        result = await wd_session.execute(select(Device))
        devices = result.scalars().all()
        for d in devices:
            last_contact = d.last_heartbeat or d.last_seen
            if last_contact:
                seconds_since = (now - last_contact).total_seconds()
                if seconds_since > 120 and d.status == "online":
                    d.status = "offline"
        await wd_session.commit()

    # Verify device is now offline
    _, admin_pt = await create_token(session, role="admin")
    await session.commit()
    resp = await client.get(f"/api/devices/{device_id}", headers=auth_header(admin_pt))
    assert resp.status_code == 200
    assert resp.json()["status"] == "offline"


async def test_device_with_layout_returns_zones(client, session):
    """Device with layout → polling returns zones array."""
    settings = await create_settings(session)
    playlist = await create_playlist(session, name="Default", is_default=True)
    sidebar_pl = await create_playlist(session, name="Sidebar PL")
    sidebar_asset = await create_asset(session, name="ad.png", uri="ad.png")
    await create_playlist_item(session, sidebar_pl.id, sidebar_asset.id, order=0)

    layout = await create_layout(session, name="Two Zone")
    await create_zone(
        session, layout.id, name="Main",
        zone_type="main", x_percent=0.0, y_percent=0.0,
        width_percent=75.0, height_percent=100.0, playlist_id=playlist.id,
    )
    await create_zone(
        session, layout.id, name="Sidebar",
        zone_type="sidebar", x_percent=75.0, y_percent=0.0,
        width_percent=25.0, height_percent=100.0, playlist_id=sidebar_pl.id,
    )

    device = await create_device(session, playlist_id=playlist.id, layout_id=layout.id)
    _, dev_pt = await create_token(session, role="device", device_id=device.id)
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_pt),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "zones" in data
    assert len(data["zones"]) == 2
    zone_names = {z["name"] for z in data["zones"]}
    assert zone_names == {"Main", "Sidebar"}
    sidebar_zone = next(z for z in data["zones"] if z["name"] == "Sidebar")
    assert len(sidebar_zone["items"]) == 1
    assert sidebar_zone["items"][0]["asset"]["name"] == "ad.png"


async def test_device_override_message(client, session):
    """Active message override → device gets override payload."""
    settings = await create_settings(session)
    playlist = await create_playlist(session, name="Default", is_default=True)
    device = await create_device(session, playlist_id=playlist.id)
    _, dev_pt = await create_token(session, role="device", device_id=device.id)

    future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    await create_override(
        session, name="Alert", content_type="message", content="Evacuate now!",
        target_type="all", is_active=True, expires_at=future,
    )
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_pt),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "override" in data
    assert data["override"]["type"] == "message"
    assert data["override"]["message"] == "Evacuate now!"
    assert data["items"] == []


async def test_device_override_playlist(client, session):
    """Active playlist override → device gets override's playlist items."""
    settings = await create_settings(session)
    default_pl = await create_playlist(session, name="Default", is_default=True)
    default_asset = await create_asset(session, name="normal.png", uri="normal.png")
    await create_playlist_item(session, default_pl.id, default_asset.id, order=0)

    override_pl = await create_playlist(session, name="Emergency PL")
    override_asset = await create_asset(session, name="emergency.png", uri="emergency.png")
    await create_playlist_item(session, override_pl.id, override_asset.id, order=0)

    device = await create_device(session, playlist_id=default_pl.id)
    _, dev_pt = await create_token(session, role="device", device_id=device.id)

    future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    await create_override(
        session, name="Emergency PL Override", content_type="playlist",
        content=override_pl.id, target_type="all",
        is_active=True, expires_at=future,
    )
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_pt),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "override" in data
    assert data["override"]["type"] == "playlist"
    assert len(data["items"]) == 1
    assert data["items"][0]["asset"]["name"] == "emergency.png"
