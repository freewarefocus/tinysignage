"""Tests for token lifecycle: generation, expiry, revocation. [FT-1.*]"""

from datetime import datetime, timezone, timedelta

from app.auth import generate_token, hash_token, hash_password, verify_password
from tests.factories import create_token, create_user
from tests.helpers import auth_header


# ── Token Generation & Hashing ─────────────────────────────────────


async def test_generate_token_format():
    """Starts with 'ts_', total length 52 (4 + 48 hex chars)."""
    token = generate_token()
    assert token.startswith("ts_")
    assert len(token) == 51  # "ts_" (3) + 48 hex chars (token_hex(24))


async def test_generate_token_unique():
    """Two calls produce different tokens."""
    t1 = generate_token()
    t2 = generate_token()
    assert t1 != t2


async def test_hash_token_deterministic():
    """Same input → same hash."""
    token = "ts_abc123"
    assert hash_token(token) == hash_token(token)


async def test_hash_token_different_inputs():
    """Different inputs → different hashes."""
    assert hash_token("ts_aaa") != hash_token("ts_bbb")


async def test_hash_token_is_sha256():
    """Hash length is 64 hex chars (SHA-256)."""
    h = hash_token("ts_test")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


# ── Password Hashing ──────────────────────────────────────────────


async def test_hash_password_produces_bcrypt():
    """Output starts with '$2b$'."""
    h = hash_password("mypassword")
    assert h.startswith("$2b$")


async def test_verify_password_correct():
    """verify_password('pass', hash_password('pass')) is True."""
    h = hash_password("pass")
    assert verify_password("pass", h) is True


async def test_verify_password_wrong():
    """verify_password('wrong', hash_password('pass')) is False."""
    h = hash_password("pass")
    assert verify_password("wrong", h) is False


async def test_hash_password_different_salts():
    """Two hashes of same password differ (different salts)."""
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2


# ── Token Expiry ──────────────────────────────────────────────────


async def test_expired_token_rejected(client, session):
    """Token with expires_at in past → 401."""
    expired = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    _, plaintext = await create_token(session, role="admin", expires_at=expired)
    await session.commit()
    resp = await client.get("/api/playlists", headers=auth_header(plaintext))
    assert resp.status_code == 401


async def test_not_yet_expired_token_accepted(client, session):
    """Token with expires_at in future → 200."""
    future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    _, plaintext = await create_token(session, role="viewer", expires_at=future)
    await session.commit()
    resp = await client.get("/api/playlists", headers=auth_header(plaintext))
    assert resp.status_code == 200


async def test_token_without_expiry_accepted(client, session):
    """Token with expires_at=None → 200 (no expiry)."""
    _, plaintext = await create_token(session, role="viewer", expires_at=None)
    await session.commit()
    resp = await client.get("/api/playlists", headers=auth_header(plaintext))
    assert resp.status_code == 200


# ── Token Deactivation ────────────────────────────────────────────


async def test_inactive_token_rejected(client, session):
    """Token with is_active=False → 401."""
    _, plaintext = await create_token(session, role="admin", is_active=False)
    await session.commit()
    resp = await client.get("/api/playlists", headers=auth_header(plaintext))
    assert resp.status_code == 401


async def test_logout_deactivates_token(client, session):
    """POST /api/auth/logout, then use same token → 401."""
    await create_user(session, username="logouttest", password="testpass123")
    await session.commit()
    # Login to get a session token
    resp = await client.post(
        "/api/auth/login",
        json={"username": "logouttest", "password": "testpass123"},
    )
    token = resp.json()["token"]
    # Logout
    resp2 = await client.post("/api/auth/logout", headers=auth_header(token))
    assert resp2.status_code == 200
    # Token should now be rejected
    resp3 = await client.get("/api/playlists", headers=auth_header(token))
    assert resp3.status_code == 401


async def test_revoke_via_api_deactivates(client, session):
    """DELETE /api/tokens/{id}, then use token → 401."""
    _, admin_token = await create_token(session, role="admin")
    await session.commit()
    # Create an admin token via API (API only allows admin|device roles)
    resp = await client.post(
        "/api/tokens",
        json={"name": "Temp", "role": "admin"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201
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


# ── Login Token Creation ──────────────────────────────────────────


async def test_login_creates_token_with_user_role(client, session):
    """Login as editor → token has role='editor'."""
    await create_user(session, username="editor1", role="editor", password="testpass123")
    await session.commit()
    resp = await client.post(
        "/api/auth/login",
        json={"username": "editor1", "password": "testpass123"},
    )
    assert resp.status_code == 200
    token = resp.json()["token"]
    # Editor can access viewer endpoints but not admin endpoints
    resp2 = await client.get("/api/playlists", headers=auth_header(token))
    assert resp2.status_code == 200
    resp3 = await client.get("/api/users", headers=auth_header(token))
    assert resp3.status_code == 403


async def test_login_creates_token_with_user_id(client, session):
    """Login → token has user_id set (verified via /api/auth/me)."""
    user, _ = await create_user(
        session, username="idcheck", role="admin", password="testpass123",
    )
    await session.commit()
    resp = await client.post(
        "/api/auth/login",
        json={"username": "idcheck", "password": "testpass123"},
    )
    token = resp.json()["token"]
    resp2 = await client.get("/api/auth/me", headers=auth_header(token))
    assert resp2.status_code == 200
    assert resp2.json()["id"] == user.id


async def test_login_inactive_user_rejected(client, session):
    """User with is_active=False → 403."""
    await create_user(
        session, username="disabled", password="testpass123", is_active=False,
    )
    await session.commit()
    resp = await client.post(
        "/api/auth/login",
        json={"username": "disabled", "password": "testpass123"},
    )
    assert resp.status_code == 403
