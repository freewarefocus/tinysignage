import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport

from app.models import Base
from app.database import get_session
from app.main import app


@pytest_asyncio.fixture
async def engine():
    """In-memory SQLite engine for tests."""
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    @event.listens_for(eng.sync_engine, "connect")
    def _set_pragma(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    """Async session bound to test engine."""
    test_session = async_sessionmaker(engine, expire_on_commit=False)
    async with test_session() as sess:
        yield sess


@pytest_asyncio.fixture
async def client(engine):
    """httpx AsyncClient with get_session overridden."""
    test_session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session():
        async with test_session() as sess:
            yield sess

    app.dependency_overrides[get_session] = _override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def media_dir(tmp_path, monkeypatch):
    """Patch media directories to use tmp_path for asset tests."""
    import app.api.assets as assets_mod
    thumbs = tmp_path / "thumbs"
    thumbs.mkdir()
    monkeypatch.setattr(assets_mod, "_media_dir", tmp_path)
    monkeypatch.setattr(assets_mod, "_thumbs_dir", thumbs)
    return tmp_path
