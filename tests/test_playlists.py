"""Tests for playlist CRUD endpoints. [FT-3.*]"""

from tests.factories import (
    create_token, create_settings, create_playlist, create_asset,
    create_playlist_item, create_device,
)
from tests.helpers import auth_header


async def test_list_playlists_empty(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/playlists", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_playlist(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/playlists", json={"name": "My Playlist"}, headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "My Playlist"


async def test_create_playlist_no_name(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/playlists", json={}, headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_get_playlist(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session, name="Test PL")
    await session.commit()
    resp = await client.get(
        f"/api/playlists/{pl.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test PL"
    assert "items" in data


async def test_get_playlist_not_found(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get(
        "/api/playlists/nonexistent", headers=auth_header(token),
    )
    assert resp.status_code == 404


async def test_update_playlist_name(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.patch(
        f"/api/playlists/{pl.id}",
        json={"name": "Renamed"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


async def test_update_playlist_mode(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.patch(
        f"/api/playlists/{pl.id}",
        json={"mode": "advanced"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "advanced"


async def test_delete_playlist(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.delete(
        f"/api/playlists/{pl.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


async def test_add_item_to_playlist(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    asset = await create_asset(session)
    await session.commit()
    resp = await client.post(
        f"/api/playlists/{pl.id}/items",
        json={"asset_id": asset.id},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["asset_id"] == asset.id


async def test_add_item_invalid_asset(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.post(
        f"/api/playlists/{pl.id}/items",
        json={"asset_id": "nonexistent"},
        headers=auth_header(token),
    )
    assert resp.status_code == 404


async def test_remove_item_from_playlist(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    asset = await create_asset(session)
    item = await create_playlist_item(session, pl.id, asset.id)
    await session.commit()
    resp = await client.delete(
        f"/api/playlists/{pl.id}/items/{item.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_reorder_playlist_items(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    a1 = await create_asset(session, name="a.png")
    a2 = await create_asset(session, name="b.png")
    i1 = await create_playlist_item(session, pl.id, a1.id, order=0)
    i2 = await create_playlist_item(session, pl.id, a2.id, order=1)
    await session.commit()
    resp = await client.post(
        f"/api/playlists/{pl.id}/reorder",
        json={"item_ids": [i2.id, i1.id]},
        headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_get_playlist_hash(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.get(
        f"/api/playlists/{pl.id}/hash", headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert "hash" in resp.json()


async def test_playlist_hash_changes_on_item_add(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    asset = await create_asset(session)
    await session.commit()
    resp1 = await client.get(
        f"/api/playlists/{pl.id}/hash", headers=auth_header(token),
    )
    hash1 = resp1.json()["hash"]
    await client.post(
        f"/api/playlists/{pl.id}/items",
        json={"asset_id": asset.id},
        headers=auth_header(token),
    )
    resp2 = await client.get(
        f"/api/playlists/{pl.id}/hash", headers=auth_header(token),
    )
    hash2 = resp2.json()["hash"]
    assert hash1 != hash2


async def test_bulk_preflight(client, session):
    await create_settings(session)
    _, token = await create_token(session)
    pl = await create_playlist(session)
    device = await create_device(session, playlist_id=pl.id)
    await session.commit()
    resp = await client.post(
        f"/api/playlists/{pl.id}/preflight",
        json={"device_ids": [device.id]},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["device_id"] == device.id
