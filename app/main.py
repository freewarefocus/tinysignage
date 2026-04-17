import html
import ipaddress
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.audit import router as audit_router
from app.api.brightsign import router as brightsign_router
from app.api.assets import router as assets_router
from app.api.backup import router as backup_router
from app.api.devices import router as devices_router
from app.api.groups import router as groups_router
from app.api.health import router as health_router
from app.api.layouts import router as layouts_router
from app.api.logs import router as logs_router
from app.api.mrss import router as mrss_router
from app.api.overrides import router as overrides_router
from app.api.playlists import router as playlists_router
from app.api.schedules import router as schedules_router
from app.api.settings import router as settings_router
from app.api.setup import router as setup_router
from app.api.storage import router as storage_router
from app.api.tags import router as tags_router
from app.api.tokens import router as tokens_router
from app.api.trigger_flows import router as trigger_flows_router
from app.api.users import router as users_router
from app.api.widgets import router as widgets_router
from app.database import engine, init_db
from app.error_handlers import register_error_handlers
from app.logging_config import setup_logging
from app.scheduler import scheduler
from app.watchdog import watchdog

def _is_loopback(host: str) -> bool:
    """Check if a hostname or IP refers to the loopback interface."""
    if host in ("localhost", "::1"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


_config_path = Path("config.yaml")
_config = yaml.safe_load(_config_path.read_text())

_log_cfg = _config.get("logging", {})
setup_logging(
    log_dir=_log_cfg.get("log_dir", "logs"),
    level=_log_cfg.get("level", "INFO"),
)
log = logging.getLogger("tinysignage")

_media_dir = Path(_config["storage"]["media_dir"])
_cms_dir = Path("app/static/cms")
_player_html = Path("app/static/player.html")


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
register_error_handlers(app)

# CORS for split deployment (player on a different machine than CMS)
_cors_origins = _config.get("cors", {}).get("allowed_origins", ["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

app.include_router(audit_router, prefix="/api")
app.include_router(assets_router, prefix="/api")
app.include_router(brightsign_router, prefix="/api")
app.include_router(mrss_router, prefix="/api")
app.include_router(backup_router, prefix="/api")
app.include_router(playlists_router, prefix="/api")
app.include_router(devices_router, prefix="/api")
app.include_router(groups_router, prefix="/api")
app.include_router(schedules_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(layouts_router, prefix="/api")
app.include_router(logs_router, prefix="/api")
app.include_router(overrides_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(storage_router, prefix="/api")
app.include_router(tags_router, prefix="/api")
app.include_router(tokens_router, prefix="/api")
app.include_router(trigger_flows_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(widgets_router, prefix="/api")
app.include_router(setup_router, prefix="/api")
# Also mount setup routes without /api prefix for the wizard UI
app.include_router(setup_router)


@app.get("/")
async def root():
    from app.api.setup import is_setup_done
    if not is_setup_done():
        return RedirectResponse(url="/setup", status_code=302)
    return RedirectResponse(url="/cms", status_code=302)


@app.get("/player")
async def player_page(request: Request):
    config = yaml.safe_load(_config_path.read_text())
    # Use the configured server_url, but fall back to the request origin so
    # the player always talks to whatever host served this page (important
    # when launcher.py opens http://localhost:8080/player)
    server_url = config.get("server_url", "") or str(request.base_url).rstrip("/")
    # If configured URL is loopback but client is remote, use request origin
    # so the player's <meta name="server-url"> points back to this CMS, not
    # to 127.0.0.1 on the remote device.
    if server_url:
        from urllib.parse import urlparse
        parsed_host = urlparse(server_url).hostname or ""
        client_ip = request.client.host if request.client else "127.0.0.1"
        if _is_loopback(parsed_host) and not _is_loopback(client_ip):
            server_url = str(request.base_url).rstrip("/")
    # Read PLAYER_VERSION from player.js for cache-busting
    player_version = "0"
    try:
        for line in _player_html.parent.joinpath("player.js").read_text(encoding="utf-8").splitlines():
            if "PLAYER_VERSION" in line and "=" in line:
                player_version = line.split("'")[1] if "'" in line else line.split('"')[1]
                break
    except Exception:
        pass
    html_content = _player_html.read_text(encoding="utf-8")
    # Inject server-url meta tag after <head> so player.js can read it
    meta_tag = f'<meta name="server-url" content="{html.escape(server_url, quote=True)}">'
    html_content = html_content.replace("<head>", f"<head>\n    {meta_tag}", 1)
    # Cache-bust CSS and JS with version query parameter
    html_content = html_content.replace("/static/player.css", f"/static/player.css?v={player_version}")
    html_content = html_content.replace("/static/player.js", f"/static/player.js?v={player_version}")
    return HTMLResponse(html_content)


@app.get("/admin")
async def admin_page():
    return RedirectResponse(url="/cms", status_code=302)


@app.get("/cms/{path:path}")
async def cms_catchall(path: str = ""):
    """Catch-all for Vue router history mode — always serve index.html."""
    from app.api.setup import is_setup_done
    if not is_setup_done():
        return RedirectResponse(url="/setup", status_code=302)
    return FileResponse(_cms_dir / "index.html")


@app.get("/cms")
async def cms_root():
    from app.api.setup import is_setup_done
    if not is_setup_done():
        return RedirectResponse(url="/setup", status_code=302)
    return FileResponse(_cms_dir / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
