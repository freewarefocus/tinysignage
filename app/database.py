import logging
import uuid
from pathlib import Path

import yaml
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import (
    Asset,
    Base,
    Device,
    Playlist,
    PlaylistItem,
    SchemaVersion,
    Settings,
)

log = logging.getLogger("tinysignage.database")

_config_path = Path("config.yaml")
_config = yaml.safe_load(_config_path.read_text())
_db_path = Path(_config["storage"]["db_path"]).resolve()
_db_path.parent.mkdir(parents=True, exist_ok=True)

CURRENT_SCHEMA_VERSION = 3

engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}",
    poolclass=NullPool,
    echo=False,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    async with async_session() as session:
        yield session


async def _get_schema_version(conn) -> int:
    """Get current schema version, or 0 if no version table exists."""
    tables = await conn.run_sync(
        lambda sync_conn: inspect(sync_conn).get_table_names()
    )
    if "schema_version" not in tables:
        if "assets" in tables:
            return 1  # v1: original schema (assets + settings, no version table)
        return 0  # Fresh database
    result = await conn.execute(text("SELECT version FROM schema_version LIMIT 1"))
    row = result.first()
    return row[0] if row else 0


async def _migrate_v1_to_v2(conn):
    """Migrate from v1 (flat assets) to v2 (devices, playlists, playlist_items)."""
    log.info("Migrating schema v1 → v2")

    # Add new columns to assets table
    columns = await conn.run_sync(
        lambda sync_conn: [
            c["name"] for c in inspect(sync_conn).get_columns("assets")
        ]
    )
    if "thumbnail_path" not in columns:
        await conn.execute(text("ALTER TABLE assets ADD COLUMN thumbnail_path VARCHAR(1024)"))
    if "content_hash" not in columns:
        await conn.execute(text("ALTER TABLE assets ADD COLUMN content_hash VARCHAR(64)"))

    # Create new tables (schema_version, devices, playlists, playlist_items)
    await conn.run_sync(Base.metadata.create_all)

    # Create schema_version record
    await conn.execute(
        text("INSERT INTO schema_version (id, version, updated_at) VALUES (1, :v, datetime('now'))"),
        {"v": CURRENT_SCHEMA_VERSION},
    )


async def _migrate_v2_to_v3(conn):
    """Add health-related columns to devices table."""
    log.info("Migrating schema v2 → v3")

    columns = await conn.run_sync(
        lambda sync_conn: [
            c["name"] for c in inspect(sync_conn).get_columns("devices")
        ]
    )
    for col, col_type in [
        ("last_heartbeat", "DATETIME"),
        ("player_version", "VARCHAR(50)"),
        ("player_timezone", "VARCHAR(50)"),
        ("clock_drift_seconds", "FLOAT"),
    ]:
        if col not in columns:
            await conn.execute(text(f"ALTER TABLE devices ADD COLUMN {col} {col_type}"))

    await conn.execute(
        text("UPDATE schema_version SET version = :v, updated_at = datetime('now')"),
        {"v": CURRENT_SCHEMA_VERSION},
    )


async def _seed_default_playlist_and_device(session):
    """Create default playlist + device, migrate existing assets into playlist items."""
    from sqlalchemy import select

    # Check if a default playlist already exists
    result = await session.execute(
        select(Playlist).where(Playlist.is_default == True)
    )
    if result.scalars().first():
        return  # Already seeded

    # Read device_id from config
    config = yaml.safe_load(_config_path.read_text())
    device_id = config.get("device_id")
    if not device_id:
        device_id = str(uuid.uuid4())
        config["device_id"] = device_id
        _config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
        log.info("Generated device_id: %s", device_id)

    # Create default playlist
    playlist_id = str(uuid.uuid4())
    playlist = Playlist(id=playlist_id, name="Default Playlist", is_default=True)
    session.add(playlist)

    # Create default device pointing to the default playlist
    device = Device(id=device_id, name="Default Player", playlist_id=playlist_id)
    session.add(device)

    # Migrate existing assets into playlist items
    result = await session.execute(
        select(Asset).order_by(Asset.play_order)
    )
    assets = result.scalars().all()
    for asset in assets:
        item = PlaylistItem(
            playlist_id=playlist_id,
            asset_id=asset.id,
            order=asset.play_order,
        )
        session.add(item)

    await session.commit()
    log.info(
        "Seeded default playlist (%d items) and device %s",
        len(assets),
        device_id,
    )


async def init_db():
    async with engine.begin() as conn:
        version = await _get_schema_version(conn)

        if version == 0:
            # Fresh database — create everything
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text("INSERT INTO schema_version (id, version, updated_at) VALUES (1, :v, datetime('now'))"),
                {"v": CURRENT_SCHEMA_VERSION},
            )
            log.info("Created fresh database at schema v%d", CURRENT_SCHEMA_VERSION)
        elif version < CURRENT_SCHEMA_VERSION:
            if version <= 1:
                await _migrate_v1_to_v2(conn)
            if version <= 2:
                await _migrate_v2_to_v3(conn)

    # Seed settings singleton + default playlist/device
    async with async_session() as session:
        existing = await session.get(Settings, 1)
        if not existing:
            session.add(Settings(id=1))
            await session.commit()

        await _seed_default_playlist_and_device(session)
