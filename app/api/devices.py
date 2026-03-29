from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.overrides import evaluate_override_for_device
from app.api.playlists import _item_to_dict, _playlist_hash
from app.api.schedules import evaluate_schedule_for_device
from app.audit import record as audit
from app.auth import (
    generate_pairing_code,
    generate_token,
    hash_pairing_code,
    hash_token,
    require_admin,
    require_device,
    require_viewer,
)
from app.database import get_session
from app.models import ApiToken, Device, DeviceGroupMembership, Playlist, PlaylistItem, Schedule, Settings

PAIRING_CODE_TTL = timedelta(minutes=10)
_config_path = Path("config.yaml")

router = APIRouter()


def _get_server_url() -> str:
    """Read server_url from config. Returns '' if unset."""
    config = yaml.safe_load(_config_path.read_text())
    return config.get("server_url", "").rstrip("/")


@router.get("/devices")
async def list_devices(
    _admin: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Device))
    devices = result.scalars().all()
    return [_device_to_dict(d) for d in devices]


@router.post("/devices/register")
async def register_with_pairing_code(
    body: dict,
    request: Request,
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

    await audit(session, action="register", entity_type="device", entity_id=matched_device.id,
                details={"name": matched_device.name}, request=request)
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
    request: Request,
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

    await audit(session, action="update", entity_type="device", entity_id=device_id,
                details={"name": device.name, "changes": {k: v for k, v in body.items() if k in allowed}},
                token=_admin, request=request)
    await session.commit()
    await session.refresh(device)
    return _device_to_dict(device)


@router.delete("/devices/{device_id}")
async def delete_device(
    device_id: str,
    request: Request,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Delete schedules targeting this device
    result = await session.execute(
        select(Schedule).where(
            Schedule.target_type == "device",
            Schedule.target_id == device_id,
        )
    )
    for schedule in result.scalars().all():
        await session.delete(schedule)

    # Delete group memberships
    result = await session.execute(
        select(DeviceGroupMembership).where(
            DeviceGroupMembership.device_id == device_id
        )
    )
    for membership in result.scalars().all():
        await session.delete(membership)

    # Delete API tokens
    result = await session.execute(
        select(ApiToken).where(ApiToken.device_id == device_id)
    )
    for token in result.scalars().all():
        await session.delete(token)

    await audit(session, action="delete", entity_type="device", entity_id=device_id,
                details={"name": device.name}, token=_admin, request=request)
    await session.delete(device)
    await session.commit()
    return {"ok": True}


@router.post("/devices", status_code=201)
async def create_device(
    body: dict,
    request: Request,
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
    await session.flush()
    await audit(session, action="create", entity_type="device", entity_id=device.id,
                details={"name": name}, token=_admin, request=request)
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

    # --- Emergency override check (absolute priority) ---
    active_override = await evaluate_override_for_device(device_id, session)
    if active_override:
        if active_override.content_type == "message":
            # Message override: return special payload the player renders as text
            override_hash = f"override-{active_override.id}"
            return {
                "hash": override_hash,
                "items": [],
                "settings": await _get_default_settings(session),
                "override": {
                    "id": active_override.id,
                    "type": "message",
                    "message": active_override.content,
                    "name": active_override.name,
                    "expires_at": active_override.expires_at.isoformat() if active_override.expires_at else None,
                },
            }
        elif active_override.content_type == "playlist":
            # Playlist override: force a specific playlist
            effective_playlist_id = active_override.content
            result = await session.execute(
                select(Playlist)
                .where(Playlist.id == effective_playlist_id)
                .options(
                    selectinload(Playlist.items).selectinload(PlaylistItem.asset)
                )
            )
            playlist = result.scalars().first()
            if playlist:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                active_items = [
                    item for item in playlist.items
                    if item.asset and item.asset.is_enabled
                    and (not item.asset.start_date or item.asset.start_date <= now)
                    and (not item.asset.end_date or item.asset.end_date >= now)
                ]
                settings = await session.get(Settings, 1)

                def _resolve_ov(field, default):
                    pl_val = getattr(playlist, field, None)
                    if pl_val is not None:
                        return pl_val
                    return getattr(settings, field, default) if settings else default

                return {
                    "hash": f"override-{active_override.id}-{_playlist_hash(active_items)}",
                    "items": [_item_to_dict(item) for item in active_items],
                    "settings": {
                        "transition_duration": _resolve_ov("transition_duration", 1.0),
                        "transition_type": _resolve_ov("transition_type", "fade"),
                        "default_duration": _resolve_ov("default_duration", 10),
                        "shuffle": _resolve_ov("shuffle", False),
                    },
                    "override": {
                        "id": active_override.id,
                        "type": "playlist",
                        "name": active_override.name,
                        "expires_at": active_override.expires_at.isoformat() if active_override.expires_at else None,
                    },
                }

    # --- Normal flow: evaluate schedules, then device default ---
    effective_playlist_id = await evaluate_schedule_for_device(device_id, session)
    if not effective_playlist_id:
        effective_playlist_id = device.playlist_id

    if not effective_playlist_id:
        return {"hash": "", "items": [], "settings": await _get_default_settings(session)}

    result = await session.execute(
        select(Playlist)
        .where(Playlist.id == effective_playlist_id)
        .options(
            selectinload(Playlist.items).selectinload(PlaylistItem.asset)
        )
    )
    playlist = result.scalars().first()
    if not playlist:
        return {"hash": "", "items": [], "settings": await _get_default_settings(session)}

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


async def _get_default_settings(session: AsyncSession) -> dict:
    """Read global settings from DB, falling back to hardcoded defaults."""
    settings = await session.get(Settings, 1)
    if settings:
        return {
            "transition_duration": settings.transition_duration or 1.0,
            "transition_type": settings.transition_type or "fade",
            "default_duration": settings.default_duration or 10,
            "shuffle": settings.shuffle or False,
        }
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
