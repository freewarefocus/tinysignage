"""Tests for widget endpoints. [FT-18.*]"""

from tests.factories import create_token
from tests.helpers import auth_header


async def test_list_widgets(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/widgets", headers=auth_header(token))
    assert resp.status_code == 200
    widgets = resp.json()
    assert len(widgets) >= 1


async def test_widgets_require_auth(client):
    resp = await client.get("/api/widgets")
    assert resp.status_code == 401


async def test_widgets_have_expected_fields(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/widgets", headers=auth_header(token))
    assert resp.status_code == 200
    for widget in resp.json():
        assert "id" in widget
        assert "name" in widget
        assert "html" in widget
