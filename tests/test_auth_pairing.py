"""Tests for device pairing flow end-to-end. [FT-4.6]-[FT-4.9]"""

import re
from datetime import datetime, timezone, timedelta

from app.auth import generate_pairing_code, hash_pairing_code
from tests.factories import create_token, create_settings, create_playlist, create_device
from tests.helpers import auth_header


# ── Pairing Code Generation ───────────────────────────────────────


async def test_pairing_code_format():
    """6 chars, uppercase alphanumeric."""
    code = generate_pairing_code()
    assert len(code) == 6
    assert re.match(r"^[A-Z0-9]{6}$", code)


async def test_pairing_code_unique():
    """Two calls produce different codes."""
    c1 = generate_pairing_code()
    c2 = generate_pairing_code()
    assert c1 != c2


async def test_hash_pairing_code_case_insensitive():
    """hash('ABC123') == hash('abc123')."""
    assert hash_pairing_code("ABC123") == hash_pairing_code("abc123")


async def test_hash_pairing_code_is_sha256():
    """Hash length is 64 hex chars."""
    h = hash_pairing_code("TEST01")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


# ── Full Pairing Flow (E2E via API) ──────────────────────────────


async def test_full_pairing_flow(client, session):
    """Admin creates device → gets pairing code → register → token works."""
    await create_settings(session)
    await create_playlist(session, is_default=True)
    _, admin_token = await create_token(session, role="admin")
    await session.commit()

    # Create device (returns pairing code)
    resp = await client.post(
        "/api/devices", json={"name": "Lobby TV"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201
    code = resp.json()["pairing_code"]
    device_id = resp.json()["id"]

    # Register with pairing code (public endpoint)
    resp2 = await client.post("/api/devices/register", json={"code": code})
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["device_id"] == device_id
    assert "token" in data

    # Device token works for device endpoint
    dev_token = data["token"]
    resp3 = await client.get(
        f"/api/devices/{device_id}/playlist",
        headers=auth_header(dev_token),
    )
    assert resp3.status_code == 200


async def test_pairing_code_expires(client, session):
    """Manually set registration_expires to past → register → 400."""
    device = await create_device(session)
    code = generate_pairing_code()
    device.registration_code = hash_pairing_code(code)
    device.registration_expires = (
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    )
    await session.commit()
    resp = await client.post("/api/devices/register", json={"code": code})
    assert resp.status_code == 400


async def test_pairing_code_single_use(client, session):
    """Register once (success) → register again with same code → 400."""
    await create_settings(session)
    await create_playlist(session, is_default=True)
    _, admin_token = await create_token(session, role="admin")
    await session.commit()

    resp = await client.post(
        "/api/devices", json={"name": "TV"},
        headers=auth_header(admin_token),
    )
    code = resp.json()["pairing_code"]

    resp2 = await client.post("/api/devices/register", json={"code": code})
    assert resp2.status_code == 200

    resp3 = await client.post("/api/devices/register", json={"code": code})
    assert resp3.status_code == 400


async def test_pairing_code_wrong_code(client, session):
    """Register with wrong code → 400."""
    resp = await client.post("/api/devices/register", json={"code": "ZZZZZZ"})
    assert resp.status_code == 400


async def test_pairing_code_empty(client, session):
    """Register with empty code → 400."""
    resp = await client.post("/api/devices/register", json={"code": ""})
    assert resp.status_code == 400


async def test_generate_new_pairing_code_for_existing_device(client, session):
    """POST /api/devices/{id}/pairing-code → new code works."""
    await create_settings(session)
    await create_playlist(session, is_default=True)
    _, admin_token = await create_token(session, role="admin")
    device = await create_device(session)
    await session.commit()

    # Generate a new pairing code
    resp = await client.post(
        f"/api/devices/{device.id}/pairing-code",
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    new_code = resp.json()["code"]

    # Register with the new code
    resp2 = await client.post("/api/devices/register", json={"code": new_code})
    assert resp2.status_code == 200
    assert resp2.json()["device_id"] == device.id


async def test_pairing_token_is_device_role(client, session):
    """Token from pairing has role='device' and device_id set."""
    await create_settings(session)
    await create_playlist(session, is_default=True)
    _, admin_token = await create_token(session, role="admin")
    await session.commit()

    resp = await client.post(
        "/api/devices", json={"name": "Role Check TV"},
        headers=auth_header(admin_token),
    )
    code = resp.json()["pairing_code"]
    device_id = resp.json()["id"]

    resp2 = await client.post("/api/devices/register", json={"code": code})
    dev_token = resp2.json()["token"]

    # Device token should access device endpoint (proves role=device)
    resp3 = await client.get(
        f"/api/devices/{device_id}/playlist",
        headers=auth_header(dev_token),
    )
    assert resp3.status_code == 200

    # Device token should NOT access viewer endpoints (proves role!=viewer+)
    resp4 = await client.get("/api/playlists", headers=auth_header(dev_token))
    assert resp4.status_code == 403


async def test_pairing_token_name_includes_device(client, session):
    """Token name is 'Device: {device_name}' — verified via /api/tokens list."""
    await create_settings(session)
    await create_playlist(session, is_default=True)
    _, admin_token = await create_token(session, role="admin")
    await session.commit()

    resp = await client.post(
        "/api/devices", json={"name": "Named TV"},
        headers=auth_header(admin_token),
    )
    code = resp.json()["pairing_code"]

    await client.post("/api/devices/register", json={"code": code})

    # List all tokens and find the device one
    resp3 = await client.get("/api/tokens", headers=auth_header(admin_token))
    tokens = resp3.json()
    device_tokens = [t for t in tokens if t["role"] == "device"]
    assert any(t["name"] == "Device: Named TV" for t in device_tokens)
