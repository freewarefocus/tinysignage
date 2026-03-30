"""Trigger flow payload in device polling tests. [FT-17.15, FT-20.10, FT-20.12]

Tests that GET /api/devices/{id}/playlist correctly includes trigger flow data
when a playlist has an associated trigger flow.
"""

import json as json_mod
from datetime import datetime, timedelta, timezone

from tests.factories import (
    create_asset, create_device, create_playlist, create_playlist_item,
    create_settings, create_token, create_trigger_branch, create_trigger_flow,
)
from tests.helpers import auth_header


async def _setup_device_with_trigger_flow(session):
    """Create a complete setup: device -> playlist -> trigger flow -> branches -> assets."""
    settings = await create_settings(session)
    pl_source = await create_playlist(session, name="Source", mode="advanced")
    pl_target = await create_playlist(session, name="Target")
    flow = await create_trigger_flow(session, name="Interactive Flow")
    pl_source.trigger_flow_id = flow.id

    asset = await create_asset(session, name="target_img.png")
    await create_playlist_item(session, pl_target.id, asset.id, order=0)

    branch = await create_trigger_branch(
        session, flow.id, pl_source.id, pl_target.id,
        trigger_type="keyboard",
        trigger_config='{"key": "1"}',
    )

    device = await create_device(session, playlist_id=pl_source.id)
    token, plaintext = await create_token(session, role="device", device_id=device.id)
    await session.commit()

    return device, plaintext, flow, branch, pl_source, pl_target


async def test_device_playlist_includes_trigger_flow(client, session):
    """Playlist has trigger_flow_id -> response has 'trigger_flow' key."""
    device, plaintext, *_ = await _setup_device_with_trigger_flow(session)

    resp = await client.get(
        f"/api/devices/{device.id}/playlist",
        headers=auth_header(plaintext),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "trigger_flow" in data


async def test_trigger_flow_has_branches(client, session):
    """trigger_flow.branches is non-empty list."""
    device, plaintext, *_ = await _setup_device_with_trigger_flow(session)

    resp = await client.get(
        f"/api/devices/{device.id}/playlist",
        headers=auth_header(plaintext),
    )
    data = resp.json()
    assert isinstance(data["trigger_flow"]["branches"], list)
    assert len(data["trigger_flow"]["branches"]) > 0


async def test_trigger_flow_branch_has_target_playlist(client, session):
    """Each branch has target_playlist with items + settings."""
    device, plaintext, *_ = await _setup_device_with_trigger_flow(session)

    resp = await client.get(
        f"/api/devices/{device.id}/playlist",
        headers=auth_header(plaintext),
    )
    data = resp.json()
    branch = data["trigger_flow"]["branches"][0]
    assert "target_playlist" in branch
    tp = branch["target_playlist"]
    assert "id" in tp
    assert "name" in tp
    assert "items" in tp
    assert "settings" in tp
    assert len(tp["items"]) == 1  # We added one asset


async def test_trigger_flow_strips_webhook_token(client, session):
    """branch.trigger_config does NOT contain 'token' key in device payload."""
    settings = await create_settings(session)
    pl_source = await create_playlist(session, name="Source", mode="advanced")
    pl_target = await create_playlist(session, name="Target")
    flow = await create_trigger_flow(session)
    pl_source.trigger_flow_id = flow.id

    asset = await create_asset(session, name="img.png")
    await create_playlist_item(session, pl_target.id, asset.id, order=0)

    branch = await create_trigger_branch(
        session, flow.id, pl_source.id, pl_target.id,
        trigger_type="webhook",
        trigger_config='{"token": "secret123", "url": "https://example.com"}',
    )
    device = await create_device(session, playlist_id=pl_source.id)
    token, plaintext = await create_token(session, role="device", device_id=device.id)
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist",
        headers=auth_header(plaintext),
    )
    data = resp.json()
    branch_data = data["trigger_flow"]["branches"][0]

    # Token MUST be stripped -- players don't need it
    assert "token" not in branch_data["trigger_config"]
    # Other config should be preserved
    assert branch_data["trigger_config"]["url"] == "https://example.com"


async def test_trigger_flow_includes_webhook_fire_timestamp(client, session):
    """Branch with last_webhook_fire -> included in payload."""
    settings = await create_settings(session)
    pl_source = await create_playlist(session, name="Source", mode="advanced")
    pl_target = await create_playlist(session, name="Target")
    flow = await create_trigger_flow(session)
    pl_source.trigger_flow_id = flow.id

    asset = await create_asset(session, name="img.png")
    await create_playlist_item(session, pl_target.id, asset.id, order=0)

    # Create webhook branch with a fire timestamp already set
    fire_time = datetime.now(timezone.utc).replace(tzinfo=None)
    branch = await create_trigger_branch(
        session, flow.id, pl_source.id, pl_target.id,
        trigger_type="webhook",
        trigger_config='{"token": "abc123"}',
        last_webhook_fire=fire_time,
    )
    device = await create_device(session, playlist_id=pl_source.id)
    token, plaintext = await create_token(session, role="device", device_id=device.id)
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist",
        headers=auth_header(plaintext),
    )
    data = resp.json()
    branch_data = data["trigger_flow"]["branches"][0]
    assert "last_webhook_fire" in branch_data


async def test_trigger_flow_target_filters_disabled_assets(client, session):
    """Disabled asset in target playlist -> not in branch items."""
    settings = await create_settings(session)
    pl_source = await create_playlist(session, name="Source", mode="advanced")
    pl_target = await create_playlist(session, name="Target")
    flow = await create_trigger_flow(session)
    pl_source.trigger_flow_id = flow.id

    enabled_asset = await create_asset(session, name="enabled.png", is_enabled=True)
    disabled_asset = await create_asset(session, name="disabled.png", uri="disabled.png", is_enabled=False)
    await create_playlist_item(session, pl_target.id, enabled_asset.id, order=0)
    await create_playlist_item(session, pl_target.id, disabled_asset.id, order=1)

    await create_trigger_branch(
        session, flow.id, pl_source.id, pl_target.id,
        trigger_type="keyboard",
        trigger_config='{"key": "1"}',
    )
    device = await create_device(session, playlist_id=pl_source.id)
    token, plaintext = await create_token(session, role="device", device_id=device.id)
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist",
        headers=auth_header(plaintext),
    )
    data = resp.json()
    target_items = data["trigger_flow"]["branches"][0]["target_playlist"]["items"]
    assert len(target_items) == 1
    assert target_items[0]["asset"]["name"] == "enabled.png"


async def test_trigger_flow_target_filters_date_range(client, session):
    """Asset outside date range -> not in branch items."""
    settings = await create_settings(session)
    pl_source = await create_playlist(session, name="Source", mode="advanced")
    pl_target = await create_playlist(session, name="Target")
    flow = await create_trigger_flow(session)
    pl_source.trigger_flow_id = flow.id

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Asset with future start_date (not yet active)
    future_asset = await create_asset(
        session, name="future.png", uri="future.png",
        start_date=now + timedelta(days=30),
    )
    # Asset with past end_date (expired)
    expired_asset = await create_asset(
        session, name="expired.png", uri="expired.png",
        end_date=now - timedelta(days=1),
    )
    # Normal active asset
    active_asset = await create_asset(session, name="active.png", uri="active.png")

    await create_playlist_item(session, pl_target.id, future_asset.id, order=0)
    await create_playlist_item(session, pl_target.id, expired_asset.id, order=1)
    await create_playlist_item(session, pl_target.id, active_asset.id, order=2)

    await create_trigger_branch(
        session, flow.id, pl_source.id, pl_target.id,
        trigger_type="keyboard",
        trigger_config='{"key": "1"}',
    )
    device = await create_device(session, playlist_id=pl_source.id)
    token, plaintext = await create_token(session, role="device", device_id=device.id)
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist",
        headers=auth_header(plaintext),
    )
    data = resp.json()
    target_items = data["trigger_flow"]["branches"][0]["target_playlist"]["items"]
    assert len(target_items) == 1
    assert target_items[0]["asset"]["name"] == "active.png"


async def test_trigger_flow_hash_changes_on_webhook_fire(client, session):
    """Fire webhook -> device playlist hash changes."""
    settings = await create_settings(session)
    pl_source = await create_playlist(session, name="Source", mode="advanced")
    pl_target = await create_playlist(session, name="Target")
    flow = await create_trigger_flow(session)
    pl_source.trigger_flow_id = flow.id

    asset = await create_asset(session, name="img.png")
    await create_playlist_item(session, pl_target.id, asset.id, order=0)

    # Also need an admin token for creating the branch via API
    _, admin_token = await create_token(session, role="admin")
    await session.commit()

    # Create webhook branch via API so we get the auto-generated token
    resp = await client.post(
        f"/api/trigger-flows/{flow.id}/branches",
        json={
            "source_playlist_id": pl_source.id,
            "target_playlist_id": pl_target.id,
            "trigger_type": "webhook",
            "trigger_config": {},
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201
    branch_data = resp.json()
    branch_id = branch_data["id"]
    tc = branch_data["trigger_config"]
    if isinstance(tc, str):
        tc = json_mod.loads(tc)
    wh_token = tc["token"]

    device = await create_device(session, playlist_id=pl_source.id)
    _, dev_plaintext = await create_token(session, role="device", device_id=device.id)
    await session.commit()

    # Get hash before webhook fire
    resp1 = await client.get(
        f"/api/devices/{device.id}/playlist",
        headers=auth_header(dev_plaintext),
    )
    hash_before = resp1.json()["hash"]

    # Fire the webhook
    resp_fire = await client.post(
        f"/api/triggers/webhook/{branch_id}",
        json={"token": wh_token},
    )
    assert resp_fire.status_code == 200

    # Get hash after webhook fire
    resp2 = await client.get(
        f"/api/devices/{device.id}/playlist",
        headers=auth_header(dev_plaintext),
    )
    hash_after = resp2.json()["hash"]

    assert hash_before != hash_after


async def test_no_trigger_flow_when_simple_mode(client, session):
    """Playlist mode='simple' with no trigger_flow_id -> no trigger_flow in response."""
    settings = await create_settings(session)
    pl = await create_playlist(session, name="Simple PL", mode="simple")
    asset = await create_asset(session, name="img.png")
    await create_playlist_item(session, pl.id, asset.id, order=0)

    device = await create_device(session, playlist_id=pl.id)
    _, plaintext = await create_token(session, role="device", device_id=device.id)
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist",
        headers=auth_header(plaintext),
    )
    data = resp.json()
    assert "trigger_flow" not in data


async def test_trigger_flow_target_settings_override(client, session):
    """Target playlist has per-playlist settings -> reflected in branch.target_playlist.settings."""
    settings = await create_settings(
        session,
        transition_duration=1.0,
        transition_type="fade",
        default_duration=10,
        shuffle=False,
    )
    pl_source = await create_playlist(session, name="Source", mode="advanced")
    pl_target = await create_playlist(
        session, name="Target",
        transition_duration=2.5,
        transition_type="slide",
        default_duration=20,
        shuffle=True,
    )
    flow = await create_trigger_flow(session)
    pl_source.trigger_flow_id = flow.id

    asset = await create_asset(session, name="img.png")
    await create_playlist_item(session, pl_target.id, asset.id, order=0)

    await create_trigger_branch(
        session, flow.id, pl_source.id, pl_target.id,
        trigger_type="keyboard",
        trigger_config='{"key": "1"}',
    )
    device = await create_device(session, playlist_id=pl_source.id)
    _, plaintext = await create_token(session, role="device", device_id=device.id)
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist",
        headers=auth_header(plaintext),
    )
    data = resp.json()
    target_settings = data["trigger_flow"]["branches"][0]["target_playlist"]["settings"]

    assert target_settings["transition_duration"] == 2.5
    assert target_settings["transition_type"] == "slide"
    assert target_settings["default_duration"] == 20
    assert target_settings["shuffle"] is True
