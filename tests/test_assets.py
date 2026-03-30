"""Tests for asset CRUD endpoints. [FT-2.*]"""

import io

from tests.factories import (
    create_token, create_settings, create_asset, create_playlist,
    create_playlist_item,
)
from tests.helpers import auth_header


async def test_list_assets_empty(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/assets", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_assets_with_data(client, session):
    _, token = await create_token(session)
    await create_asset(session, name="a.png")
    await create_asset(session, name="b.png")
    await session.commit()
    resp = await client.get("/api/assets", headers=auth_header(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_create_asset_image_upload(client, session, media_dir):
    await create_settings(session)
    await create_playlist(session, is_default=True)
    _, token = await create_token(session)
    await session.commit()
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(buf, format="PNG")
    buf.seek(0)
    files = {"file": ("test.png", buf, "image/png")}
    resp = await client.post("/api/assets", files=files, headers=auth_header(token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["asset_type"] == "image"
    assert data["name"] == "test.png"


async def test_create_asset_url_type(client, session):
    await create_settings(session)
    await create_playlist(session, is_default=True)
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/assets",
        data={"asset_type": "url", "url": "https://example.com", "name": "Example"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["asset_type"] == "url"
    assert data["uri"] == "https://example.com"


async def test_create_asset_no_auth(client):
    resp = await client.post("/api/assets")
    assert resp.status_code == 401


async def test_create_asset_viewer_forbidden(client, session):
    _, token = await create_token(session, role="viewer")
    await session.commit()
    resp = await client.post(
        "/api/assets",
        data={"asset_type": "url", "url": "https://example.com"},
        headers=auth_header(token),
    )
    assert resp.status_code == 403


async def test_get_asset(client, session):
    _, token = await create_token(session)
    asset = await create_asset(session)
    await session.commit()
    resp = await client.get(f"/api/assets/{asset.id}", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == asset.id


async def test_get_asset_not_found(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/assets/nonexistent", headers=auth_header(token))
    assert resp.status_code == 404


async def test_update_asset_name(client, session):
    _, token = await create_token(session)
    asset = await create_asset(session)
    await session.commit()
    resp = await client.patch(
        f"/api/assets/{asset.id}",
        json={"name": "renamed.png"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "renamed.png"


async def test_update_asset_duration(client, session):
    _, token = await create_token(session)
    asset = await create_asset(session)
    await session.commit()
    resp = await client.patch(
        f"/api/assets/{asset.id}",
        json={"duration": 30},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["duration"] == 30


async def test_update_asset_enable_disable(client, session):
    _, token = await create_token(session)
    asset = await create_asset(session)
    await session.commit()
    resp = await client.patch(
        f"/api/assets/{asset.id}",
        json={"is_enabled": False},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_enabled"] is False


async def test_delete_asset(client, session):
    _, token = await create_token(session)
    asset = await create_asset(session, asset_type="url", uri="https://example.com")
    await session.commit()
    resp = await client.delete(f"/api/assets/{asset.id}", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


async def test_delete_asset_not_found(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.delete("/api/assets/nonexistent", headers=auth_header(token))
    assert resp.status_code == 404


async def test_delete_asset_cascades_playlist_items(client, session):
    _, token = await create_token(session)
    playlist = await create_playlist(session)
    asset = await create_asset(session, asset_type="url", uri="https://example.com")
    await create_playlist_item(session, playlist.id, asset.id)
    await session.commit()
    resp = await client.delete(f"/api/assets/{asset.id}", headers=auth_header(token))
    assert resp.status_code == 200
    resp2 = await client.get(f"/api/playlists/{playlist.id}", headers=auth_header(token))
    assert len(resp2.json()["items"]) == 0


async def test_duplicate_asset(client, session):
    await create_settings(session)
    await create_playlist(session, is_default=True)
    _, token = await create_token(session)
    asset = await create_asset(
        session, asset_type="url", uri="https://example.com", duration=15,
    )
    await session.commit()
    resp = await client.post(
        f"/api/assets/{asset.id}/duplicate", headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["asset_type"] == "url"
    assert data["duration"] == 15
    assert data["id"] != asset.id


async def test_reorder_assets(client, session):
    _, token = await create_token(session)
    a1 = await create_asset(session, name="a.png", play_order=0)
    a2 = await create_asset(session, name="b.png", play_order=1)
    await session.commit()
    resp = await client.post(
        "/api/assets/reorder",
        json=[{"id": a2.id, "play_order": 0}, {"id": a1.id, "play_order": 1}],
        headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_get_asset_thumbnail_no_thumb(client, session):
    _, token = await create_token(session)
    asset = await create_asset(session)
    await session.commit()
    resp = await client.get(
        f"/api/assets/{asset.id}/thumbnail", headers=auth_header(token),
    )
    assert resp.status_code == 404


async def test_get_asset_content(client, session, media_dir):
    _, token = await create_token(session)
    (media_dir / "test.html").write_text("<h1>Hello</h1>")
    asset = await create_asset(
        session, name="test.html", asset_type="html", uri="test.html",
    )
    await session.commit()
    resp = await client.get(
        f"/api/assets/{asset.id}/content", headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert "<h1>Hello</h1>" in resp.text


async def test_replace_asset_file(client, session, media_dir):
    _, token = await create_token(session)
    (media_dir / "old.png").write_bytes(b"fake")
    asset = await create_asset(
        session, name="old.png", asset_type="image", uri="old.png",
    )
    await session.commit()
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1, 1)).save(buf, format="PNG")
    buf.seek(0)
    files = {"file": ("new.png", buf, "image/png")}
    resp = await client.put(
        f"/api/assets/{asset.id}/replace", files=files, headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["uri"] != "old.png"


async def test_create_asset_html_type(client, session, media_dir):
    await create_settings(session)
    await create_playlist(session, is_default=True)
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/assets",
        data={"asset_type": "html", "content": "<h1>Test</h1>", "name": "Test HTML"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["asset_type"] == "html"
