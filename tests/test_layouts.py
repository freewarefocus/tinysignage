"""Tests for layout and zone endpoints. [FT-6.*]"""

from tests.factories import create_token, create_layout, create_zone, create_playlist
from tests.helpers import auth_header


async def test_list_layouts_empty(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/layouts", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_layout(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/layouts",
        json={"name": "Split Screen"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Split Screen"


async def test_get_layout_with_zones(client, session):
    _, token = await create_token(session)
    layout = await create_layout(session)
    await create_zone(session, layout.id)
    await session.commit()
    resp = await client.get(
        f"/api/layouts/{layout.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "zones" in data
    assert len(data["zones"]) == 1


async def test_update_layout(client, session):
    _, token = await create_token(session)
    layout = await create_layout(session)
    await session.commit()
    resp = await client.patch(
        f"/api/layouts/{layout.id}",
        json={"name": "New Name"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


async def test_delete_layout(client, session):
    _, token = await create_token(session)
    layout = await create_layout(session)
    await session.commit()
    resp = await client.delete(
        f"/api/layouts/{layout.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_delete_layout_cascades_zones(client, session):
    _, token = await create_token(session)
    layout = await create_layout(session)
    await create_zone(session, layout.id)
    await session.commit()
    await client.delete(
        f"/api/layouts/{layout.id}", headers=auth_header(token),
    )
    resp = await client.get(
        f"/api/layouts/{layout.id}", headers=auth_header(token),
    )
    assert resp.status_code == 404


async def test_create_zone(client, session):
    _, token = await create_token(session)
    layout = await create_layout(session)
    await session.commit()
    resp = await client.post(
        f"/api/layouts/{layout.id}/zones",
        json={"name": "Left", "zone_type": "main"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Left"


async def test_create_zone_with_playlist(client, session):
    _, token = await create_token(session)
    layout = await create_layout(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.post(
        f"/api/layouts/{layout.id}/zones",
        json={"name": "Main", "playlist_id": pl.id},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["playlist_id"] == pl.id


async def test_update_zone_position(client, session):
    _, token = await create_token(session)
    layout = await create_layout(session)
    zone = await create_zone(session, layout.id)
    await session.commit()
    resp = await client.patch(
        f"/api/layouts/{layout.id}/zones/{zone.id}",
        json={"x_percent": 50.0, "width_percent": 50.0},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["x_percent"] == 50.0


async def test_delete_zone(client, session):
    _, token = await create_token(session)
    layout = await create_layout(session)
    zone = await create_zone(session, layout.id)
    await session.commit()
    resp = await client.delete(
        f"/api/layouts/{layout.id}/zones/{zone.id}",
        headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_zone_types(client, session):
    _, token = await create_token(session)
    layout = await create_layout(session)
    await session.commit()
    for zt in ("main", "ticker", "sidebar", "pip"):
        resp = await client.post(
            f"/api/layouts/{layout.id}/zones",
            json={"name": f"{zt} zone", "zone_type": zt},
            headers=auth_header(token),
        )
        assert resp.status_code == 201
        assert resp.json()["zone_type"] == zt


async def test_zone_z_index(client, session):
    _, token = await create_token(session)
    layout = await create_layout(session)
    await session.commit()
    resp = await client.post(
        f"/api/layouts/{layout.id}/zones",
        json={"name": "Overlay", "z_index": 10},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["z_index"] == 10
