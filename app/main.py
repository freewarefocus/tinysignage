import logging
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.assets import router as assets_router
from app.api.devices import router as devices_router
from app.api.health import router as health_router
from app.api.playlists import router as playlists_router
from app.api.settings import router as settings_router
from app.api.setup import router as setup_router
from app.database import engine, init_db
from app.scheduler import scheduler
from app.watchdog import watchdog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tinysignage")

_config = yaml.safe_load(Path("config.yaml").read_text())
_media_dir = Path(_config["storage"]["media_dir"])
_cms_dir = Path("app/static/cms")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _media_dir.mkdir(parents=True, exist_ok=True)
    (_media_dir / "thumbs").mkdir(parents=True, exist_ok=True)
    await init_db()
    scheduler.start()
    watchdog.start()
    log.info("TinySignage ready — http://localhost:%s", _config["server"]["port"])
    yield
    await watchdog.stop()
    await scheduler.stop()
    await engine.dispose()


app = FastAPI(title="TinySignage", lifespan=lifespan)


@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    response = await call_next(request)
    # Long cache for media files — browser will cache locally for offline resilience
    if request.url.path.startswith("/media/"):
        response.headers["Cache-Control"] = "public, max-age=86400, immutable"
    return response


app.mount("/static", StaticFiles(directory=Path("app/static")), name="static")
app.mount("/media", StaticFiles(directory=_media_dir), name="media")

# Mount CMS static assets (JS/CSS/fonts) — must come before the catch-all route
if _cms_dir.exists():
    app.mount("/cms/assets", StaticFiles(directory=_cms_dir / "assets"), name="cms-assets")

app.include_router(assets_router, prefix="/api")
app.include_router(playlists_router, prefix="/api")
app.include_router(devices_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(setup_router, prefix="/api")
# Also mount setup routes without /api prefix for the wizard UI
app.include_router(setup_router)


@app.get("/player")
async def player_page():
    return FileResponse(Path("app/static/player.html"))


@app.get("/admin")
async def admin_page():
    return RedirectResponse(url="/cms", status_code=302)


@app.get("/cms/{path:path}")
async def cms_catchall(path: str = ""):
    """Catch-all for Vue router history mode — always serve index.html."""
    return FileResponse(_cms_dir / "index.html")


@app.get("/cms")
async def cms_root():
    return FileResponse(_cms_dir / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
