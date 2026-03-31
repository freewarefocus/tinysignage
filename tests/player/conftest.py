"""Playwright fixtures + test server for player browser tests."""

import importlib
import shutil
import threading
import time
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
import uvicorn
from playwright.async_api import async_playwright

TEST_PORT = 18_080
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

# Paths relative to the project root
_DB_PATH = Path("db/signage.db")
_SETUP_MARKER = Path("db/.setup_done")


def _reset_test_state():
    """Delete database and setup marker so the server starts fresh."""
    if _DB_PATH.exists():
        _DB_PATH.unlink()
    if _SETUP_MARKER.exists():
        _SETUP_MARKER.unlink()
    # Force the app module to re-initialize with the clean DB
    import app.database as db_mod
    importlib.reload(db_mod)


@pytest.fixture(scope="session")
def test_server():
    """Start a real TinySignage server on TEST_PORT for player tests."""
    _reset_test_state()

    config = uvicorn.Config(
        "app.main:app",
        host="127.0.0.1",
        port=TEST_PORT,
        log_level="error",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server readiness
    for _ in range(50):
        try:
            r = httpx.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.1)
    else:
        pytest.fail("Test server did not start in time")

    yield BASE_URL
    server.should_exit = True


@pytest_asyncio.fixture
async def browser():
    """Launch headless Chromium for each test module."""
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        yield b
        await b.close()


@pytest_asyncio.fixture
async def page(browser):
    """Fresh browser page per test."""
    pg = await browser.new_page()
    yield pg
    await pg.close()


# ---------------------------------------------------------------------------
# API helpers — seed data via HTTP so the live server DB is populated
# ---------------------------------------------------------------------------

async def api_setup(base_url: str) -> dict:
    """Run first-boot setup if not already done. Returns setup response dict.

    Keys: status, device_name, device_id, admin_token, device_token, server_url
    """
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as c:
        resp = await c.post("/api/setup", json={
            "device_name": "Test Player",
            "server_url": base_url,
            "admin_username": "admin",
            "admin_password": "testpass123",
        })
        return resp.json()


async def api_login(base_url: str, username: str = "admin",
                    password: str = "testpass123") -> str:
    """Login and return the session token."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as c:
        resp = await c.post("/api/auth/login", json={
            "username": username,
            "password": password,
        })
        return resp.json()["token"]


async def api_get_admin_token(base_url: str) -> str:
    """Ensure setup is done and return an admin-level token."""
    data = await api_setup(base_url)
    if data.get("admin_token"):
        return data["admin_token"]
    # Setup already done — login instead
    return await api_login(base_url)


async def api_get_registration_key(base_url: str, admin_token: str) -> str:
    """Get the current registration key from settings. Regenerates if needed."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await c.get("/api/settings", headers=headers)
        settings = resp.json()
        if settings.get("registration_key_created_at"):
            # Key exists but we can't read the plaintext; regenerate
            resp2 = await c.post("/api/settings/registration-key", headers=headers)
            return resp2.json()["registration_key"]
        resp2 = await c.post("/api/settings/registration-key", headers=headers)
        return resp2.json()["registration_key"]


async def api_register_device_with_key(base_url: str, registration_key: str,
                                        name: str = "PW Test Device") -> dict:
    """Register a device with a registration key. Returns {device_id, token, device_name, status}."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as c:
        resp = await c.post("/api/devices/register", json={
            "registration_key": registration_key,
            "name": name,
        })
        return resp.json()


async def api_approve_device(base_url: str, admin_token: str, device_id: str) -> dict:
    """Approve a pending device."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await c.post(f"/api/devices/{device_id}/approve", headers=headers)
        return resp.json()


async def api_create_asset(base_url: str, admin_token: str,
                           name: str = "test-image.png",
                           asset_type: str = "image") -> dict:
    """Create an asset record via file upload. Returns asset dict."""
    import io
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        # Create a minimal valid PNG (1x1 pixel)
        png_bytes = (
            b'\x89PNG\r\n\x1a\n'  # PNG signature
            b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde'
            b'\x00\x00\x00\x0cIDATx'
            b'\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N'
            b'\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        files = {"file": (name, io.BytesIO(png_bytes), "image/png")}
        resp = await c.post("/api/assets", files=files, headers=headers)
        return resp.json()


async def api_add_item_to_playlist(base_url: str, admin_token: str,
                                    playlist_id: str, asset_id: str,
                                    order: int = 0) -> dict:
    """Add an asset to a playlist."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await c.post(
            f"/api/playlists/{playlist_id}/items",
            json={"asset_id": asset_id, "order": order},
            headers=headers,
        )
        return resp.json()


async def api_list_playlists(base_url: str, token: str) -> list:
    """List all playlists."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as c:
        headers = {"Authorization": f"Bearer {token}"}
        resp = await c.get("/api/playlists", headers=headers)
        return resp.json()


async def api_list_devices(base_url: str, token: str) -> list:
    """List all devices."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as c:
        headers = {"Authorization": f"Bearer {token}"}
        resp = await c.get("/api/devices", headers=headers)
        return resp.json()


async def api_create_trigger_flow(base_url: str, admin_token: str,
                                   name: str = "Test Flow") -> dict:
    """Create a trigger flow."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await c.post("/api/trigger-flows", json={"name": name}, headers=headers)
        return resp.json()


async def api_add_trigger_branch(base_url: str, admin_token: str,
                                  flow_id: str, source_playlist_id: str,
                                  target_playlist_id: str,
                                  trigger_type: str = "keyboard",
                                  trigger_config: dict | None = None,
                                  priority: int = 0) -> dict:
    """Add a branch to a trigger flow."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await c.post(
            f"/api/trigger-flows/{flow_id}/branches",
            json={
                "source_playlist_id": source_playlist_id,
                "target_playlist_id": target_playlist_id,
                "trigger_type": trigger_type,
                "trigger_config": trigger_config or {"key": "1"},
                "priority": priority,
            },
            headers=headers,
        )
        return resp.json()


async def api_update_playlist(base_url: str, admin_token: str,
                               playlist_id: str, **fields) -> dict:
    """Patch a playlist."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await c.patch(
            f"/api/playlists/{playlist_id}",
            json=fields,
            headers=headers,
        )
        return resp.json()
