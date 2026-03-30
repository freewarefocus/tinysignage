"""Tests for emergency override endpoints. [FT-8.*]"""

from datetime import datetime, timezone, timedelta

from tests.factories import create_token, create_playlist, create_device
from tests.helpers import auth_header


async def test_list_overrides_empty(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/overrides", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_message_override(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={
            "name": "Emergency",
            "content_type": "message",
            "content": "Building evacuation!",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content_type"] == "message"
    assert data["content"] == "Building evacuation!"


async def test_create_playlist_override(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={
            "name": "Special",
            "content_type": "playlist",
            "content": pl.id,
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["content_type"] == "playlist"


async def test_create_override_with_expiry(client, session):
    _, token = await create_token(session)
    expires = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={
            "name": "Timed",
            "content_type": "message",
            "content": "Test",
            "expires_at": expires,
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["expires_at"] is not None


async def test_create_override_with_duration(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={
            "name": "30min",
            "content_type": "message",
            "content": "Test",
            "duration_minutes": 30,
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["expires_at"] is not None


async def test_create_override_target_device(client, session):
    _, token = await create_token(session)
    device = await create_device(session)
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={
            "name": "Device Override",
            "content_type": "message",
            "content": "Test",
            "target_type": "device",
            "target_id": device.id,
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["target_type"] == "device"


async def test_create_override_invalid_target(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={
            "name": "Bad Target",
            "content_type": "message",
            "content": "Test",
            "target_type": "device",
            "target_id": "nonexistent",
        },
        headers=auth_header(token),
    )
    assert resp.status_code in (400, 404)


async def test_update_override_deactivate(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={"name": "ToDeactivate", "content_type": "message", "content": "X"},
        headers=auth_header(token),
    )
    oid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/overrides/{oid}",
        json={"is_active": False},
        headers=auth_header(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["is_active"] is False


async def test_delete_override(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={"name": "ToDelete", "content_type": "message", "content": "X"},
        headers=auth_header(token),
    )
    oid = resp.json()["id"]
    resp2 = await client.delete(
        f"/api/overrides/{oid}", headers=auth_header(token),
    )
    assert resp2.status_code == 200


async def test_override_editor_forbidden(client, session):
    _, token = await create_token(session, role="editor")
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={"name": "Nope", "content_type": "message", "content": "X"},
        headers=auth_header(token),
    )
    assert resp.status_code == 403
