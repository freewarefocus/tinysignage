"""E2E tests for trigger system.

Tests: create flow → attach to playlist → poll → fire webhook → cleanup.

[FT-17.12]-[FT-17.16], [FT-20.10]
"""

import json

from tests.factories import (
    create_asset,
    create_device,
    create_playlist,
    create_playlist_item,
    create_settings,
    create_token,
    create_trigger_branch,
    create_trigger_flow,
)
from tests.helpers import auth_header


async def test_trigger_flow_in_device_polling(client, session):
    """Device poll includes trigger_flow with branches when playlist has one."""
    settings = await create_settings(session)
    source_pl = await create_playlist(session, name="Source", mode="advanced")
    source_asset = await create_asset(session, name="main.png", uri="main.png")
    await create_playlist_item(session, source_pl.id, source_asset.id, order=0)

    target_pl = await create_playlist(session, name="Target")
    target_asset = await create_asset(session, name="target.png", uri="target.png")
    await create_playlist_item(session, target_pl.id, target_asset.id, order=0)

    flow = await create_trigger_flow(session, name="Nav Flow")
    source_pl.trigger_flow_id = flow.id
    await create_trigger_branch(
        session, flow.id, source_pl.id, target_pl.id,
        trigger_type="keyboard",
        trigger_config=json.dumps({"key": "ArrowRight"}),
    )

    device = await create_device(session, playlist_id=source_pl.id)
    _, dev_pt = await create_token(session, role="device", device_id=device.id)
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_pt),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "trigger_flow" in data
    tf = data["trigger_flow"]
    assert tf["id"] == flow.id
    assert len(tf["branches"]) == 1
    branch = tf["branches"][0]
    assert branch["trigger_type"] == "keyboard"
    assert branch["target_playlist"]["name"] == "Target"
    assert len(branch["target_playlist"]["items"]) == 1


async def test_webhook_fire_changes_poll_hash(client, session):
    """Fire webhook → device poll hash changes due to last_webhook_fire update."""
    settings = await create_settings(session)
    source_pl = await create_playlist(session, name="Source", mode="advanced")
    source_asset = await create_asset(session, name="src.png", uri="src.png")
    await create_playlist_item(session, source_pl.id, source_asset.id, order=0)

    target_pl = await create_playlist(session, name="Target")
    target_asset = await create_asset(session, name="tgt.png", uri="tgt.png")
    await create_playlist_item(session, target_pl.id, target_asset.id, order=0)

    flow = await create_trigger_flow(session, name="Webhook Flow")
    source_pl.trigger_flow_id = flow.id
    branch = await create_trigger_branch(
        session, flow.id, source_pl.id, target_pl.id,
        trigger_type="webhook",
        trigger_config=json.dumps({"token": "secret123"}),
    )

    device = await create_device(session, playlist_id=source_pl.id)
    _, dev_pt = await create_token(session, role="device", device_id=device.id)
    await session.commit()

    # First poll — baseline hash
    resp1 = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_pt),
    )
    assert resp1.status_code == 200
    hash1 = resp1.json()["hash"]

    # Fire webhook
    resp = await client.post(
        f"/api/triggers/webhook/{branch.id}",
        json={"token": "secret123"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "triggered"

    # Second poll — hash should differ
    resp2 = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_pt),
    )
    assert resp2.status_code == 200
    hash2 = resp2.json()["hash"]
    assert hash1 != hash2


async def test_trigger_branch_target_playlist_items(client, session):
    """Branch target playlist items are included in trigger payload."""
    settings = await create_settings(session)
    source_pl = await create_playlist(session, name="Source", mode="advanced")
    source_asset = await create_asset(session, name="s.png", uri="s.png")
    await create_playlist_item(session, source_pl.id, source_asset.id, order=0)

    target_pl = await create_playlist(session, name="Target")
    t1 = await create_asset(session, name="slide1.png", uri="slide1.png")
    t2 = await create_asset(session, name="slide2.png", uri="slide2.png")
    await create_playlist_item(session, target_pl.id, t1.id, order=0)
    await create_playlist_item(session, target_pl.id, t2.id, order=1)

    flow = await create_trigger_flow(session, name="Content Flow")
    source_pl.trigger_flow_id = flow.id
    await create_trigger_branch(
        session, flow.id, source_pl.id, target_pl.id,
        trigger_type="touch_zone",
        trigger_config=json.dumps({"zone": "bottom-left"}),
    )

    device = await create_device(session, playlist_id=source_pl.id)
    _, dev_pt = await create_token(session, role="device", device_id=device.id)
    await session.commit()

    resp = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_pt),
    )
    assert resp.status_code == 200
    tf = resp.json()["trigger_flow"]
    target_items = tf["branches"][0]["target_playlist"]["items"]
    assert len(target_items) == 2
    names = [i["asset"]["name"] for i in target_items]
    assert names == ["slide1.png", "slide2.png"]


async def test_flow_deletion_cleans_up_playlist_ref(client, session):
    """Deleting a trigger flow nullifies playlist's trigger_flow_id."""
    _, token = await create_token(session, role="editor")
    flow = await create_trigger_flow(session, name="Temp Flow")
    playlist = await create_playlist(
        session, name="Attached PL", mode="advanced", trigger_flow_id=flow.id,
    )
    await session.commit()

    # Verify the reference is set
    resp = await client.get(
        f"/api/playlists/{playlist.id}", headers=auth_header(token),
    )
    assert resp.json()["trigger_flow_id"] == flow.id

    # Delete the flow
    resp = await client.delete(
        f"/api/trigger-flows/{flow.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200

    # Verify playlist's trigger_flow_id is now null
    resp = await client.get(
        f"/api/playlists/{playlist.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["trigger_flow_id"] is None
