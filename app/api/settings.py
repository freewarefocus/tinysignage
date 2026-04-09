import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record as audit
from app.auth import require_admin, require_viewer
from app.database import get_session
from app.models import ApiToken, Settings

log = logging.getLogger(__name__)

_CONFIG_PATH = Path("config.yaml")

router = APIRouter()

VALID_TRANSITION_TYPES = {"fade", "slide", "none"}
VALID_OBJECT_FIT_VALUES = {"contain", "cover", "fill", "none"}
VALID_EFFECTS = {"none", "zoom-in", "zoom-out", "pan-left", "pan-right", "pan-up", "pan-down", "random"}


@router.get("/settings")
async def get_settings(
    _admin: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    settings = await session.get(Settings, 1)
    return {
        "transition_duration": settings.transition_duration,
        "transition_type": settings.transition_type,
        "default_duration": settings.default_duration,
        "shuffle": settings.shuffle,
        "object_fit": settings.object_fit,
        "effect": settings.effect,
        "auto_add_to_playlist": settings.auto_add_to_playlist,
        "player_restart_hour": settings.player_restart_hour,
        "player_memory_limit_mb": settings.player_memory_limit_mb if settings.player_memory_limit_mb is not None else 200,
    }


def _validate_settings(data: dict) -> dict:
    """Validate and coerce settings values. Returns cleaned dict."""
    allowed = {"transition_duration", "transition_type", "default_duration", "shuffle", "object_fit", "effect", "auto_add_to_playlist", "player_restart_hour", "player_memory_limit_mb"}
    changes = {}
    for key, value in data.items():
        if key not in allowed:
            continue
        if key == "player_restart_hour":
            if value is not None:
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    raise HTTPException(status_code=400, detail="player_restart_hour must be an integer 0-23 or null")
                if value < 0 or value > 23:
                    raise HTTPException(status_code=400, detail="player_restart_hour must be 0-23")
            changes[key] = value
            continue
        elif key == "player_memory_limit_mb":
            if value is not None:
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    raise HTTPException(status_code=400, detail="player_memory_limit_mb must be a positive integer")
                if value < 50:
                    raise HTTPException(status_code=400, detail="player_memory_limit_mb must be at least 50")
            changes[key] = value
            continue
        elif key == "effect":
            if not isinstance(value, str) or value not in VALID_EFFECTS:
                raise HTTPException(
                    status_code=400,
                    detail=f"effect must be one of: {', '.join(sorted(VALID_EFFECTS))}",
                )
        elif key == "object_fit":
            if not isinstance(value, str) or value not in VALID_OBJECT_FIT_VALUES:
                raise HTTPException(
                    status_code=400,
                    detail=f"object_fit must be one of: {', '.join(sorted(VALID_OBJECT_FIT_VALUES))}",
                )
        elif key == "transition_duration":
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="transition_duration must be a number")
            if value < 0:
                raise HTTPException(status_code=400, detail="transition_duration must be non-negative")
        elif key == "transition_type":
            if not isinstance(value, str) or value not in VALID_TRANSITION_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"transition_type must be one of: {', '.join(sorted(VALID_TRANSITION_TYPES))}",
                )
        elif key == "default_duration":
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="default_duration must be an integer")
            if value < 1:
                raise HTTPException(status_code=400, detail="default_duration must be at least 1")
        elif key == "shuffle":
            if not isinstance(value, bool):
                raise HTTPException(status_code=400, detail="shuffle must be a boolean")
        elif key == "auto_add_to_playlist":
            if not isinstance(value, bool):
                raise HTTPException(status_code=400, detail="auto_add_to_playlist must be a boolean")
        changes[key] = value
    return changes


@router.patch("/settings")
async def update_settings(
    data: dict,
    request: Request,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    settings = await session.get(Settings, 1)
    changes = _validate_settings(data)
    for key, value in changes.items():
        setattr(settings, key, value)
    await audit(session, action="update", entity_type="settings", entity_id="global",
                details={"changes": changes}, token=_admin, request=request)
    await session.commit()
    return {"status": "ok"}


@router.get("/settings/network")
async def get_network_settings(_viewer: ApiToken = Depends(require_viewer)):
    """Read-only network/HTTPS configuration summary.

    Reads directly from config.yaml — network settings live in YAML,
    not the Settings singleton, because changing them requires a
    server restart.
    """
    try:
        config = yaml.safe_load(_CONFIG_PATH.read_text()) or {}
    except Exception as e:
        log.warning("Could not read config.yaml for /settings/network: %s", e)
        config = {}

    server_cfg = config.get("server", {}) or {}
    https_cfg = server_cfg.get("https", {}) or {}

    https_enabled = bool(https_cfg.get("enabled", False))
    cert_path = https_cfg.get("cert_file", "./certs/cert.pem")
    key_path = https_cfg.get("key_file", "./certs/key.pem")

    fingerprint = None
    if https_enabled and Path(cert_path).exists():
        try:
            from app.tls import compute_cert_fingerprint_sha256
            fingerprint = compute_cert_fingerprint_sha256(cert_path)
        except Exception as e:
            log.warning("Could not compute cert fingerprint: %s", e)

    return {
        "https_enabled": https_enabled,
        "host": server_cfg.get("host", "0.0.0.0"),
        "port": int(server_cfg.get("port", 8080)),
        "cert_path": cert_path if https_enabled else None,
        "key_path": key_path if https_enabled else None,
        "cert_fingerprint_sha256": fingerprint,
        "server_url": config.get("server_url", ""),
    }


@router.get("/status")
async def get_status(_admin: ApiToken = Depends(require_viewer)):
    from app.scheduler import scheduler

    return {
        "current_asset_id": scheduler.current_asset_id,
        "current_asset_name": scheduler.current_asset_name,
        "running": scheduler.running,
    }


@router.post("/control/next")
async def control_next(_admin: ApiToken = Depends(require_admin)):
    from app.scheduler import scheduler

    scheduler.skip_to_next()
    return {"status": "ok"}


@router.post("/control/previous")
async def control_previous(_admin: ApiToken = Depends(require_admin)):
    from app.scheduler import scheduler

    scheduler.skip_to_previous()
    return {"status": "ok"}


@router.post("/control/asset/{asset_id}")
async def control_jump(asset_id: str, _admin: ApiToken = Depends(require_admin)):
    from app.scheduler import scheduler

    scheduler.jump_to(asset_id)
    return {"status": "ok"}
