"""Tests for API token endpoints. [FT-10.*]"""

from tests.factories import create_token, create_device
from tests.helpers import auth_header


async def test_create_token(client, session):
    _, admin_token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/tokens",
        json={"name": "CI Token", "role": "admin"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "token" in data
    assert data["name"] == "CI Token"


async def test_list_tokens(client, session):
    _, admin_token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/tokens", headers=auth_header(admin_token))
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_revoke_token(client, session):
    _, admin_token = await create_token(session)
    target, _ = await create_token(session, name="to_revoke")
    await session.commit()
    resp = await client.delete(
        f"/api/tokens/{target.id}", headers=auth_header(admin_token),
    )
    assert resp.status_code == 200


async def test_revoked_token_rejected(client, session):
    _, admin_token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/tokens",
        json={"name": "Temp", "role": "admin"},
        headers=auth_header(admin_token),
    )
    new_id = resp.json()["id"]
    new_token = resp.json()["token"]
    # Verify it works
    resp2 = await client.get("/api/tokens", headers=auth_header(new_token))
    assert resp2.status_code == 200
    # Revoke
    await client.delete(f"/api/tokens/{new_id}", headers=auth_header(admin_token))
    # Verify rejected
    resp3 = await client.get("/api/tokens", headers=auth_header(new_token))
    assert resp3.status_code == 401


async def test_create_device_token(client, session):
    _, admin_token = await create_token(session)
    device = await create_device(session)
    await session.commit()
    resp = await client.post(
        "/api/tokens",
        json={"name": "Device Token", "role": "device", "device_id": device.id},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "device"


async def test_create_token_viewer_forbidden(client, session):
    _, viewer_token = await create_token(session, role="viewer")
    await session.commit()
    resp = await client.post(
        "/api/tokens",
        json={"name": "Nope", "role": "admin"},
        headers=auth_header(viewer_token),
    )
    assert resp.status_code == 403
