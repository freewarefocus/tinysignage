import logging
import uuid
from pathlib import Path

import yaml
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import Asset, Device, Playlist, PlaylistItem, Settings

log = logging.getLogger("tinysignage.database")

_config_path = Path("config.yaml")
_config = yaml.safe_load(_config_path.read_text())
_db_path = Path(_config["storage"]["db_path"]).resolve()
_db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}",
    poolclass=NullPool,
    echo=False,
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key enforcement for every SQLite connection."""
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


async_session = async_sessionmaker(engine, expire_on_commit=False)


def _alembic_cfg() -> AlembicConfig:
    """Build an Alembic Config pointing at our alembic/ directory."""
    cfg = AlembicConfig(str(Path("alembic.ini").resolve()))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{_db_path}")
    return cfg


def _run_migrations() -> None:
    """Run Alembic upgrade head (synchronous — called before async work)."""
    cfg = _alembic_cfg()

    # Check if this is an existing pre-Alembic database that needs stamping
    from sqlalchemy import create_engine, inspect as sa_inspect
    sync_engine = create_engine(f"sqlite:///{_db_path}", poolclass=NullPool)
    with sync_engine.connect() as conn:
        inspector = sa_inspect(conn)
        tables = inspector.get_table_names()
        has_alembic = "alembic_version" in tables
        has_existing_tables = "assets" in tables
    sync_engine.dispose()

    if has_existing_tables and not has_alembic:
        # Existing v3 database — stamp it at the initial revision
        log.info("Existing database detected — stamping Alembic revision")
        command.stamp(cfg, "cba88a050e57")

    # Always run upgrade to apply any pending migrations
    command.upgrade(cfg, "head")
    log.info("Alembic migrations applied")


async def get_session():
    async with async_session() as session:
        yield session


async def _seed_defaults(session):
    """Create default Settings, Playlist, and Device if they don't exist."""
    from sqlalchemy import select

    # Settings singleton
    existing = await session.get(Settings, 1)
    if not existing:
        session.add(Settings(id=1))
        await session.commit()

    # Default playlist + device
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

    playlist_id = str(uuid.uuid4())
    playlist = Playlist(id=playlist_id, name="Default Playlist", is_default=True)
    session.add(playlist)

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
    # Run Alembic migrations (synchronous — SQLite DDL doesn't need async)
    _run_migrations()

    # Seed default data
    async with async_session() as session:
        await _seed_defaults(session)
