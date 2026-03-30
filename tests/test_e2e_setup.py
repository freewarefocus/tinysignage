"""E2E tests for first-boot setup wizard.

Tests the complete setup flow: POST /api/setup → admin creation → token → API access.

[FT-19.1, FT-19.3]
"""

from unittest.mock import PropertyMock, patch

from tests.factories import create_device, create_playlist, create_settings
from tests.helpers import auth_header, seed_defaults


async def test_fresh_setup_flow(client, session):
    """POST /api/setup creates admin user and returns a working token."""
    await seed_defaults(session)

    with patch("app.api.setup.is_setup_done", return_value=False), \
         patch("app.api.setup._setup_done_marker") as mock_marker:
        mock_marker.parent.mkdir = lambda **kw: None
        mock_marker.touch = lambda: None

        resp = await client.post("/api/setup", json={
            "admin_username": "admin",
            "admin_password": "SecurePass123!",
            "device_name": "Lobby TV",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["admin_token"].startswith("ts_")
    assert data["device_name"] == "Lobby TV"
    token = data["admin_token"]

    # Token works for API calls
    resp2 = await client.get("/api/settings", headers=auth_header(token))
    assert resp2.status_code == 200


async def test_setup_creates_admin_user(client, session):
    """After setup, GET /api/users shows the created admin."""
    await seed_defaults(session)

    with patch("app.api.setup.is_setup_done", return_value=False), \
         patch("app.api.setup._setup_done_marker") as mock_marker:
        mock_marker.parent.mkdir = lambda **kw: None
        mock_marker.touch = lambda: None

        resp = await client.post("/api/setup", json={
            "admin_username": "myadmin",
            "admin_password": "SecurePass123!",
        })
    token = resp.json()["admin_token"]

    resp2 = await client.get("/api/users", headers=auth_header(token))
    assert resp2.status_code == 200
    users = resp2.json()
    assert any(u["username"] == "myadmin" and u["role"] == "admin" for u in users)


async def test_setup_already_done_rejects(client, session):
    """Second setup call is rejected when marker says already done."""
    await seed_defaults(session)

    with patch("app.api.setup.is_setup_done", return_value=True):
        resp = await client.post("/api/setup", json={
            "admin_username": "admin",
            "admin_password": "SecurePass123!",
        })
    assert resp.status_code == 200
    assert resp.json()["status"] == "already_done"


async def test_root_redirect_before_setup(client):
    """GET / before setup redirects to /setup."""
    with patch("app.api.setup.is_setup_done", return_value=False):
        resp = await client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/setup" in resp.headers["location"]
