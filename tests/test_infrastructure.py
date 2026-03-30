"""Phase 0: Test infrastructure verification.

These tests verify the test infrastructure itself works before any API testing.
Feature tree refs: [FT-19.6], [FT-19.7], [FT-19.8], [FT-1.1]-[FT-1.6]
"""

from sqlalchemy import inspect as sa_inspect, select
from app.models import Settings
from app.auth import hash_token
from tests.factories import create_token, create_settings
from tests.helpers import auth_header


async def test_engine_creates_tables(engine):
    """All model tables exist in the in-memory DB."""
    async with engine.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: sa_inspect(sync_conn).get_table_names()
        )
    expected = ["assets", "playlists", "devices", "settings",
                "api_tokens", "users", "schedules"]
    for table in expected:
        assert table in table_names, f"Missing table: {table}"


async def test_session_can_write_and_read(session):
    """Write a Settings record, read it back, verify fields match."""
    settings = await create_settings(session)
    await session.commit()

    result = await session.get(Settings, 1)
    assert result is not None
    assert result.transition_duration == 1.0
    assert result.transition_type == "fade"
    assert result.default_duration == 10
    assert result.shuffle is False


async def test_client_returns_health(client):
    """GET /health returns {"status": "ok"} with status 200."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_factory_creates_token(session):
    """create_token() returns a token whose hash matches DB lookup."""
    token_record, plaintext = await create_token(session)
    await session.commit()

    expected_hash = hash_token(plaintext)
    assert token_record.token_hash == expected_hash

    from sqlalchemy import select
    from app.models import ApiToken
    result = await session.execute(
        select(ApiToken).where(ApiToken.token_hash == expected_hash)
    )
    db_token = result.scalars().first()
    assert db_token is not None
    assert db_token.role == "admin"


async def test_auth_header_works(client, session):
    """Create admin token, make authenticated request, get 200 (not 401)."""
    await create_settings(session)
    token_record, plaintext = await create_token(session)
    await session.commit()

    resp = await client.get("/api/settings", headers=auth_header(plaintext))
    assert resp.status_code == 200
