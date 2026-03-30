"""Tests for user CRUD and auth endpoints. [FT-9.*]"""

from tests.factories import create_token, create_user
from tests.helpers import auth_header


async def test_list_users(client, session):
    user, _ = await create_user(session)
    _, token = await create_token(session, user_id=user.id)
    await session.commit()
    resp = await client.get("/api/users", headers=auth_header(token))
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_create_user(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/users",
        json={"username": "newuser", "password": "password123", "role": "viewer"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "newuser"


async def test_create_user_duplicate_username(client, session):
    _, token = await create_token(session)
    await create_user(session, username="alice")
    await session.commit()
    resp = await client.post(
        "/api/users",
        json={"username": "alice", "password": "password123"},
        headers=auth_header(token),
    )
    assert resp.status_code in (400, 409)


async def test_get_current_user(client, session):
    user, _ = await create_user(session)
    _, token = await create_token(session, user_id=user.id)
    await session.commit()
    resp = await client.get("/api/auth/me", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == user.username
    assert data["role"] == user.role


async def test_update_user_role(client, session):
    _, token = await create_token(session)
    user, _ = await create_user(session, username="bob", role="viewer")
    await session.commit()
    resp = await client.put(
        f"/api/users/{user.id}",
        json={"role": "editor"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "editor"


async def test_delete_user(client, session):
    admin, _ = await create_user(session, username="admin1")
    _, token = await create_token(session, user_id=admin.id)
    target, _ = await create_user(session, username="target", role="viewer")
    await session.commit()
    resp = await client.delete(
        f"/api/users/{target.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_login_success(client, session):
    await create_user(session, username="loginuser", password="testpass123")
    await session.commit()
    resp = await client.post(
        "/api/auth/login",
        json={"username": "loginuser", "password": "testpass123"},
    )
    assert resp.status_code == 200
    assert "token" in resp.json()


async def test_login_wrong_password(client, session):
    await create_user(session, username="wrongpw")
    await session.commit()
    resp = await client.post(
        "/api/auth/login",
        json={"username": "wrongpw", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


async def test_login_nonexistent_user(client):
    resp = await client.post(
        "/api/auth/login",
        json={"username": "ghost", "password": "password123"},
    )
    assert resp.status_code == 401


async def test_logout(client, session):
    await create_user(session, username="logoutuser", password="testpass123")
    await session.commit()
    resp = await client.post(
        "/api/auth/login",
        json={"username": "logoutuser", "password": "testpass123"},
    )
    token = resp.json()["token"]
    resp2 = await client.post("/api/auth/logout", headers=auth_header(token))
    assert resp2.status_code == 200
    resp3 = await client.get("/api/auth/me", headers=auth_header(token))
    assert resp3.status_code == 401


async def test_get_preferences(client, session):
    user, _ = await create_user(session)
    _, token = await create_token(session, user_id=user.id)
    await session.commit()
    resp = await client.get(
        "/api/users/me/preferences", headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert "theme_preference" in resp.json()


async def test_update_preferences(client, session):
    user, _ = await create_user(session)
    _, token = await create_token(session, user_id=user.id)
    await session.commit()
    resp = await client.patch(
        "/api/users/me/preferences",
        json={"theme_preference": "light"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["theme_preference"] == "light"
