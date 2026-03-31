"""Phase 9: Documentation-vs-Code Gap Analysis — Feature verification tests.

Verifies documented feature claims match actual code behavior.
Feature tree refs: 1.x (Auth), 19.x (Infrastructure), 2.x/3.x (Cascade).
"""

import pytest
from sqlalchemy import select, text

from app.auth import (
    ROLE_HIERARCHY, generate_registration_key, generate_token,
    hash_password, hash_token,
)
from app.models import Asset, Device, Playlist, PlaylistItem
from tests.factories import (
    create_asset, create_device, create_playlist,
    create_playlist_item, create_settings,
)


# ---------------------------------------------------------------------------
# 1. Foreign keys enforced (PRAGMA foreign_keys=ON)
# ---------------------------------------------------------------------------

async def test_foreign_keys_enforced(session):
    """Verify PRAGMA foreign_keys=ON is active. [FT-19.8]"""
    result = await session.execute(text("PRAGMA foreign_keys"))
    fk_status = result.scalar()
    assert fk_status == 1, "Foreign keys not enforced — check engine pragma"


# ---------------------------------------------------------------------------
# 2. NullPool in production engine
# ---------------------------------------------------------------------------

def test_nullpool_in_use():
    """Production engine uses NullPool. [CLAUDE.md constraint]"""
    from sqlalchemy.pool import NullPool
    from app.database import engine as prod_engine
    assert isinstance(prod_engine.pool, NullPool), (
        f"Expected NullPool, got {type(prod_engine.pool).__name__}"
    )


# ---------------------------------------------------------------------------
# 3. aiosqlite version pinned to 0.21.x
# ---------------------------------------------------------------------------

def test_aiosqlite_version():
    """aiosqlite version must be 0.21.x (pinned for Windows stability). [CLAUDE.md]"""
    import aiosqlite
    assert aiosqlite.__version__.startswith("0.21"), (
        f"Expected aiosqlite 0.21.x, got {aiosqlite.__version__}"
    )


# ---------------------------------------------------------------------------
# 4. Token prefix is ts_
# ---------------------------------------------------------------------------

def test_token_prefix_is_ts():
    """generate_token() returns string starting with 'ts_'. [FT-1.1]"""
    token = generate_token()
    assert token.startswith("ts_"), f"Token does not start with ts_: {token[:10]}"
    # ts_ + 48 hex chars = 51 total
    assert len(token) == 51, f"Token length should be 51, got {len(token)}"


# ---------------------------------------------------------------------------
# 5. Registration key is XXXX-XXXX-XXXX format
# ---------------------------------------------------------------------------

def test_registration_key_format():
    """generate_registration_key() returns XXXX-XXXX-XXXX uppercase alphanumeric string. [FT-1.5]"""
    key = generate_registration_key()
    parts = key.split("-")
    assert len(parts) == 3, f"Registration key should have 3 parts, got {len(parts)}"
    for part in parts:
        assert len(part) == 4, f"Each part should be 4 chars, got {len(part)}"
        assert part == part.upper(), "Registration key should be uppercase"
        assert part.isalnum(), "Registration key should be alphanumeric"


# ---------------------------------------------------------------------------
# 6. bcrypt used for passwords
# ---------------------------------------------------------------------------

def test_bcrypt_used_for_passwords():
    """hash_password() produces a bcrypt hash (starts with $2b$). [FT-1.3]"""
    hashed = hash_password("testpassword")
    assert hashed.startswith("$2b$"), f"Expected bcrypt hash, got: {hashed[:10]}"


# ---------------------------------------------------------------------------
# 7. Role hierarchy documented correctly
# ---------------------------------------------------------------------------

def test_role_hierarchy_documented_correctly():
    """Role hierarchy: admin=3, editor=2, viewer=1, device=0. [FT-1.9]"""
    assert ROLE_HIERARCHY == {"admin": 3, "editor": 2, "viewer": 1, "device": 0}


# ---------------------------------------------------------------------------
# 8. Cascade delete on asset → playlist items
# ---------------------------------------------------------------------------

async def test_cascade_delete_on_asset(session):
    """Deleting an asset should cascade-delete its playlist items. [FT-2.x]"""
    await create_settings(session)
    playlist = await create_playlist(session, name="Test")
    asset = await create_asset(session, name="img.png")
    item = await create_playlist_item(session, playlist.id, asset.id)
    await session.commit()

    item_id = item.id

    # Delete asset
    await session.delete(asset)
    await session.commit()

    # PlaylistItem should be gone
    result = await session.execute(
        select(PlaylistItem).where(PlaylistItem.id == item_id)
    )
    assert result.scalars().first() is None, "PlaylistItem should be cascade-deleted with asset"


# ---------------------------------------------------------------------------
# 9. Cascade delete on playlist → playlist items
# ---------------------------------------------------------------------------

async def test_cascade_delete_on_playlist(session):
    """Deleting a playlist should cascade-delete its items. [FT-3.x]"""
    await create_settings(session)
    playlist = await create_playlist(session, name="Cascade Test")
    asset = await create_asset(session, name="img2.png", uri="img2.png")
    item = await create_playlist_item(session, playlist.id, asset.id)
    await session.commit()

    item_id = item.id

    # Delete playlist
    await session.delete(playlist)
    await session.commit()

    # PlaylistItem should be gone
    result = await session.execute(
        select(PlaylistItem).where(PlaylistItem.id == item_id)
    )
    assert result.scalars().first() is None, "PlaylistItem should be cascade-deleted with playlist"


# ---------------------------------------------------------------------------
# 10. ON DELETE SET NULL on device.playlist_id
# ---------------------------------------------------------------------------

async def test_ondelete_set_null_on_device_playlist(session):
    """Deleting a playlist should set device.playlist_id to NULL. [FT-4.x]"""
    await create_settings(session)
    playlist = await create_playlist(session, name="Device PL")
    device = await create_device(session, name="Player", playlist_id=playlist.id)
    await session.commit()

    device_id = device.id

    # Delete playlist
    await session.delete(playlist)
    await session.commit()

    # Refresh device — playlist_id should be NULL
    session.expire_all()
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    refreshed = result.scalars().first()
    assert refreshed is not None, "Device should still exist"
    assert refreshed.playlist_id is None, (
        f"Device playlist_id should be NULL after playlist deletion, got {refreshed.playlist_id}"
    )
