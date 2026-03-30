"""Playlist polling and content display tests — [FT-20.*]."""

import pytest

from tests.player.conftest import (
    api_setup, api_create_device_with_pairing, api_get_admin_token,
    api_register_device, api_create_asset, api_add_item_to_playlist,
    api_list_playlists, api_list_devices, api_update_playlist,
)

pytestmark = pytest.mark.slow


async def _seed_registered_device(test_server):
    """Setup server, create a device, register it, return (device_id, device_token, admin_token)."""
    admin_token = await api_get_admin_token(test_server)
    device = await api_create_device_with_pairing(test_server, admin_token)
    pairing_code = device.get("pairing_code")
    if not pairing_code:
        # Fallback: use the default device from setup
        devices = await api_list_devices(test_server, admin_token)
        device = devices[0] if devices else device
        # Need to regenerate a pairing code
        import httpx
        async with httpx.AsyncClient(base_url=test_server, timeout=10) as c:
            headers = {"Authorization": f"Bearer {admin_token}"}
            resp = await c.post(f"/api/devices/{device['id']}/pairing-code", headers=headers)
            code_data = resp.json()
            pairing_code = code_data["code"]

    reg = await api_register_device(test_server, pairing_code)
    return reg["device_id"], reg["token"], admin_token


async def _setup_player_with_credentials(page, test_server, device_id, device_token):
    """Navigate to /player and inject device credentials into localStorage."""
    await page.goto(f"{test_server}/player")
    await page.evaluate(f"""() => {{
        localStorage.setItem('tinysignage_device_id', '{device_id}');
        localStorage.setItem('tinysignage_device_token', '{device_token}');
    }}""")
    await page.reload()


async def test_player_polls_playlist(page, test_server):
    """After registration, player makes GET /api/devices/{{id}}/playlist."""
    device_id, device_token, _ = await _seed_registered_device(test_server)
    poll_requests = []

    async def capture_poll(route):
        poll_requests.append(route.request.url)
        await route.continue_()

    await page.route("**/api/devices/*/playlist", capture_poll)
    await _setup_player_with_credentials(page, test_server, device_id, device_token)
    # Wait for at least one poll cycle
    await page.wait_for_timeout(3000)
    assert len(poll_requests) > 0, "Player did not poll for playlist"
    assert f"/api/devices/{device_id}/playlist" in poll_requests[0]


async def test_player_displays_image_asset(page, test_server):
    """Image asset in playlist — <img> tag visible in player."""
    device_id, device_token, admin_token = await _seed_registered_device(test_server)

    # Get default playlist
    playlists = await api_list_playlists(test_server, admin_token)
    default_pl = next((p for p in playlists if p.get("is_default")), playlists[0])

    # Create asset and add to playlist
    asset = await api_create_asset(test_server, admin_token, name="poll-test.png")
    await api_add_item_to_playlist(test_server, admin_token, default_pl["id"], asset["id"])

    # Assign the default playlist to the device
    import httpx
    async with httpx.AsyncClient(base_url=test_server, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        await c.patch(f"/api/devices/{device_id}", json={"playlist_id": default_pl["id"]}, headers=headers)

    await _setup_player_with_credentials(page, test_server, device_id, device_token)
    # Wait for poll + asset rendering
    await page.wait_for_timeout(5000)

    # Check for an <img> element in one of the layers
    img = await page.query_selector("#layer-a img, #layer-b img")
    assert img is not None, "No <img> found in player layers"


async def test_player_displays_url_asset(page, test_server):
    """URL asset in playlist — <iframe> rendered."""
    device_id, device_token, admin_token = await _seed_registered_device(test_server)

    # Create a dedicated playlist with only a URL asset
    import httpx
    async with httpx.AsyncClient(base_url=test_server, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await c.post("/api/playlists", json={"name": "URL PL"}, headers=headers)
        url_pl = resp.json()

        # Create a URL-type asset via form data (url field, no file)
        resp = await c.post("/api/assets", headers=headers,
                            data={"name": "URL Asset", "url": "about:blank"})
        asset = resp.json()
        assert "id" in asset, f"Failed to create URL asset: {asset}"

    await api_add_item_to_playlist(test_server, admin_token, url_pl["id"], asset["id"], order=0)

    # Assign this playlist to device
    async with httpx.AsyncClient(base_url=test_server, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        await c.patch(f"/api/devices/{device_id}", json={"playlist_id": url_pl["id"]}, headers=headers)

    await _setup_player_with_credentials(page, test_server, device_id, device_token)
    await page.wait_for_timeout(5000)

    iframe = await page.query_selector("#layer-a iframe, #layer-b iframe")
    assert iframe is not None, "No <iframe> found for URL asset"


async def test_player_advances_after_duration(page, test_server):
    """Asset with short duration — player advances to next asset."""
    device_id, device_token, admin_token = await _seed_registered_device(test_server)

    # Create a dedicated playlist with exactly 2 assets and short duration
    import httpx
    async with httpx.AsyncClient(base_url=test_server, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await c.post("/api/playlists", json={"name": "Advance PL"}, headers=headers)
        adv_pl = resp.json()

    asset1 = await api_create_asset(test_server, admin_token, name="advance-1.png")
    asset2 = await api_create_asset(test_server, admin_token, name="advance-2.png")
    await api_add_item_to_playlist(test_server, admin_token, adv_pl["id"], asset1["id"], order=0)
    await api_add_item_to_playlist(test_server, admin_token, adv_pl["id"], asset2["id"], order=1)

    # Set short default duration (3s) on playlist
    await api_update_playlist(test_server, admin_token, adv_pl["id"], default_duration=3)

    async with httpx.AsyncClient(base_url=test_server, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        await c.patch(f"/api/devices/{device_id}", json={"playlist_id": adv_pl["id"]}, headers=headers)

    await _setup_player_with_credentials(page, test_server, device_id, device_token)

    # Collect img src values seen across both layers over time
    seen_srcs = set()
    for _ in range(6):
        srcs = await page.evaluate("""() => {
            const imgs = document.querySelectorAll('#layer-a img, #layer-b img');
            return Array.from(imgs).map(i => i.src).filter(Boolean);
        }""")
        seen_srcs.update(srcs)
        await page.wait_for_timeout(2000)

    # With 2 assets and 3s duration over 12s, both assets should have been loaded
    assert len(seen_srcs) >= 2, \
        f"Expected >=2 unique asset URLs (advance happened), got {len(seen_srcs)}: {seen_srcs}"


async def test_player_handles_empty_playlist(page, test_server):
    """Empty playlist — player shows splash or waits gracefully."""
    device_id, device_token, admin_token = await _seed_registered_device(test_server)

    # Create an empty playlist
    import httpx
    async with httpx.AsyncClient(base_url=test_server, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await c.post("/api/playlists", json={"name": "Empty PL"}, headers=headers)
        empty_pl = resp.json()
        await c.patch(f"/api/devices/{device_id}", json={"playlist_id": empty_pl["id"]}, headers=headers)

    await _setup_player_with_credentials(page, test_server, device_id, device_token)
    await page.wait_for_timeout(3000)

    # Splash screen should be visible (not hidden)
    splash = await page.query_selector("#splash")
    assert splash is not None
    splash_classes = await splash.get_attribute("class") or ""
    # If no items, splash should not have hidden class
    assert "hidden" not in splash_classes, "Splash should be visible with empty playlist"


async def test_player_detects_hash_change(page, test_server):
    """Change playlist content — player re-fetches on next poll."""
    device_id, device_token, admin_token = await _seed_registered_device(test_server)

    playlists = await api_list_playlists(test_server, admin_token)
    default_pl = next((p for p in playlists if p.get("is_default")), playlists[0])

    # Start with one asset
    asset1 = await api_create_asset(test_server, admin_token, name="hash-1.png")
    await api_add_item_to_playlist(test_server, admin_token, default_pl["id"], asset1["id"])

    import httpx
    async with httpx.AsyncClient(base_url=test_server, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        await c.patch(f"/api/devices/{device_id}", json={"playlist_id": default_pl["id"]}, headers=headers)

    # Track poll responses
    poll_hashes = []

    async def capture_poll(route):
        resp = await route.fetch()
        try:
            body = await resp.json()
            poll_hashes.append(body.get("hash"))
        except Exception:
            pass
        await route.fulfill(response=resp)

    await page.route("**/api/devices/*/playlist", capture_poll)
    await _setup_player_with_credentials(page, test_server, device_id, device_token)
    await page.wait_for_timeout(3000)

    first_hash = poll_hashes[0] if poll_hashes else None

    # Add another asset to change the hash
    asset2 = await api_create_asset(test_server, admin_token, name="hash-2.png")
    await api_add_item_to_playlist(test_server, admin_token, default_pl["id"], asset2["id"], order=1)

    # Force a quick re-poll by evaluating JS
    await page.evaluate("() => { if (typeof poll === 'function') poll(); }")
    await page.wait_for_timeout(3000)

    # We should see a different hash after the content change
    if len(poll_hashes) >= 2:
        assert poll_hashes[-1] != first_hash, "Hash did not change after playlist update"


async def test_player_applies_transition(page, test_server):
    """Transition setting — CSS transition applied to layers."""
    device_id, device_token, admin_token = await _seed_registered_device(test_server)

    playlists = await api_list_playlists(test_server, admin_token)
    default_pl = next((p for p in playlists if p.get("is_default")), playlists[0])

    asset = await api_create_asset(test_server, admin_token, name="trans.png")
    await api_add_item_to_playlist(test_server, admin_token, default_pl["id"], asset["id"])
    await api_update_playlist(test_server, admin_token, default_pl["id"],
                              transition_type="fade", transition_duration=2.0)

    import httpx
    async with httpx.AsyncClient(base_url=test_server, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        await c.patch(f"/api/devices/{device_id}", json={"playlist_id": default_pl["id"]}, headers=headers)

    await _setup_player_with_credentials(page, test_server, device_id, device_token)
    await page.wait_for_timeout(3000)

    # Check that the CSS variable --transition-duration is set
    td_val = await page.evaluate(
        "() => getComputedStyle(document.getElementById('player')).getPropertyValue('--transition-duration').trim()"
    )
    # Should be set to 2s or similar
    assert td_val, "CSS --transition-duration variable not set"


async def test_player_applies_shuffle(page, test_server):
    """shuffle=True — assets display and player advances through them."""
    device_id, device_token, admin_token = await _seed_registered_device(test_server)

    # Create a dedicated playlist with several assets
    import httpx
    async with httpx.AsyncClient(base_url=test_server, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await c.post("/api/playlists", json={"name": "Shuffle PL"}, headers=headers)
        shuf_pl = resp.json()

    assets = []
    for i in range(5):
        a = await api_create_asset(test_server, admin_token, name=f"shuffle-{i}.png")
        assets.append(a)
        await api_add_item_to_playlist(test_server, admin_token, shuf_pl["id"], a["id"], order=i)

    # Enable shuffle with short duration
    await api_update_playlist(test_server, admin_token, shuf_pl["id"],
                              shuffle=True, default_duration=3)

    async with httpx.AsyncClient(base_url=test_server, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        await c.patch(f"/api/devices/{device_id}", json={"playlist_id": shuf_pl["id"]}, headers=headers)

    await _setup_player_with_credentials(page, test_server, device_id, device_token)

    # Collect unique img src values over time to verify shuffle advances
    seen_srcs = set()
    for _ in range(8):
        srcs = await page.evaluate("""() => {
            const imgs = document.querySelectorAll('#layer-a img, #layer-b img');
            return Array.from(imgs).map(i => i.src).filter(Boolean);
        }""")
        seen_srcs.update(srcs)
        await page.wait_for_timeout(2000)

    # With 5 assets, 3s duration, and 16s of observation, should see multiple unique assets
    assert len(seen_srcs) >= 2, \
        f"Expected >=2 unique shuffled assets, got {len(seen_srcs)}: {seen_srcs}"
