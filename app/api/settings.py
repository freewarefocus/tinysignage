from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record as audit
from app.auth import require_admin, require_viewer
from app.database import get_session
from app.models import ApiToken, Settings

router = APIRouter()

VALID_TRANSITION_TYPES = {"fade", "slide", "none"}
VALID_OBJECT_FIT_VALUES = {"contain", "cover", "fill", "none"}


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
        "auto_add_to_playlist": settings.auto_add_to_playlist,
    }


def _validate_settings(data: dict) -> dict:
    """Validate and coerce settings values. Returns cleaned dict."""
    allowed = {"transition_duration", "transition_type", "default_duration", "shuffle", "object_fit", "auto_add_to_playlist"}
    changes = {}
    for key, value in data.items():
        if key not in allowed:
            continue
        if key == "object_fit":
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
