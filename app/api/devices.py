from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.playlists import _item_to_dict, _playlist_hash
from app.api.schedules import evaluate_schedule_for_device
from app.auth import (
    generate_pairing_code,
    generate_token,
    hash_pairing_code,
    hash_token,
    require_admin,
    require_device,
)
from app.database import get_session
from app.models import ApiToken, Device, Playlist, PlaylistItem

PAIRING_CODE_TTL = timedelta(minutes=10)
_config_path = Path("config.yaml")

router = APIRouter()


def _get_server_url() -> str:
    """Read server_url from config. Returns '' if unset."""
    config = yaml.safe_load(_config_path.read_text())
    return config.get("server_url", "").rstrip("/")


@router.get("/devices")
async def list_devices(
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Device))
    devices = result.scalars().all()
    return [_device_to_dict(d) for d in devices]


@router.post("/devices/register")
async def register_with_pairing_code(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Public endpoint: exchange a pairing code for a device token."""
    code = body.get("code", "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Pairing code required")

    code_hash = hash_pairing_code(code)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Find device with matching code
    result = await session.execute(
        select(Device).where(Device.registration_code.isnot(None))
    )
    matched_device = None
    for device in result.scalars().all():
        if device.registration_code == code_hash:
            if device.registration_expires and device.registration_expires > now:
                matched_device = device
            break

    if not matched_device:
        raise HTTPException(status_code=400, detail="Invalid or expired pairing code")

    # Generate device token
    plaintext = generate_token()
    token = ApiToken(
        token_hash=hash_token(plaintext),
        name=f"Device: {matched_device.name}",
        role="device",
        device_id=matched_device.id,
        created_by="pairing",
    )
    session.add(token)

    # Clear pairing code (single-use)
    matched_device.registration_code = None
    matched_device.registration_expires = None

    await session.commit()

    return {
        "device_id": matched_device.id,
        "device_name": matched_device.name,
        "token": plaintext,
    }


@router.get("/devices/{device_id}")
async def get_device(
    device_id: str,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return _device_to_dict(device)


@router.patch("/devices/{device_id}")
async def update_device(
    device_id: str,
    body: dict,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
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
async def create_device(
    body: dict,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
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

    # Auto-generate pairing code for the new device
    pairing_code = generate_pairing_code()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    device = Device(
        name=name,
        playlist_id=playlist_id,
        registration_code=hash_pairing_code(pairing_code),
        registration_expires=now + PAIRING_CODE_TTL,
    )
    session.add(device)
    await session.commit()
    await session.refresh(device)

    resp = _device_to_dict(device)
    resp["pairing_code"] = pairing_code
    server_url = _get_server_url()
    resp["pairing_url"] = f"{server_url}/player?pair={pairing_code}"
    return resp


@router.post("/devices/{device_id}/pairing-code")
async def generate_device_pairing_code(
    device_id: str,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Admin-only: generate a new pairing code for a device."""
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    pairing_code = generate_pairing_code()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    device.registration_code = hash_pairing_code(pairing_code)
    device.registration_expires = now + PAIRING_CODE_TTL
    await session.commit()

    server_url = _get_server_url()
    return {
        "code": pairing_code,
        "expires_in": int(PAIRING_CODE_TTL.total_seconds()),
        "pairing_url": f"{server_url}/player?pair={pairing_code}",
    }


@router.get("/devices/{device_id}/playlist")
async def get_device_playlist(
    device_id: str,
    token: ApiToken = Depends(require_device),
    session: AsyncSession = Depends(get_session),
):
    """Polling endpoint: returns the device's assigned playlist with hash."""
    # Ensure the device token matches the requested device
    if token.device_id != device_id:
        raise HTTPException(status_code=403, detail="Token not authorized for this device")
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Update last_seen (strip tzinfo — SQLite stores naive datetimes)
    device.last_seen = datetime.now(timezone.utc).replace(tzinfo=None)
    device.status = "online"
    await session.commit()

    # Evaluate schedules: highest-priority active schedule wins,
    # falls back to device's directly assigned playlist
    effective_playlist_id = await evaluate_schedule_for_device(device_id, session)
    if not effective_playlist_id:
        effective_playlist_id = device.playlist_id

    if not effective_playlist_id:
        return {"hash": "", "items": [], "settings": _get_default_settings()}

    result = await session.execute(
        select(Playlist)
        .where(Playlist.id == effective_playlist_id)
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

    # Get settings: per-playlist overrides take precedence over global
    from app.models import Settings
    settings = await session.get(Settings, 1)

    def _resolve(field: str, default):
        """Per-playlist override wins, then global, then hardcoded default."""
        pl_val = getattr(playlist, field, None)
        if pl_val is not None:
            return pl_val
        return getattr(settings, field, default) if settings else default

    return {
        "hash": _playlist_hash(active_items),
        "items": [_item_to_dict(item) for item in active_items],
        "settings": {
            "transition_duration": _resolve("transition_duration", 1.0),
            "transition_type": _resolve("transition_type", "fade"),
            "default_duration": _resolve("default_duration", 10),
            "shuffle": _resolve("shuffle", False),
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
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    has_pairing_code = bool(
        device.registration_code
        and device.registration_expires
        and device.registration_expires > now
    )
    return {
        "id": device.id,
        "name": device.name,
        "playlist_id": device.playlist_id,
        "last_seen": device.last_seen.isoformat() if device.last_seen else None,
        "ip_address": device.ip_address,
        "status": device.status,
        "has_pairing_code": has_pairing_code,
        "created_at": device.created_at.isoformat() if device.created_at else None,
    }
