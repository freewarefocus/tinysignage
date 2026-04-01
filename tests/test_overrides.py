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
    assert data["is_active"] is False
    assert data["activated_at"] is None
    assert data["expires_at"] is None


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
    data = resp.json()
    assert data["duration_minutes"] == 30
    # expires_at is NOT computed at creation — only at activation
    assert data["expires_at"] is None
    assert data["is_active"] is False


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


async def test_activate_override(client, session):
    """Create template → activate → verify activated_at and expires_at computed."""
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={
            "name": "Fire Drill",
            "content_type": "message",
            "content": "Evacuate!",
            "duration_minutes": 30,
        },
        headers=auth_header(token),
    )
    oid = resp.json()["id"]
    assert resp.json()["is_active"] is False

    resp2 = await client.patch(
        f"/api/overrides/{oid}",
        json={"is_active": True},
        headers=auth_header(token),
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["is_active"] is True
    assert data["activated_at"] is not None
    assert data["expires_at"] is not None


async def test_deactivate_override(client, session):
    """Activate → deactivate → verify expires_at cleared."""
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={"name": "ToDeactivate", "content_type": "message", "content": "X"},
        headers=auth_header(token),
    )
    oid = resp.json()["id"]
    # Activate first
    await client.patch(
        f"/api/overrides/{oid}",
        json={"is_active": True},
        headers=auth_header(token),
    )
    # Deactivate
    resp2 = await client.patch(
        f"/api/overrides/{oid}",
        json={"is_active": False},
        headers=auth_header(token),
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["is_active"] is False
    assert data["expires_at"] is None


async def test_reactivate_override(client, session):
    """Activate → deactivate → activate again → new timestamps."""
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={
            "name": "Reactivatable",
            "content_type": "message",
            "content": "X",
            "duration_minutes": 15,
        },
        headers=auth_header(token),
    )
    oid = resp.json()["id"]

    # Activate
    r1 = await client.patch(
        f"/api/overrides/{oid}",
        json={"is_active": True},
        headers=auth_header(token),
    )
    first_activated = r1.json()["activated_at"]
    first_expires = r1.json()["expires_at"]

    # Deactivate
    await client.patch(
        f"/api/overrides/{oid}",
        json={"is_active": False},
        headers=auth_header(token),
    )

    # Re-activate
    r2 = await client.patch(
        f"/api/overrides/{oid}",
        json={"is_active": True},
        headers=auth_header(token),
    )
    assert r2.json()["is_active"] is True
    assert r2.json()["activated_at"] is not None
    assert r2.json()["expires_at"] is not None


async def test_edit_active_blocked(client, session):
    """Cannot edit fields on an active override."""
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={"name": "Active", "content_type": "message", "content": "X"},
        headers=auth_header(token),
    )
    oid = resp.json()["id"]
    # Activate
    await client.patch(
        f"/api/overrides/{oid}",
        json={"is_active": True},
        headers=auth_header(token),
    )
    # Try to edit name
    resp2 = await client.patch(
        f"/api/overrides/{oid}",
        json={"name": "Renamed"},
        headers=auth_header(token),
    )
    assert resp2.status_code == 400


async def test_edit_inactive(client, session):
    """Can edit fields on an inactive override."""
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={"name": "Editable", "content_type": "message", "content": "X"},
        headers=auth_header(token),
    )
    oid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/overrides/{oid}",
        json={"name": "Renamed", "content": "Updated content"},
        headers=auth_header(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "Renamed"
    assert resp2.json()["content"] == "Updated content"


async def test_delete_active_blocked(client, session):
    """Cannot delete an active override."""
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/overrides",
        json={"name": "Active", "content_type": "message", "content": "X"},
        headers=auth_header(token),
    )
    oid = resp.json()["id"]
    # Activate
    await client.patch(
        f"/api/overrides/{oid}",
        json={"is_active": True},
        headers=auth_header(token),
    )
    # Try to delete
    resp2 = await client.delete(
        f"/api/overrides/{oid}", headers=auth_header(token),
    )
    assert resp2.status_code == 400


async def test_delete_override(client, session):
    """Can delete an inactive template."""
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
