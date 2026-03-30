"""Trigger flow & branch CRUD validation tests. [FT-17.*]"""

import json as json_mod

from tests.factories import (
    create_token, create_playlist, create_trigger_flow, create_trigger_branch,
)
from tests.helpers import auth_header


# --- Trigger Flow CRUD ---


async def test_create_flow(client, session):
    """POST /api/trigger-flows -> 201, returns id, name, branch_count=0."""
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/trigger-flows",
        json={"name": "Interactive Menu"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Interactive Menu"
    assert "id" in data
    assert data["branch_count"] == 0


async def test_create_flow_no_name(client, session):
    """POST /api/trigger-flows with no name -> 400."""
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/trigger-flows", json={}, headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_get_flow_with_branches(client, session):
    """Create flow + branch -> GET returns branches array with source/target names."""
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    src = await create_playlist(session, name="Source PL")
    tgt = await create_playlist(session, name="Target PL")
    await create_trigger_branch(session, flow.id, src.id, tgt.id)
    await session.commit()

    resp = await client.get(
        f"/api/trigger-flows/{flow.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "branches" in data
    assert len(data["branches"]) == 1
    branch = data["branches"][0]
    assert branch["source_playlist_name"] == "Source PL"
    assert branch["target_playlist_name"] == "Target PL"


async def test_update_flow_name(client, session):
    """PATCH /api/trigger-flows/{id} -> name updated."""
    _, token = await create_token(session)
    flow = await create_trigger_flow(session, name="Old Name")
    await session.commit()

    resp = await client.patch(
        f"/api/trigger-flows/{flow.id}",
        json={"name": "New Name"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


async def test_delete_flow_clears_playlist_refs(client, session):
    """Playlist has trigger_flow_id set -> delete flow -> playlist.trigger_flow_id is None."""
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    pl = await create_playlist(session, trigger_flow_id=flow.id)
    await session.commit()

    resp = await client.delete(
        f"/api/trigger-flows/{flow.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200

    resp = await client.get(
        f"/api/playlists/{pl.id}", headers=auth_header(token),
    )
    assert resp.json()["trigger_flow_id"] is None


# --- Trigger Branch CRUD ---


async def test_add_branch_keyboard(client, session):
    """trigger_type='keyboard' -> 201."""
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    src = await create_playlist(session, name="src")
    tgt = await create_playlist(session, name="tgt")
    await session.commit()

    resp = await client.post(
        f"/api/trigger-flows/{flow.id}/branches",
        json={
            "source_playlist_id": src.id,
            "target_playlist_id": tgt.id,
            "trigger_type": "keyboard",
            "trigger_config": {"key": "1"},
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["trigger_type"] == "keyboard"


async def test_add_branch_touch_zone(client, session):
    """trigger_type='touch_zone' -> 201."""
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    src = await create_playlist(session, name="src")
    tgt = await create_playlist(session, name="tgt")
    await session.commit()

    resp = await client.post(
        f"/api/trigger-flows/{flow.id}/branches",
        json={
            "source_playlist_id": src.id,
            "target_playlist_id": tgt.id,
            "trigger_type": "touch_zone",
            "trigger_config": {"x": 0, "y": 0, "w": 50, "h": 50},
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["trigger_type"] == "touch_zone"


async def test_add_branch_gpio(client, session):
    """trigger_type='gpio' -> 201."""
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    src = await create_playlist(session, name="src")
    tgt = await create_playlist(session, name="tgt")
    await session.commit()

    resp = await client.post(
        f"/api/trigger-flows/{flow.id}/branches",
        json={
            "source_playlist_id": src.id,
            "target_playlist_id": tgt.id,
            "trigger_type": "gpio",
            "trigger_config": {"pin": 17},
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["trigger_type"] == "gpio"


async def test_add_branch_timeout(client, session):
    """trigger_type='timeout' -> 201."""
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    src = await create_playlist(session, name="src")
    tgt = await create_playlist(session, name="tgt")
    await session.commit()

    resp = await client.post(
        f"/api/trigger-flows/{flow.id}/branches",
        json={
            "source_playlist_id": src.id,
            "target_playlist_id": tgt.id,
            "trigger_type": "timeout",
            "trigger_config": {"seconds": 30},
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["trigger_type"] == "timeout"


async def test_add_branch_loop_count(client, session):
    """trigger_type='loop_count' -> 201."""
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    src = await create_playlist(session, name="src")
    tgt = await create_playlist(session, name="tgt")
    await session.commit()

    resp = await client.post(
        f"/api/trigger-flows/{flow.id}/branches",
        json={
            "source_playlist_id": src.id,
            "target_playlist_id": tgt.id,
            "trigger_type": "loop_count",
            "trigger_config": {"count": 3},
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["trigger_type"] == "loop_count"


async def test_add_branch_invalid_type(client, session):
    """trigger_type='invalid' -> 400."""
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    src = await create_playlist(session, name="src")
    tgt = await create_playlist(session, name="tgt")
    await session.commit()

    resp = await client.post(
        f"/api/trigger-flows/{flow.id}/branches",
        json={
            "source_playlist_id": src.id,
            "target_playlist_id": tgt.id,
            "trigger_type": "invalid",
            "trigger_config": {},
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_add_branch_invalid_source_playlist(client, session):
    """source_playlist_id doesn't exist -> 404."""
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    tgt = await create_playlist(session, name="tgt")
    await session.commit()

    resp = await client.post(
        f"/api/trigger-flows/{flow.id}/branches",
        json={
            "source_playlist_id": "nonexistent-id",
            "target_playlist_id": tgt.id,
            "trigger_type": "keyboard",
            "trigger_config": {"key": "1"},
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 404
    assert "Source" in resp.json()["detail"]


async def test_add_branch_invalid_target_playlist(client, session):
    """target_playlist_id doesn't exist -> 404."""
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    src = await create_playlist(session, name="src")
    await session.commit()

    resp = await client.post(
        f"/api/trigger-flows/{flow.id}/branches",
        json={
            "source_playlist_id": src.id,
            "target_playlist_id": "nonexistent-id",
            "trigger_type": "keyboard",
            "trigger_config": {"key": "1"},
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 404
    assert "Target" in resp.json()["detail"]


async def test_add_branch_webhook_auto_token(client, session):
    """trigger_type='webhook', no token in config -> auto-generated token in trigger_config."""
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    src = await create_playlist(session, name="src")
    tgt = await create_playlist(session, name="tgt")
    await session.commit()

    resp = await client.post(
        f"/api/trigger-flows/{flow.id}/branches",
        json={
            "source_playlist_id": src.id,
            "target_playlist_id": tgt.id,
            "trigger_type": "webhook",
            "trigger_config": {},  # no token provided
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    config = data["trigger_config"]
    if isinstance(config, str):
        config = json_mod.loads(config)
    assert "token" in config
    assert len(config["token"]) == 16  # secrets.token_hex(8) = 16 chars
