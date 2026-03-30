"""CMS Router tests — Python equivalent of Phase 6 Router.test.js.

Tests that unauthenticated requests are blocked and authenticated
requests reach their target endpoints.

[FT-1.14, FT-1.9]
"""

from tests.factories import create_settings, create_token
from tests.helpers import auth_header


async def test_router_blocks_unauthenticated_access(client):
    """Protected endpoints return 401 without a token."""
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_router_allows_authenticated_access(client, session):
    """Protected endpoints return 200 with a valid token."""
    _, token = await create_token(session, role="viewer")
    await create_settings(session)
    await session.commit()

    # Viewer can access read endpoints
    for url in ["/api/assets", "/api/playlists", "/api/settings"]:
        resp = await client.get(url, headers=auth_header(token))
        assert resp.status_code == 200, f"{url} should be accessible with viewer token"
