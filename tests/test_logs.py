"""Tests for error log endpoints. [FT-16.*]"""

from tests.factories import create_token
from tests.helpers import auth_header


async def test_get_error_logs(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/logs/errors", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert "total" in data


async def test_clear_error_logs(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.delete("/api/logs/errors", headers=auth_header(token))
    assert resp.status_code == 200


async def test_clear_logs_viewer_forbidden(client, session):
    _, token = await create_token(session, role="viewer")
    await session.commit()
    resp = await client.delete("/api/logs/errors", headers=auth_header(token))
    assert resp.status_code == 403
