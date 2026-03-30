"""CMS Layout Editor tests — Python equivalent of Phase 6 LayoutEditor.test.js.

Tests layout zone rendering and zone creation via API.

[FT-6.3, FT-6.6, FT-6.10]
"""

from tests.factories import create_layout, create_token, create_zone
from tests.helpers import auth_header


async def test_layout_editor_renders_zones(client, session):
    """GET /api/layouts/{id} returns zones with correct positioning."""
    _, token = await create_token(session)
    layout = await create_layout(session, name="Multi-Zone")
    await create_zone(
        session, layout.id, name="Main",
        zone_type="main", x_percent=0.0, y_percent=0.0,
        width_percent=75.0, height_percent=100.0, z_index=0,
    )
    await create_zone(
        session, layout.id, name="Ticker",
        zone_type="ticker", x_percent=75.0, y_percent=80.0,
        width_percent=25.0, height_percent=20.0, z_index=1,
    )
    await session.commit()

    resp = await client.get(
        f"/api/layouts/{layout.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["zone_count"] == 2
    zones = data["zones"]
    main_zone = next(z for z in zones if z["name"] == "Main")
    assert main_zone["zone_type"] == "main"
    assert main_zone["width_percent"] == 75.0
    assert main_zone["height_percent"] == 100.0
    ticker = next(z for z in zones if z["name"] == "Ticker")
    assert ticker["zone_type"] == "ticker"
    assert ticker["z_index"] == 1


async def test_layout_editor_adds_zone(client, session):
    """POST /api/layouts/{id}/zones creates a new zone."""
    _, token = await create_token(session, role="editor")
    layout = await create_layout(session, name="New Layout")
    await session.commit()

    resp = await client.post(
        f"/api/layouts/{layout.id}/zones",
        json={
            "name": "Sidebar",
            "zone_type": "sidebar",
            "x_percent": 80.0,
            "y_percent": 0.0,
            "width_percent": 20.0,
            "height_percent": 100.0,
            "z_index": 2,
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Sidebar"
    assert data["zone_type"] == "sidebar"
    assert data["x_percent"] == 80.0
    assert data["width_percent"] == 20.0
