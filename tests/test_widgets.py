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


async def test_all_seven_widget_ids(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/widgets", headers=auth_header(token))
    assert resp.status_code == 200
    ids = [w["id"] for w in resp.json()]
    assert ids == ["clock", "date", "weather", "centered_text",
                   "heading_subtitle", "scrolling_text", "countdown"]


async def test_centered_text_contains_default_message(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/widgets", headers=auth_header(token))
    widget = next(w for w in resp.json() if w["id"] == "centered_text")
    assert "Today\\'s Special" in widget["html"]


async def test_scrolling_text_has_keyframes(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/widgets", headers=auth_header(token))
    widget = next(w for w in resp.json() if w["id"] == "scrolling_text")
    assert "@keyframes" in widget["html"]
    assert "translateX" in widget["html"]


async def test_countdown_has_setinterval_and_label(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/widgets", headers=auth_header(token))
    widget = next(w for w in resp.json() if w["id"] == "countdown")
    assert "setInterval" in widget["html"]
    assert "Grand Opening" in widget["html"]


async def test_heading_subtitle_contains_defaults(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/widgets", headers=auth_header(token))
    widget = next(w for w in resp.json() if w["id"] == "heading_subtitle")
    assert "WELCOME" in widget["html"]
    assert "to our store" in widget["html"]
