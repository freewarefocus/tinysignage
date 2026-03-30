"""Tests for storage usage endpoint. [FT-15.*]"""

from tests.factories import create_token
from tests.helpers import auth_header


async def test_get_storage_usage(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/storage", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "disk" in data
    assert "media" in data


async def test_storage_viewer_can_read(client, session):
    _, token = await create_token(session, role="viewer")
    await session.commit()
    resp = await client.get("/api/storage", headers=auth_header(token))
    assert resp.status_code == 200
