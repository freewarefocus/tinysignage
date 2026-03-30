"""Player initialization and setup tests — [FT-19.4]."""

import pytest

from tests.player.conftest import api_setup

pytestmark = pytest.mark.slow


async def test_player_page_loads(page, test_server):
    """Navigate to /player — page title and #player container present."""
    await page.goto(f"{test_server}/player")
    assert await page.title() == "TinySignage Player"
    container = await page.query_selector("#player")
    assert container is not None


async def test_player_has_server_url_meta(page, test_server):
    """`<meta name="server-url">` tag injected by server."""
    await api_setup(test_server)
    await page.goto(f"{test_server}/player")
    meta = await page.query_selector('meta[name="server-url"]')
    assert meta is not None
    content = await meta.get_attribute("content")
    # content may be empty (same-origin) or a URL — just verify the attribute exists
    assert content is not None


async def test_player_js_loads(page, test_server):
    """player.js loads without console errors."""
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    await page.goto(f"{test_server}/player")
    await page.wait_for_timeout(1000)
    # Filter out expected errors (e.g. fetch failures when no device token)
    unexpected = [e for e in errors if "Failed to fetch" not in e and "net::" not in e]
    assert not unexpected, f"Console errors: {unexpected}"


async def test_player_shows_pairing_ui_when_unregistered(page, test_server):
    """No device token in localStorage — pairing overlay shown."""
    await page.goto(f"{test_server}/player")
    # Wait for init() to run and decide to show pairing
    await page.wait_for_timeout(1000)
    overlay = await page.query_selector("#pairing-overlay")
    assert overlay is not None
    # Pairing overlay should NOT have the hidden class
    classes = await overlay.get_attribute("class") or ""
    assert "hidden" not in classes, "Pairing overlay should be visible when unregistered"


async def test_player_version_cachebust(page, test_server):
    """player.js URL has ?v= cache-busting parameter."""
    await page.goto(f"{test_server}/player")
    content = await page.content()
    assert "player.js?v=" in content
    assert "player.css?v=" in content


async def test_player_css_loads(page, test_server):
    """player.css loaded without 404."""
    css_responses = []

    async def capture_css(response):
        if "player.css" in response.url:
            css_responses.append(response)

    page.on("response", capture_css)
    await page.goto(f"{test_server}/player")
    await page.wait_for_timeout(500)
    assert len(css_responses) > 0, "player.css request not captured"
    assert css_responses[0].status == 200, f"player.css returned {css_responses[0].status}"
