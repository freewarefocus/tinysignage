"""CMS API Client tests — Python equivalent of Phase 6 ApiClient.test.js.

Tests that the API requires auth headers and returns 401 without them.

[FT-1.7, FT-1.14]
"""

from tests.factories import create_token
from tests.helpers import auth_header


async def test_api_client_auth_header_grants_access(client, session):
    """Request with valid Authorization header succeeds."""
    _, token = await create_token(session, role="viewer")
    await session.commit()
    resp = await client.get("/api/assets", headers=auth_header(token))
    assert resp.status_code == 200


async def test_api_client_returns_401_without_auth(client):
    """Request without Authorization header returns 401."""
    endpoints = [
        ("GET", "/api/assets"),
        ("GET", "/api/playlists"),
        ("GET", "/api/devices"),
        ("GET", "/api/schedules"),
        ("GET", "/api/groups"),
        ("GET", "/api/layouts"),
        ("GET", "/api/settings"),
    ]
    for method, url in endpoints:
        resp = await client.request(method, url)
        assert resp.status_code == 401, f"{method} {url} should return 401 without auth"
