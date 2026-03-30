"""Tests for settings and control endpoints. [FT-12.*]"""

from tests.factories import create_token, create_settings
from tests.helpers import auth_header


async def test_get_settings(client, session):
    await create_settings(session)
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/settings", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["transition_duration"] == 1.0
    assert data["transition_type"] == "fade"
    assert data["default_duration"] == 10
    assert data["shuffle"] is False


async def test_update_settings_transition(client, session):
    await create_settings(session)
    _, token = await create_token(session)
    await session.commit()
    resp = await client.patch(
        "/api/settings",
        json={"transition_type": "slide"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_update_settings_duration(client, session):
    await create_settings(session)
    _, token = await create_token(session)
    await session.commit()
    resp = await client.patch(
        "/api/settings",
        json={"default_duration": 15},
        headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_update_settings_shuffle(client, session):
    await create_settings(session)
    _, token = await create_token(session)
    await session.commit()
    resp = await client.patch(
        "/api/settings",
        json={"shuffle": True},
        headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_update_settings_viewer_forbidden(client, session):
    await create_settings(session)
    _, token = await create_token(session, role="viewer")
    await session.commit()
    resp = await client.patch(
        "/api/settings",
        json={"shuffle": True},
        headers=auth_header(token),
    )
    assert resp.status_code == 403


async def test_get_status(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/status", headers=auth_header(token))
    assert resp.status_code == 200
    assert "running" in resp.json()


async def test_control_next(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post("/api/control/next", headers=auth_header(token))
    assert resp.status_code == 200


async def test_control_previous(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post("/api/control/previous", headers=auth_header(token))
    assert resp.status_code == 200
