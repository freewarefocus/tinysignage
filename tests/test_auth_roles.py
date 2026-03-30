"""Tests for role hierarchy and permission boundary enforcement. [FT-1.*]"""

from app.auth import ROLE_HIERARCHY
from tests.factories import (
    create_token, create_settings, create_playlist, create_device,
    create_asset, create_playlist_item,
)
from tests.helpers import auth_header, seed_defaults


# ── Role Matrix Tests ──────────────────────────────────────────────


async def test_admin_can_access_admin_endpoints(client, session):
    """Admin token → GET /api/users → 200"""
    _, token = await create_token(session, role="admin")
    await session.commit()
    resp = await client.get("/api/users", headers=auth_header(token))
    assert resp.status_code == 200


async def test_editor_cannot_access_admin_endpoints(client, session):
    """Editor token → GET /api/users → 403"""
    _, token = await create_token(session, role="editor")
    await session.commit()
    resp = await client.get("/api/users", headers=auth_header(token))
    assert resp.status_code == 403


async def test_viewer_cannot_access_admin_endpoints(client, session):
    """Viewer token → GET /api/users → 403"""
    _, token = await create_token(session, role="viewer")
    await session.commit()
    resp = await client.get("/api/users", headers=auth_header(token))
    assert resp.status_code == 403


async def test_device_cannot_access_admin_endpoints(client, session):
    """Device token → GET /api/users → 403"""
    device = await create_device(session)
    _, token = await create_token(session, role="device", device_id=device.id)
    await session.commit()
    resp = await client.get("/api/users", headers=auth_header(token))
    assert resp.status_code == 403


async def test_admin_can_access_editor_endpoints(client, session):
    """Admin token → POST /api/playlists → 201"""
    _, token = await create_token(session, role="admin")
    await session.commit()
    resp = await client.post(
        "/api/playlists", json={"name": "Admin Playlist"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201


async def test_editor_can_access_editor_endpoints(client, session):
    """Editor token → POST /api/playlists → 201"""
    _, token = await create_token(session, role="editor")
    await session.commit()
    resp = await client.post(
        "/api/playlists", json={"name": "Editor Playlist"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201


async def test_viewer_cannot_access_editor_endpoints(client, session):
    """Viewer token → POST /api/playlists → 403"""
    _, token = await create_token(session, role="viewer")
    await session.commit()
    resp = await client.post(
        "/api/playlists", json={"name": "Nope"},
        headers=auth_header(token),
    )
    assert resp.status_code == 403


async def test_device_cannot_access_editor_endpoints(client, session):
    """Device token → POST /api/playlists → 403"""
    device = await create_device(session)
    _, token = await create_token(session, role="device", device_id=device.id)
    await session.commit()
    resp = await client.post(
        "/api/playlists", json={"name": "Nope"},
        headers=auth_header(token),
    )
    assert resp.status_code == 403


async def test_admin_can_access_viewer_endpoints(client, session):
    """Admin token → GET /api/playlists → 200"""
    _, token = await create_token(session, role="admin")
    await session.commit()
    resp = await client.get("/api/playlists", headers=auth_header(token))
    assert resp.status_code == 200


async def test_editor_can_access_viewer_endpoints(client, session):
    """Editor token → GET /api/playlists → 200"""
    _, token = await create_token(session, role="editor")
    await session.commit()
    resp = await client.get("/api/playlists", headers=auth_header(token))
    assert resp.status_code == 200


async def test_viewer_can_access_viewer_endpoints(client, session):
    """Viewer token → GET /api/playlists → 200"""
    _, token = await create_token(session, role="viewer")
    await session.commit()
    resp = await client.get("/api/playlists", headers=auth_header(token))
    assert resp.status_code == 200


async def test_device_cannot_access_viewer_endpoints(client, session):
    """Device token → GET /api/playlists → 403"""
    device = await create_device(session)
    _, token = await create_token(session, role="device", device_id=device.id)
    await session.commit()
    resp = await client.get("/api/playlists", headers=auth_header(token))
    assert resp.status_code == 403


async def test_device_can_access_device_endpoints(client, session):
    """Device token → GET /api/devices/{id}/playlist → 200"""
    await create_settings(session)
    pl = await create_playlist(session)
    asset = await create_asset(session)
    await create_playlist_item(session, pl.id, asset.id)
    device = await create_device(session, playlist_id=pl.id)
    _, token = await create_token(session, role="device", device_id=device.id)
    await session.commit()
    resp = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_admin_cannot_access_device_endpoints(client, session):
    """Admin token → GET /api/devices/{id}/playlist → 403"""
    await create_settings(session)
    pl = await create_playlist(session)
    device = await create_device(session, playlist_id=pl.id)
    _, token = await create_token(session, role="admin")
    await session.commit()
    resp = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(token),
    )
    assert resp.status_code == 403


# ── Auth Header Tests ──────────────────────────────────────────────


async def test_missing_auth_header(client):
    """No header → 401"""
    resp = await client.get("/api/playlists")
    assert resp.status_code == 401
    assert "Missing Authorization header" in resp.json()["detail"]


async def test_empty_bearer_token(client):
    """Bearer (empty) → 401"""
    resp = await client.get(
        "/api/playlists", headers={"Authorization": "Bearer "},
    )
    assert resp.status_code == 401


async def test_malformed_auth_header(client):
    """Basic abc123 → 401"""
    resp = await client.get(
        "/api/playlists", headers={"Authorization": "Basic abc123"},
    )
    assert resp.status_code == 401


async def test_invalid_token_string(client):
    """Bearer invalid_token_string → 401"""
    resp = await client.get(
        "/api/playlists", headers={"Authorization": "Bearer invalid_token_string"},
    )
    assert resp.status_code == 401


async def test_token_without_prefix(client):
    """Bearer abc... (no ts_ prefix) → 401"""
    resp = await client.get(
        "/api/playlists",
        headers={"Authorization": "Bearer abcdef1234567890abcdef1234567890abcdef1234567890ab"},
    )
    assert resp.status_code == 401


# ── Role Hierarchy Function Tests (unit-level) ────────────────────


async def test_role_hierarchy_values():
    """ROLE_HIERARCHY has admin=3, editor=2, viewer=1, device=0"""
    assert ROLE_HIERARCHY["admin"] == 3
    assert ROLE_HIERARCHY["editor"] == 2
    assert ROLE_HIERARCHY["viewer"] == 1
    assert ROLE_HIERARCHY["device"] == 0


async def test_require_editor_accepts_admin(client, session):
    """Admin token passes require_editor check (POST /api/playlists)."""
    _, token = await create_token(session, role="admin")
    await session.commit()
    resp = await client.post(
        "/api/playlists", json={"name": "Via Admin"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201


async def test_require_viewer_accepts_editor(client, session):
    """Editor token passes require_viewer check (GET /api/playlists)."""
    _, token = await create_token(session, role="editor")
    await session.commit()
    resp = await client.get("/api/playlists", headers=auth_header(token))
    assert resp.status_code == 200


async def test_require_viewer_rejects_device(client, session):
    """Device token fails require_viewer (GET /api/playlists → 403)."""
    device = await create_device(session)
    _, token = await create_token(session, role="device", device_id=device.id)
    await session.commit()
    resp = await client.get("/api/playlists", headers=auth_header(token))
    assert resp.status_code == 403


async def test_require_device_rejects_admin(client, session):
    """Admin token fails require_device (GET /api/devices/{id}/playlist → 403)."""
    await create_settings(session)
    pl = await create_playlist(session)
    device = await create_device(session, playlist_id=pl.id)
    _, token = await create_token(session, role="admin")
    await session.commit()
    resp = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(token),
    )
    assert resp.status_code == 403


async def test_require_admin_rejects_editor(client, session):
    """Editor token fails require_admin (GET /api/users → 403)."""
    _, token = await create_token(session, role="editor")
    await session.commit()
    resp = await client.get("/api/users", headers=auth_header(token))
    assert resp.status_code == 403
