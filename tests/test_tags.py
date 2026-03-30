"""Tests for tag CRUD endpoints. [FT-11.*]"""

from tests.factories import create_token, create_tag, create_asset
from tests.helpers import auth_header


async def test_list_tags_empty(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/tags", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_tag(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/tags",
        json={"name": "promo", "color": "#ff0000"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "promo"
    assert resp.json()["color"] == "#ff0000"


async def test_create_tag_duplicate_name(client, session):
    _, token = await create_token(session)
    await create_tag(session, name="unique")
    await session.commit()
    resp = await client.post(
        "/api/tags", json={"name": "unique"}, headers=auth_header(token),
    )
    assert resp.status_code == 409


async def test_update_tag(client, session):
    _, token = await create_token(session)
    tag = await create_tag(session)
    await session.commit()
    resp = await client.patch(
        f"/api/tags/{tag.id}",
        json={"name": "updated-tag"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "updated-tag"


async def test_delete_tag(client, session):
    _, token = await create_token(session)
    tag = await create_tag(session)
    await session.commit()
    resp = await client.delete(
        f"/api/tags/{tag.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_add_tag_to_asset(client, session):
    _, token = await create_token(session)
    asset = await create_asset(session)
    tag = await create_tag(session)
    await session.commit()
    resp = await client.post(
        f"/api/assets/{asset.id}/tags",
        json={"tag_id": tag.id},
        headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_remove_tag_from_asset(client, session):
    _, token = await create_token(session)
    asset = await create_asset(session)
    tag = await create_tag(session)
    await session.commit()
    await client.post(
        f"/api/assets/{asset.id}/tags",
        json={"tag_id": tag.id},
        headers=auth_header(token),
    )
    resp = await client.delete(
        f"/api/assets/{asset.id}/tags/{tag.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_get_asset_tags(client, session):
    _, token = await create_token(session)
    asset = await create_asset(session)
    tag = await create_tag(session)
    await session.commit()
    await client.post(
        f"/api/assets/{asset.id}/tags",
        json={"tag_id": tag.id},
        headers=auth_header(token),
    )
    resp = await client.get(
        f"/api/assets/{asset.id}/tags", headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == tag.name


async def test_add_duplicate_tag_to_asset(client, session):
    _, token = await create_token(session)
    asset = await create_asset(session)
    tag = await create_tag(session)
    await session.commit()
    await client.post(
        f"/api/assets/{asset.id}/tags",
        json={"tag_id": tag.id},
        headers=auth_header(token),
    )
    # Idempotent — should succeed
    resp = await client.post(
        f"/api/assets/{asset.id}/tags",
        json={"tag_id": tag.id},
        headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_delete_tag_cascades_asset_tags(client, session):
    _, token = await create_token(session)
    asset = await create_asset(session)
    tag = await create_tag(session)
    await session.commit()
    await client.post(
        f"/api/assets/{asset.id}/tags",
        json={"tag_id": tag.id},
        headers=auth_header(token),
    )
    await client.delete(f"/api/tags/{tag.id}", headers=auth_header(token))
    resp = await client.get(
        f"/api/assets/{asset.id}/tags", headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 0
