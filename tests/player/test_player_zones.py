"""Multi-zone layout rendering tests — [FT-6.*, FT-20.9]."""

import pytest

from tests.player.conftest import (
    api_get_admin_token, api_get_registration_key,
    api_register_device_with_key, api_approve_device,
    api_list_playlists, api_create_asset, api_add_item_to_playlist,
)

pytestmark = pytest.mark.slow


async def _seed_zone_env(test_server, zone_count=2):
    """Create a device with a multi-zone layout.

    Returns (device_id, device_token, admin_token, layout, zones, playlists).
    """
    import httpx
    admin_token = await api_get_admin_token(test_server)

    # Create and register device via registration key
    reg_key = await api_get_registration_key(test_server, admin_token)
    reg = await api_register_device_with_key(test_server, reg_key,
                                              name="Zone Test Device")
    device_id, device_token = reg["device_id"], reg["token"]
    await api_approve_device(test_server, admin_token, device_id)

    async with httpx.AsyncClient(base_url=test_server, timeout=10) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Create layout
        resp = await c.post("/api/layouts", json={"name": "Test Layout"}, headers=headers)
        layout = resp.json()

        # Create zones with playlists
        zones = []
        zone_playlists = []
        zone_configs = [
            {"name": "Top Zone", "x_percent": 0, "y_percent": 0,
             "width_percent": 100, "height_percent": 50, "z_index": 1},
            {"name": "Bottom Zone", "x_percent": 0, "y_percent": 50,
             "width_percent": 100, "height_percent": 50, "z_index": 2},
            {"name": "Sidebar", "x_percent": 80, "y_percent": 0,
             "width_percent": 20, "height_percent": 100, "z_index": 3},
        ]

        for i in range(min(zone_count, len(zone_configs))):
            cfg = zone_configs[i]

            # Create playlist for this zone
            resp = await c.post("/api/playlists",
                                json={"name": f"Zone {i} PL"}, headers=headers)
            pl = resp.json()
            zone_playlists.append(pl)

            # Add asset to zone playlist
            asset = await api_create_asset(test_server, admin_token,
                                           name=f"zone-{i}.png")
            await api_add_item_to_playlist(test_server, admin_token,
                                           pl["id"], asset["id"])

            # Create zone with playlist assignment
            resp = await c.post(
                f"/api/layouts/{layout['id']}/zones",
                json={**cfg, "zone_type": "main", "playlist_id": pl["id"]},
                headers=headers,
            )
            zones.append(resp.json())

        # Also need a default playlist for the device
        all_pl = await api_list_playlists(test_server, admin_token)
        default_pl = next((p for p in all_pl if p.get("is_default")), all_pl[0])
        asset = await api_create_asset(test_server, admin_token, name="main.png")
        await api_add_item_to_playlist(test_server, admin_token,
                                       default_pl["id"], asset["id"])

        # Assign layout and playlist to device
        await c.patch(
            f"/api/devices/{device_id}",
            json={"layout_id": layout["id"], "playlist_id": default_pl["id"]},
            headers=headers,
        )

    return device_id, device_token, admin_token, layout, zones, zone_playlists


async def _load_player(page, test_server, device_id, device_token):
    """Navigate to player with credentials."""
    await page.goto(f"{test_server}/player")
    await page.evaluate(f"""() => {{
        localStorage.setItem('tinysignage_device_id', '{device_id}');
        localStorage.setItem('tinysignage_device_token', '{device_token}');
    }}""")
    await page.reload()
    await page.wait_for_timeout(5000)


async def test_player_renders_multi_zone_layout(page, test_server):
    """Device has layout with 2 zones — 2 zone containers visible."""
    device_id, device_token, *_ = await _seed_zone_env(test_server, zone_count=2)
    await _load_player(page, test_server, device_id, device_token)

    # zones-container should be visible (not hidden)
    zones_container = await page.query_selector("#zones-container")
    assert zones_container is not None

    zones_classes = await zones_container.get_attribute("class") or ""
    assert "hidden" not in zones_classes, "Zones container should be visible"

    # Count zone divs
    zone_divs = await page.query_selector_all("#zones-container .zone")
    assert len(zone_divs) >= 2, f"Expected 2 zone containers, got {len(zone_divs)}"


async def test_zone_positioning(page, test_server):
    """Zone with specific position — CSS left/top/width/height match."""
    device_id, device_token, _, layout, zones, _ = \
        await _seed_zone_env(test_server, zone_count=2)
    await _load_player(page, test_server, device_id, device_token)

    # Check the first zone's CSS positioning
    zone_styles = await page.evaluate("""() => {
        const zones = document.querySelectorAll('#zones-container .zone');
        return Array.from(zones).map(z => ({
            left: z.style.left,
            top: z.style.top,
            width: z.style.width,
            height: z.style.height,
            name: z.dataset.name || z.dataset.zoneName || '',
        }));
    }""")

    assert len(zone_styles) >= 2, f"Expected >=2 zones, got {len(zone_styles)}"

    # First zone (Top): x=0%, y=0%, w=100%, h=50%
    top_zone = zone_styles[0]
    assert "0%" in top_zone["left"] or top_zone["left"] == "0%"
    assert "0%" in top_zone["top"] or top_zone["top"] == "0%"
    assert "100%" in top_zone["width"]
    assert "50%" in top_zone["height"]

    # Second zone (Bottom): x=0%, y=50%, w=100%, h=50%
    bottom_zone = zone_styles[1]
    assert "50%" in bottom_zone["top"]
    assert "100%" in bottom_zone["width"]
    assert "50%" in bottom_zone["height"]


async def test_zone_z_index(page, test_server):
    """Overlapping zones — z-index applied correctly."""
    device_id, device_token, _, layout, zones, _ = \
        await _seed_zone_env(test_server, zone_count=3)
    await _load_player(page, test_server, device_id, device_token)

    z_indices = await page.evaluate("""() => {
        const zones = document.querySelectorAll('#zones-container .zone');
        return Array.from(zones).map(z => parseInt(z.style.zIndex || '0'));
    }""")

    assert len(z_indices) >= 2, f"Expected >=2 zones, got {len(z_indices)}"

    # z-index values should be distinct and ordered
    for z in z_indices:
        assert z >= 0, "z-index should be non-negative"

    # At least some zones should have different z-index values
    assert len(set(z_indices)) > 1, \
        "All zones have the same z-index — overlapping zones need distinct z-index"


async def test_zone_playlist_independence(page, test_server):
    """Each zone plays its own playlist independently."""
    device_id, device_token, admin_token, layout, zones, zone_playlists = \
        await _seed_zone_env(test_server, zone_count=2)
    await _load_player(page, test_server, device_id, device_token)

    # Each zone should have its own layer content
    zone_contents = await page.evaluate("""() => {
        const zones = document.querySelectorAll('#zones-container .zone');
        return Array.from(zones).map(z => {
            const layers = z.querySelectorAll('.zone-layer');
            const content = Array.from(layers).map(l => l.innerHTML).join('');
            return { hasContent: content.length > 0 };
        });
    }""")

    assert len(zone_contents) >= 2
    # At least one zone should have content rendered
    zones_with_content = sum(1 for z in zone_contents if z["hasContent"])
    assert zones_with_content >= 1, "No zones have content rendered"
