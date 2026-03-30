"""Tests for audit log endpoints. [FT-14.*]"""

from tests.factories import create_token, create_user
from tests.helpers import auth_header


async def test_list_audit_logs(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/audit", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert "total" in data


async def test_audit_log_created_on_mutation(client, session):
    _, token = await create_token(session)
    await session.commit()
    await client.post(
        "/api/playlists",
        json={"name": "Audited PL"},
        headers=auth_header(token),
    )
    resp = await client.get("/api/audit", headers=auth_header(token))
    entries = resp.json()["entries"]
    assert any(e["entity_type"] == "playlist" for e in entries)


async def test_audit_log_has_user_info(client, session):
    user, _ = await create_user(session)
    _, token = await create_token(session, user_id=user.id)
    await session.commit()
    await client.post(
        "/api/playlists",
        json={"name": "User PL"},
        headers=auth_header(token),
    )
    resp = await client.get("/api/audit", headers=auth_header(token))
    entries = resp.json()["entries"]
    assert len(entries) > 0
    assert any(e.get("user_id") for e in entries)


async def test_list_audit_actions(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/audit/actions", headers=auth_header(token))
    assert resp.status_code == 200
    assert "actions" in resp.json()


async def test_audit_viewer_forbidden(client, session):
    _, token = await create_token(session, role="viewer")
    await session.commit()
    resp = await client.get("/api/audit", headers=auth_header(token))
    assert resp.status_code == 403
