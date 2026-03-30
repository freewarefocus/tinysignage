"""Offline resilience tests — [FT-20.*]."""

import pytest

from tests.player.conftest import (
    api_get_admin_token, api_create_device_with_pairing,
    api_register_device, api_list_playlists,
    api_create_asset, api_add_item_to_playlist,
)

pytestmark = pytest.mark.slow


async def _seed_device_with_content(test_server):
    """Create a registered device with an asset in its playlist.

    Returns (device_id, device_token, admin_token).
    """
    admin_token = await api_get_admin_token(test_server)
    device = await api_create_device_with_pairing(test_server, admin_token,
                                                   name="Offline Test Device")
    pairing_code = device.get("pairing_code")
    if not pairing_code:
        import httpx
        async with httpx.AsyncClient(base_url=test_server, timeout=10) as c:
            headers = {"Authorization": f"Bearer {admin_token}"}
            resp = await c.post(f"/api/devices/{device['id']}/pairing-code", headers=headers)
            pairing_code = resp.json()["code"]

    reg = await api_register_device(test_server, pairing_code)
    device_id, device_token = reg["device_id"], reg["token"]

    # Get default playlist and add an asset
    playlists = await api_list_playlists(test_server, admin_token)
    default_pl = next((p for p in playlists if p.get("is_default")), playlists[0])
    asset = await api_create_asset(test_server, admin_token, name="offline-test.png")
    await api_add_item_to_playlist(test_server, admin_token, default_pl["id"], asset["id"])

    import httpx
    async with httpx.AsyncClient(base_url=test_server, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        await c.patch(f"/api/devices/{device_id}",
                      json={"playlist_id": default_pl["id"]}, headers=headers)

    return device_id, device_token, admin_token


async def _load_player(page, test_server, device_id, device_token):
    """Navigate to player and inject credentials."""
    await page.goto(f"{test_server}/player")
    await page.evaluate(f"""() => {{
        localStorage.setItem('tinysignage_device_id', '{device_id}');
        localStorage.setItem('tinysignage_device_token', '{device_token}');
    }}""")
    await page.reload()


async def test_player_caches_playlist(page, test_server):
    """Load playlist — go offline — player still shows cached content."""
    device_id, device_token, _ = await _seed_device_with_content(test_server)
    await _load_player(page, test_server, device_id, device_token)
    await page.wait_for_timeout(5000)  # Let poll + render complete

    # Verify playlist is cached in localStorage
    cached = await page.evaluate(
        "() => localStorage.getItem('tinysignage_playlist')"
    )
    assert cached is not None, "Playlist not cached in localStorage"

    # Simulate offline by blocking all API requests
    await page.route("**/api/**", lambda route: route.abort())
    await page.wait_for_timeout(2000)

    # Content should still be visible (layers should have content)
    layer_a_html = await page.evaluate("() => document.getElementById('layer-a').innerHTML")
    layer_b_html = await page.evaluate("() => document.getElementById('layer-b').innerHTML")
    assert layer_a_html or layer_b_html, "No content in player layers after going offline"


async def test_player_shows_cached_on_server_error(page, test_server):
    """Server returns 500 — player shows last cached playlist."""
    device_id, device_token, _ = await _seed_device_with_content(test_server)
    await _load_player(page, test_server, device_id, device_token)
    await page.wait_for_timeout(5000)

    # Verify content is loaded
    cached = await page.evaluate(
        "() => localStorage.getItem('tinysignage_playlist')"
    )
    assert cached is not None

    # Intercept poll requests and return 500
    async def return_500(route):
        await route.fulfill(status=500, body="Internal Server Error")

    await page.route("**/api/devices/*/playlist", return_500)

    # Wait for next poll cycle to hit the 500
    await page.wait_for_timeout(3000)

    # Player should still show content from cache
    layer_a_html = await page.evaluate("() => document.getElementById('layer-a').innerHTML")
    layer_b_html = await page.evaluate("() => document.getElementById('layer-b').innerHTML")
    assert layer_a_html or layer_b_html, \
        "Player should show cached content when server returns 500"


async def test_player_recovers_after_reconnect(page, test_server):
    """Go offline — come back — player resumes polling."""
    device_id, device_token, _ = await _seed_device_with_content(test_server)
    await _load_player(page, test_server, device_id, device_token)
    await page.wait_for_timeout(3000)

    # Go offline by blocking API requests
    await page.route("**/api/**", lambda route: route.abort())

    # Wait long enough for at least one poll cycle to fail (30s poll interval + buffer)
    await page.wait_for_timeout(35000)

    # Check status indicator shows offline
    status_classes = await page.evaluate(
        "() => document.getElementById('status-indicator').className"
    )
    assert "status-offline" in status_classes, "Status should show offline after failed poll"

    # Come back online by removing the route interception
    await page.unroute("**/api/**")

    # Track if polling resumes
    poll_happened = []

    async def capture_poll(route):
        poll_happened.append(True)
        await route.continue_()

    await page.route("**/api/devices/*/playlist", capture_poll)

    # Wait for next poll cycle
    await page.wait_for_timeout(35000)

    assert len(poll_happened) > 0, "Player did not resume polling after reconnect"

    # Status should return to online
    status_classes = await page.evaluate(
        "() => document.getElementById('status-indicator').className"
    )
    assert "status-online" in status_classes, "Status should show online after reconnect"


async def test_player_persists_device_credentials(page, test_server):
    """Register device — reload page — credentials still in localStorage."""
    device_id, device_token, _ = await _seed_device_with_content(test_server)
    await _load_player(page, test_server, device_id, device_token)
    await page.wait_for_timeout(2000)

    # Verify credentials are in localStorage
    stored_id = await page.evaluate(
        "() => localStorage.getItem('tinysignage_device_id')"
    )
    stored_token = await page.evaluate(
        "() => localStorage.getItem('tinysignage_device_token')"
    )
    assert stored_id == device_id
    assert stored_token == device_token

    # Reload the page
    await page.reload()
    await page.wait_for_timeout(2000)

    # Credentials should persist
    stored_id_after = await page.evaluate(
        "() => localStorage.getItem('tinysignage_device_id')"
    )
    stored_token_after = await page.evaluate(
        "() => localStorage.getItem('tinysignage_device_token')"
    )
    assert stored_id_after == device_id, "Device ID not persisted across reload"
    assert stored_token_after == device_token, "Device token not persisted across reload"

    # Pairing overlay should NOT be shown (credentials exist)
    overlay_classes = await page.evaluate(
        "() => document.getElementById('pairing-overlay').className"
    )
    assert "hidden" in overlay_classes, \
        "Pairing overlay should be hidden when credentials exist"
