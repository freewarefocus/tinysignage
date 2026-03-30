"""Tests for device CRUD endpoints. [FT-4.*]"""

from datetime import datetime, timezone, timedelta

from app.auth import generate_pairing_code, hash_pairing_code
from tests.factories import (
    create_token, create_settings, create_playlist, create_device,
    create_asset, create_playlist_item, create_device_group,
    add_device_to_group,
)
from tests.helpers import auth_header


async def test_list_devices_empty(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/devices", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_device(client, session):
    await create_settings(session)
    await create_playlist(session, is_default=True)
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/devices", json={"name": "Lobby TV"}, headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Lobby TV"
    assert "pairing_code" in data


async def test_create_device_auto_default_playlist(client, session):
    await create_settings(session)
    pl = await create_playlist(session, is_default=True)
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/devices", json={}, headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["playlist_id"] == pl.id


async def test_get_device(client, session):
    _, token = await create_token(session)
    device = await create_device(session)
    await session.commit()
    resp = await client.get(
        f"/api/devices/{device.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == device.id


async def test_get_device_not_found(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get(
        "/api/devices/nonexistent", headers=auth_header(token),
    )
    assert resp.status_code == 404


async def test_update_device_name(client, session):
    _, token = await create_token(session)
    device = await create_device(session)
    await session.commit()
    resp = await client.patch(
        f"/api/devices/{device.id}",
        json={"name": "Updated TV"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated TV"


async def test_update_device_playlist(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    device = await create_device(session)
    await session.commit()
    resp = await client.patch(
        f"/api/devices/{device.id}",
        json={"playlist_id": pl.id},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["playlist_id"] == pl.id


async def test_delete_device(client, session):
    _, token = await create_token(session)
    device = await create_device(session)
    await session.commit()
    resp = await client.delete(
        f"/api/devices/{device.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


async def test_delete_device_cascades(client, session):
    _, admin_token = await create_token(session)
    device = await create_device(session)
    _, dev_token = await create_token(session, role="device", device_id=device.id)
    group = await create_device_group(session)
    await add_device_to_group(session, device.id, group.id)
    await session.commit()
    resp = await client.delete(
        f"/api/devices/{device.id}", headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    # Device token should no longer work
    resp2 = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_token),
    )
    assert resp2.status_code in (401, 403, 404)


async def test_generate_pairing_code(client, session):
    _, token = await create_token(session)
    device = await create_device(session)
    await session.commit()
    resp = await client.post(
        f"/api/devices/{device.id}/pairing-code", headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "code" in data
    assert "expires_in" in data


async def test_register_with_pairing_code(client, session):
    await create_settings(session)
    await create_playlist(session, is_default=True)
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/devices", json={"name": "New TV"}, headers=auth_header(token),
    )
    code = resp.json()["pairing_code"]
    device_id = resp.json()["id"]
    resp2 = await client.post("/api/devices/register", json={"code": code})
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["device_id"] == device_id
    assert "token" in data


async def test_register_invalid_code(client):
    resp = await client.post("/api/devices/register", json={"code": "ZZZZZZ"})
    assert resp.status_code == 400


async def test_register_expired_code(client, session):
    device = await create_device(session)
    code = generate_pairing_code()
    device.registration_code = hash_pairing_code(code)
    device.registration_expires = (
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=15)
    )
    await session.commit()
    resp = await client.post("/api/devices/register", json={"code": code})
    assert resp.status_code == 400


async def test_pairing_code_single_use(client, session):
    await create_settings(session)
    await create_playlist(session, is_default=True)
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/devices", json={"name": "TV"}, headers=auth_header(token),
    )
    code = resp.json()["pairing_code"]
    resp2 = await client.post("/api/devices/register", json={"code": code})
    assert resp2.status_code == 200
    resp3 = await client.post("/api/devices/register", json={"code": code})
    assert resp3.status_code == 400


async def test_device_playlist_polling(client, session):
    await create_settings(session)
    pl = await create_playlist(session, name="Test PL")
    asset = await create_asset(session)
    await create_playlist_item(session, pl.id, asset.id)
    device = await create_device(session, playlist_id=pl.id)
    _, dev_token = await create_token(
        session, role="device", device_id=device.id,
    )
    await session.commit()
    resp = await client.get(
        f"/api/devices/{device.id}/playlist", headers=auth_header(dev_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "hash" in data
    assert "items" in data
    assert "settings" in data
    assert len(data["items"]) == 1
