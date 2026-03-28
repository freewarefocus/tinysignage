from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Settings

router = APIRouter()


@router.get("/settings")
async def get_settings(session: AsyncSession = Depends(get_session)):
    settings = await session.get(Settings, 1)
    return {
        "transition_duration": settings.transition_duration,
        "transition_type": settings.transition_type,
        "default_duration": settings.default_duration,
        "shuffle": settings.shuffle,
    }


@router.patch("/settings")
async def update_settings(data: dict, session: AsyncSession = Depends(get_session)):
    settings = await session.get(Settings, 1)
    allowed = {"transition_duration", "transition_type", "default_duration", "shuffle"}
    for key, value in data.items():
        if key in allowed:
            setattr(settings, key, value)
    await session.commit()
    return {"status": "ok"}


@router.get("/status")
async def get_status():
    from app.scheduler import scheduler

    return {
        "current_asset_id": scheduler.current_asset_id,
        "current_asset_name": scheduler.current_asset_name,
        "running": scheduler.running,
    }


@router.post("/control/next")
async def control_next():
    from app.scheduler import scheduler

    scheduler.skip_to_next()
    return {"status": "ok"}


@router.post("/control/previous")
async def control_previous():
    from app.scheduler import scheduler

    scheduler.skip_to_previous()
    return {"status": "ok"}


@router.post("/control/asset/{asset_id}")
async def control_jump(asset_id: str):
    from app.scheduler import scheduler

    scheduler.jump_to(asset_id)
    return {"status": "ok"}
