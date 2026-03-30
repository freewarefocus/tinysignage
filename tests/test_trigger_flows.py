"""Tests for trigger flow and branch endpoints. [FT-17.*]"""

import json as json_mod

from tests.factories import (
    create_token, create_playlist, create_trigger_flow, create_trigger_branch,
)
from tests.helpers import auth_header


async def test_list_flows_empty(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/trigger-flows", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_flow(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/trigger-flows",
        json={"name": "Interactive Menu"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Interactive Menu"


async def test_create_flow_no_name(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/trigger-flows", json={}, headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_get_flow_with_branches(client, session):
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    src = await create_playlist(session, name="src")
    tgt = await create_playlist(session, name="tgt")
    await create_trigger_branch(session, flow.id, src.id, tgt.id)
    await session.commit()
    resp = await client.get(
        f"/api/trigger-flows/{flow.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "branches" in data
    assert len(data["branches"]) == 1


async def test_update_flow(client, session):
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    await session.commit()
    resp = await client.patch(
        f"/api/trigger-flows/{flow.id}",
        json={"name": "Renamed Flow"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Flow"


async def test_delete_flow(client, session):
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    await session.commit()
    resp = await client.delete(
        f"/api/trigger-flows/{flow.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_delete_flow_clears_playlist_ref(client, session):
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    pl = await create_playlist(session, trigger_flow_id=flow.id)
    await session.commit()
    await client.delete(
        f"/api/trigger-flows/{flow.id}", headers=auth_header(token),
    )
    resp = await client.get(
        f"/api/playlists/{pl.id}", headers=auth_header(token),
    )
    assert resp.json()["trigger_flow_id"] is None


async def test_add_branch(client, session):
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


async def test_add_branch_invalid_type(client, session):
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
            "trigger_type": "invalid_type",
            "trigger_config": {},
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_add_branch_auto_webhook_token(client, session):
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
            "trigger_config": {},
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    config = resp.json()["trigger_config"]
    if isinstance(config, str):
        config = json_mod.loads(config)
    assert "token" in config


async def test_update_branch(client, session):
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    src = await create_playlist(session, name="src")
    tgt = await create_playlist(session, name="tgt")
    branch = await create_trigger_branch(session, flow.id, src.id, tgt.id)
    await session.commit()
    resp = await client.patch(
        f"/api/trigger-branches/{branch.id}",
        json={"priority": 5},
        headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_delete_branch(client, session):
    _, token = await create_token(session)
    flow = await create_trigger_flow(session)
    src = await create_playlist(session, name="src")
    tgt = await create_playlist(session, name="tgt")
    branch = await create_trigger_branch(session, flow.id, src.id, tgt.id)
    await session.commit()
    resp = await client.delete(
        f"/api/trigger-branches/{branch.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200
