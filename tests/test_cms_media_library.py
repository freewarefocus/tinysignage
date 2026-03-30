"""CMS Media Library tests — Python equivalent of Phase 6 MediaLibrary.test.js.

Tests the asset listing API from the CMS media library's perspective:
empty state, populated list, and upload via file POST.

[FT-2.1, FT-2.2, FT-2.13]
"""

import io

from tests.factories import create_asset, create_playlist, create_settings, create_token
from tests.helpers import auth_header


async def test_media_library_empty_state(client, session):
    """GET /api/assets with no assets returns empty list."""
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/assets", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_media_library_lists_assets(client, session):
    """GET /api/assets returns asset cards with name, type, and URI."""
    _, token = await create_token(session)
    await create_asset(session, name="banner.png", asset_type="image", uri="banner.png")
    await create_asset(session, name="promo.mp4", asset_type="video", uri="promo.mp4")
    await create_asset(session, name="info.html", asset_type="html", uri="info.html")
    await session.commit()
    resp = await client.get("/api/assets", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    names = {a["name"] for a in data}
    assert names == {"banner.png", "promo.mp4", "info.html"}
    types = {a["asset_type"] for a in data}
    assert types == {"image", "video", "html"}


async def test_media_library_upload_url_asset(client, session):
    """POST /api/assets with url creates a URL-type asset (simulates upload zone)."""
    _, token = await create_token(session, role="editor")
    await session.commit()
    resp = await client.post(
        "/api/assets",
        data={"url": "https://example.com/slide", "name": "Web Slide", "asset_type": "url"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Web Slide"
    assert data["asset_type"] == "url"
    assert data["uri"] == "https://example.com/slide"
