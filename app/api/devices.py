from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.playlists import _item_to_dict, _playlist_hash
from app.database import get_session
from app.models import Device, Playlist, PlaylistItem

router = APIRouter()


@router.get("/devices")
async def list_devices(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Device))
    devices = result.scalars().all()
    return [_device_to_dict(d) for d in devices]


@router.get("/devices/{device_id}")
async def get_device(device_id: str, session: AsyncSession = Depends(get_session)):
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return _device_to_dict(device)


@router.patch("/devices/{device_id}")
async def update_device(
    device_id: str, body: dict, session: AsyncSession = Depends(get_session)
):
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    allowed = {"name", "playlist_id"}
    for key, value in body.items():
        if key in allowed:
            setattr(device, key, value)

    await session.commit()
    await session.refresh(device)
    return _device_to_dict(device)


@router.post("/devices", status_code=201)
async def register_device(body: dict, session: AsyncSession = Depends(get_session)):
    name = body.get("name", "New Player")

    # Assign default playlist if none specified
    playlist_id = body.get("playlist_id")
    if not playlist_id:
        result = await session.execute(
            select(Playlist).where(Playlist.is_default == True)
        )
        default = result.scalars().first()
        if default:
            playlist_id = default.id

    device = Device(name=name, playlist_id=playlist_id)
    session.add(device)
    await session.commit()
    await session.refresh(device)
    return _device_to_dict(device)


@router.get("/devices/{device_id}/playlist")
async def get_device_playlist(
    device_id: str, session: AsyncSession = Depends(get_session)
):
    """Polling endpoint: returns the device's assigned playlist with hash."""
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Update last_seen
    device.last_seen = datetime.now(timezone.utc)
    device.status = "online"
    await session.commit()

    if not device.playlist_id:
        return {"hash": "", "items": [], "settings": _get_default_settings()}

    result = await session.execute(
        select(Playlist)
        .where(Playlist.id == device.playlist_id)
        .options(
            selectinload(Playlist.items).selectinload(PlaylistItem.asset)
        )
    )
    playlist = result.scalars().first()
    if not playlist:
        return {"hash": "", "items": [], "settings": _get_default_settings()}

    # Filter to enabled assets within schedule window
    # SQLite returns naive datetimes; strip tzinfo for comparison
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    active_items = []
    for item in playlist.items:
        asset = item.asset
        if not asset or not asset.is_enabled:
            continue
        if asset.start_date and asset.start_date > now:
            continue
        if asset.end_date and asset.end_date < now:
            continue
        active_items.append(item)

    # Get settings for the response
    from app.models import Settings
    settings = await session.get(Settings, 1)

    return {
        "hash": _playlist_hash(active_items),
        "items": [_item_to_dict(item) for item in active_items],
        "settings": {
            "transition_duration": settings.transition_duration if settings else 1.0,
            "transition_type": settings.transition_type if settings else "fade",
            "default_duration": settings.default_duration if settings else 10,
            "shuffle": settings.shuffle if settings else False,
        },
    }


def _get_default_settings() -> dict:
    return {
        "transition_duration": 1.0,
        "transition_type": "fade",
        "default_duration": 10,
        "shuffle": False,
    }


def _device_to_dict(device: Device) -> dict:
    return {
        "id": device.id,
        "name": device.name,
        "playlist_id": device.playlist_id,
        "last_seen": device.last_seen.isoformat() if device.last_seen else None,
        "ip_address": device.ip_address,
        "status": device.status,
        "created_at": device.created_at.isoformat() if device.created_at else None,
    }
