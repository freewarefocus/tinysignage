"""Tests for device group endpoints. [FT-5.*]"""

from tests.factories import (
    create_token, create_device, create_device_group, create_playlist,
    add_device_to_group,
)
from tests.helpers import auth_header


async def test_list_groups_empty(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/groups", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_group(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/groups",
        json={"name": "Lobby Screens"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Lobby Screens"


async def test_get_group(client, session):
    _, token = await create_token(session)
    group = await create_device_group(session)
    await session.commit()
    resp = await client.get(
        f"/api/groups/{group.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert "members" in resp.json()


async def test_update_group(client, session):
    _, token = await create_token(session)
    group = await create_device_group(session)
    await session.commit()
    resp = await client.patch(
        f"/api/groups/{group.id}",
        json={"name": "Updated"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


async def test_delete_group(client, session):
    _, token = await create_token(session)
    group = await create_device_group(session)
    await session.commit()
    resp = await client.delete(
        f"/api/groups/{group.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_add_member(client, session):
    _, token = await create_token(session)
    group = await create_device_group(session)
    device = await create_device(session)
    await session.commit()
    resp = await client.post(
        f"/api/groups/{group.id}/members",
        json={"device_id": device.id},
        headers=auth_header(token),
    )
    assert resp.status_code in (200, 201)


async def test_add_member_device_not_found(client, session):
    _, token = await create_token(session)
    group = await create_device_group(session)
    await session.commit()
    resp = await client.post(
        f"/api/groups/{group.id}/members",
        json={"device_id": "nonexistent"},
        headers=auth_header(token),
    )
    assert resp.status_code == 404


async def test_remove_member(client, session):
    _, token = await create_token(session)
    group = await create_device_group(session)
    device = await create_device(session)
    await add_device_to_group(session, device.id, group.id)
    await session.commit()
    resp = await client.delete(
        f"/api/groups/{group.id}/members/{device.id}",
        headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_assign_playlist_to_group(client, session):
    _, token = await create_token(session)
    group = await create_device_group(session)
    device = await create_device(session)
    await add_device_to_group(session, device.id, group.id)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.post(
        f"/api/groups/{group.id}/assign-playlist",
        json={"playlist_id": pl.id},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


async def test_create_group_editor_forbidden(client, session):
    _, token = await create_token(session, role="editor")
    await session.commit()
    resp = await client.post(
        "/api/groups",
        json={"name": "Nope"},
        headers=auth_header(token),
    )
    assert resp.status_code == 403
