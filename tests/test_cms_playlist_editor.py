"""CMS Playlist Editor tests — Python equivalent of Phase 6 PlaylistEditor.test.js.

Tests playlist item rendering and trigger flow visibility based on mode.

[FT-3.3, FT-3.12, FT-3.14]
"""

from tests.factories import (
    create_asset,
    create_playlist,
    create_playlist_item,
    create_token,
    create_trigger_flow,
)
from tests.helpers import auth_header


async def test_playlist_editor_renders_items_in_order(client, session):
    """GET /api/playlists/{id} returns items sorted by order."""
    _, token = await create_token(session)
    playlist = await create_playlist(session, name="Editor Test")
    a1 = await create_asset(session, name="Slide A", uri="a.png")
    a2 = await create_asset(session, name="Slide B", uri="b.png")
    a3 = await create_asset(session, name="Slide C", uri="c.png")
    await create_playlist_item(session, playlist.id, a1.id, order=0)
    await create_playlist_item(session, playlist.id, a2.id, order=1)
    await create_playlist_item(session, playlist.id, a3.id, order=2)
    await session.commit()

    resp = await client.get(
        f"/api/playlists/{playlist.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 3
    item_names = [i["asset"]["name"] for i in data["items"]]
    assert item_names == ["Slide A", "Slide B", "Slide C"]


async def test_playlist_editor_shows_trigger_flow_in_advanced_mode(client, session):
    """Advanced-mode playlist includes trigger_flow_id in response."""
    _, token = await create_token(session)
    flow = await create_trigger_flow(session, name="Interactive Flow")
    playlist = await create_playlist(
        session, name="Advanced PL", mode="advanced", trigger_flow_id=flow.id,
    )
    await session.commit()

    resp = await client.get(
        f"/api/playlists/{playlist.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "advanced"
    assert data["trigger_flow_id"] == flow.id


async def test_playlist_editor_hides_trigger_flow_in_simple_mode(client, session):
    """Simple-mode playlist has trigger_flow_id=None."""
    _, token = await create_token(session)
    playlist = await create_playlist(session, name="Simple PL", mode="simple")
    await session.commit()

    resp = await client.get(
        f"/api/playlists/{playlist.id}", headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "simple"
    assert data["trigger_flow_id"] is None
