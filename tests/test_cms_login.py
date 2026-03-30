"""CMS Login flow tests — Python equivalent of Phase 6 Login.test.js.

Tests the authentication API from the CMS frontend's perspective:
login form submission, error responses, and successful token issuance.

[FT-9.1, FT-9.2, FT-1.14]
"""

from tests.factories import create_user
from tests.helpers import auth_header


async def test_login_form_fields_accepted(client, session):
    """POST /api/auth/login accepts username + password fields."""
    await create_user(session, username="cmsuser", password="securepass1")
    await session.commit()
    resp = await client.post(
        "/api/auth/login",
        json={"username": "cmsuser", "password": "securepass1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert "user" in data
    assert data["user"]["username"] == "cmsuser"


async def test_login_submits_credentials(client, session):
    """Successful login returns a token and user object with role."""
    await create_user(session, username="editor1", password="editorpass1", role="editor")
    await session.commit()
    resp = await client.post(
        "/api/auth/login",
        json={"username": "editor1", "password": "editorpass1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"].startswith("ts_")
    assert data["user"]["role"] == "editor"


async def test_login_shows_error_on_failure(client, session):
    """401 response with error detail on wrong credentials."""
    await create_user(session, username="failuser", password="rightpass1")
    await session.commit()
    resp = await client.post(
        "/api/auth/login",
        json={"username": "failuser", "password": "wrongpass1"},
    )
    assert resp.status_code == 401
    assert "detail" in resp.json()


async def test_login_token_grants_access(client, session):
    """Token from login can be used to access protected endpoints."""
    await create_user(session, username="access1", password="accesspass1")
    await session.commit()
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "access1", "password": "accesspass1"},
    )
    token = login_resp.json()["token"]
    me_resp = await client.get("/api/auth/me", headers=auth_header(token))
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "access1"
