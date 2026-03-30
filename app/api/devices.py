import hashlib
import json
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
    hash_registration_key,
    hash_token,
    require_admin,
    require_device,
    require_viewer,
)
from app.database import get_session
from app.models import ApiToken, Asset, AssetTag, Device, DeviceGroupMembership, Layout, LayoutZone, Override, Playlist, PlaylistItem, Schedule, Settings, TriggerBranch, TriggerFlow

PAIRING_CODE_TTL = timedelta(minutes=10)
_config_path = Path("config.yaml")

router = APIRouter()


def _get_server_url(request: Request = None) -> str:
    """Read server_url from config. Falls back to request origin if unset."""
    config = yaml.safe_load(_config_path.read_text())
    url = config.get("server_url", "").rstrip("/")
    if not url and request:
        url = str(request.base_url).rstrip("/")
    return url


@router.get("/devices")
async def list_devices(
    _admin: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Device))
    devices = result.scalars().all()
    return [_device_to_dict(d) for d in devices]


@router.post("/devices/register")
async def register_device(
    body: dict,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Public endpoint: register via pairing code or registration key."""
    # Dispatch on body shape
    if "registration_key" in body:
        return await _register_with_key(body, request, session)
    return await _register_with_pairing_code(body, request, session)


async def _register_with_pairing_code(body: dict, request: Request, session: AsyncSession):
    """Exchange a pairing code for a device token (pre-approved path)."""
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
                details={"name": matched_device.name, "method": "pairing_code"}, request=request)
    await session.commit()

    return {
        "device_id": matched_device.id,
        "device_name": matched_device.name,
        "token": plaintext,
    }


async def _register_with_key(body: dict, request: Request, session: AsyncSession):
    """Register a new device using the shared registration key (pending approval)."""
    key = body.get("registration_key", "").strip()
    name = body.get("name", "New Display").strip() or "New Display"

    if not key:
        raise HTTPException(status_code=400, detail="Registration key required")

    # Validate key against stored hash
    settings = await session.get(Settings, 1)
    if not settings or not settings.registration_key_hash:
        raise HTTPException(status_code=400, detail="Registration key not configured on this server")

    if hash_registration_key(key) != settings.registration_key_hash:
        raise HTTPException(status_code=400, detail="Invalid registration key")

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Assign default playlist
    playlist_result = await session.execute(
        select(Playlist).where(Playlist.is_default == True)
    )
    default_playlist = playlist_result.scalars().first()

    # Create device in pending status
    device = Device(
        name=name,
        status="pending",
        playlist_id=default_playlist.id if default_playlist else None,
        ip_address=request.client.host if request.client else None,
    )
    session.add(device)
    await session.flush()

    # Generate device token
    plaintext = generate_token()
    token = ApiToken(
        token_hash=hash_token(plaintext),
        name=f"Device: {name}",
        role="device",
        device_id=device.id,
        created_by="registration_key",
    )
    session.add(token)

    await audit(session, action="register", entity_type="device", entity_id=device.id,
                details={"name": name, "method": "registration_key"}, request=request)
    await session.commit()

    return {
        "device_id": device.id,
        "device_name": name,
        "token": plaintext,
        "status": "pending",
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

    allowed = {"name", "playlist_id", "layout_id"}
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

    # Delete overrides targeting this device
    result = await session.execute(
        select(Override).where(
            Override.target_type == "device",
            Override.target_id == device_id,
        )
    )
    for override in result.scalars().all():
        await session.delete(override)

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
    server_url = _get_server_url(request)
    resp["pairing_url"] = f"{server_url}/player?pair={pairing_code}"
    return resp


@router.post("/devices/{device_id}/pairing-code")
async def generate_device_pairing_code(
    device_id: str,
    request: Request,
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

    server_url = _get_server_url(request)
    return {
        "code": pairing_code,
        "expires_in": int(PAIRING_CODE_TTL.total_seconds()),
        "pairing_url": f"{server_url}/player?pair={pairing_code}",
    }


@router.post("/devices/{device_id}/approve")
async def approve_device(
    device_id: str,
    request: Request,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Admin-only: approve a pending device."""
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.status != "pending":
        raise HTTPException(status_code=400, detail="Device is not pending approval")

    device.status = "offline"  # Will become online on next heartbeat
    await audit(session, action="approve", entity_type="device", entity_id=device_id,
                details={"name": device.name}, token=_admin, request=request)
    await session.commit()
    return {"ok": True, "status": "offline"}


@router.post("/devices/{device_id}/reject")
async def reject_device(
    device_id: str,
    request: Request,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Admin-only: reject a pending device (deletes it)."""
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.status != "pending":
        raise HTTPException(status_code=400, detail="Device is not pending approval")

    # Delete API tokens for this device
    result = await session.execute(
        select(ApiToken).where(ApiToken.device_id == device_id)
    )
    for token in result.scalars().all():
        await session.delete(token)

    await audit(session, action="reject", entity_type="device", entity_id=device_id,
                details={"name": device.name}, token=_admin, request=request)
    await session.delete(device)
    await session.commit()
    return {"ok": True}


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

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Pending devices get no content — just update last_seen
    if device.status == "pending":
        device.last_seen = now
        await session.commit()
        return {"status": "pending"}

    # Update last_seen (strip tzinfo — SQLite stores naive datetimes)
    device.last_seen = now
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
                    selectinload(Playlist.items).selectinload(PlaylistItem.asset).selectinload(Asset.asset_tags).selectinload(AssetTag.tag)
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
    effective_playlist_id, transition_playlist_id = await evaluate_schedule_for_device(device_id, session)
    if not effective_playlist_id:
        effective_playlist_id = device.playlist_id
        transition_playlist_id = None

    # --- Multi-zone layout support ---
    zones_data = None
    if device.layout_id:
        zones_data = await _build_zones_payload(device.layout_id, session)

    if not effective_playlist_id and not zones_data:
        return {"hash": "", "items": [], "settings": await _get_default_settings(session)}

    if not effective_playlist_id:
        # Layout assigned but no default playlist — return empty main with zones
        return {
            "hash": _zones_hash(zones_data),
            "items": [],
            "settings": await _get_default_settings(session),
            "zones": zones_data,
        }

    result = await session.execute(
        select(Playlist)
        .where(Playlist.id == effective_playlist_id)
        .options(
            selectinload(Playlist.items).selectinload(PlaylistItem.asset).selectinload(Asset.asset_tags).selectinload(AssetTag.tag)
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
    settings = await session.get(Settings, 1)

    def _resolve(field: str, default):
        """Per-playlist override wins, then global, then hardcoded default."""
        pl_val = getattr(playlist, field, None)
        if pl_val is not None:
            return pl_val
        return getattr(settings, field, default) if settings else default

    resp = {
        "hash": _playlist_hash(active_items),
        "items": [_item_to_dict(item) for item in active_items],
        "settings": {
            "transition_duration": _resolve("transition_duration", 1.0),
            "transition_type": _resolve("transition_type", "fade"),
            "default_duration": _resolve("default_duration", 10),
            "shuffle": _resolve("shuffle", False),
        },
    }

    # Include transition playlist for schedule-change bumpers
    if transition_playlist_id:
        tp_result = await session.execute(
            select(Playlist)
            .where(Playlist.id == transition_playlist_id)
            .options(selectinload(Playlist.items).selectinload(PlaylistItem.asset).selectinload(Asset.asset_tags).selectinload(AssetTag.tag))
        )
        tp = tp_result.scalars().first()
        if tp:
            now_tp = datetime.now(timezone.utc).replace(tzinfo=None)
            tp_items = [
                item for item in tp.items
                if item.asset and item.asset.is_enabled
                and (not item.asset.start_date or item.asset.start_date <= now_tp)
                and (not item.asset.end_date or item.asset.end_date >= now_tp)
            ]
            resp["transition_playlist"] = {
                "id": tp.id,
                "name": tp.name,
                "items": [_item_to_dict(item) for item in tp_items],
            }
            resp["hash"] += f"-tp{tp.id[:8]}"

    # Include trigger_flow when playlist has one (not during overrides)
    if playlist.trigger_flow_id:
        tf_payload = await _build_trigger_flow_payload(
            playlist.trigger_flow_id, playlist.id, session, settings
        )
        if tf_payload:
            resp["trigger_flow"] = tf_payload
            resp["hash"] += f"-tf{_trigger_flow_hash(tf_payload)}"

    if zones_data:
        resp["zones"] = zones_data
        base_hash = _playlist_hash(active_items) + "-" + _zones_hash(zones_data)
        if "transition_playlist" in resp:
            base_hash += f"-tp{resp['transition_playlist']['id'][:8]}"
        if "trigger_flow" in resp:
            base_hash += f"-tf{_trigger_flow_hash(resp['trigger_flow'])}"
        resp["hash"] = base_hash

    return resp


async def _build_trigger_flow_payload(
    flow_id: str, source_playlist_id: str, session: AsyncSession, global_settings: Settings | None
) -> dict | None:
    """Load a TriggerFlow with branches and pre-resolved target playlists."""
    result = await session.execute(
        select(TriggerFlow)
        .where(TriggerFlow.id == flow_id)
        .options(selectinload(TriggerFlow.branches))
    )
    flow = result.scalars().first()
    if not flow or not flow.branches:
        return None

    # Batch-load all target playlists (avoids N+1)
    target_ids = list({b.target_playlist_id for b in flow.branches})
    pl_result = await session.execute(
        select(Playlist)
        .where(Playlist.id.in_(target_ids))
        .options(selectinload(Playlist.items).selectinload(PlaylistItem.asset).selectinload(Asset.asset_tags).selectinload(AssetTag.tag))
    )
    targets_by_id = {pl.id: pl for pl in pl_result.scalars().all()}

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    branches_out = []
    for branch in flow.branches:
        target_pl = targets_by_id.get(branch.target_playlist_id)
        if not target_pl:
            continue

        # Filter target items same as main playlist
        active_items = [
            item for item in target_pl.items
            if item.asset and item.asset.is_enabled
            and (not item.asset.start_date or item.asset.start_date <= now)
            and (not item.asset.end_date or item.asset.end_date >= now)
        ]

        # Resolve per-playlist > global settings
        def _tr(field, default, _pl=target_pl):
            val = getattr(_pl, field, None)
            if val is not None:
                return val
            return getattr(global_settings, field, default) if global_settings else default

        try:
            config = json.loads(branch.trigger_config) if branch.trigger_config else {}
        except (json.JSONDecodeError, TypeError):
            config = {}

        # Strip webhook token from config sent to players — they don't need it
        player_config = {k: v for k, v in config.items() if k != "token"}

        branch_data = {
            "id": branch.id,
            "source_playlist_id": branch.source_playlist_id,
            "target_playlist_id": branch.target_playlist_id,
            "trigger_type": branch.trigger_type,
            "trigger_config": player_config,
            "priority": branch.priority,
        }
        if branch.trigger_type == "webhook" and branch.last_webhook_fire:
            branch_data["last_webhook_fire"] = branch.last_webhook_fire.isoformat()

        branch_data["target_playlist"] = {
            "id": target_pl.id,
            "name": target_pl.name,
            "items": [_item_to_dict(item) for item in active_items],
            "settings": {
                "transition_duration": _tr("transition_duration", 1.0),
                "transition_type": _tr("transition_type", "fade"),
                "default_duration": _tr("default_duration", 10),
                "shuffle": _tr("shuffle", False),
            },
        }

        branches_out.append(branch_data)

    if not branches_out:
        return None

    return {
        "id": flow.id,
        "source_playlist_id": source_playlist_id,
        "branches": branches_out,
    }


async def _build_zones_payload(layout_id: str, session: AsyncSession) -> list[dict]:
    """Build zone payload with each zone's playlist items resolved."""
    result = await session.execute(
        select(LayoutZone).where(LayoutZone.layout_id == layout_id)
    )
    zones = result.scalars().all()
    if not zones:
        return []

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    global_settings = await session.get(Settings, 1)

    # Batch-load all zone playlists in a single query (avoids N+1)
    playlist_ids = [z.playlist_id for z in zones if z.playlist_id]
    playlists_by_id = {}
    if playlist_ids:
        pl_result = await session.execute(
            select(Playlist)
            .where(Playlist.id.in_(playlist_ids))
            .options(selectinload(Playlist.items).selectinload(PlaylistItem.asset).selectinload(Asset.asset_tags).selectinload(AssetTag.tag))
        )
        for pl in pl_result.scalars().all():
            playlists_by_id[pl.id] = pl

    zones_out = []
    for zone in zones:
        zone_dict = {
            "id": zone.id,
            "name": zone.name,
            "zone_type": zone.zone_type,
            "x_percent": zone.x_percent,
            "y_percent": zone.y_percent,
            "width_percent": zone.width_percent,
            "height_percent": zone.height_percent,
            "z_index": zone.z_index,
            "playlist_id": zone.playlist_id,
            "items": [],
            "settings": {},
        }

        pl = playlists_by_id.get(zone.playlist_id) if zone.playlist_id else None
        if pl:
            active_items = [
                item for item in pl.items
                if item.asset and item.asset.is_enabled
                and (not item.asset.start_date or item.asset.start_date <= now)
                and (not item.asset.end_date or item.asset.end_date >= now)
            ]
            zone_dict["items"] = [_item_to_dict(item) for item in active_items]

            def _zr(field, default, _pl=pl):
                val = getattr(_pl, field, None)
                if val is not None:
                    return val
                return getattr(global_settings, field, default) if global_settings else default

            zone_dict["settings"] = {
                "transition_duration": _zr("transition_duration", 1.0),
                "transition_type": _zr("transition_type", "fade"),
                "default_duration": _zr("default_duration", 10),
                "shuffle": _zr("shuffle", False),
            }

        zones_out.append(zone_dict)

    return zones_out


def _trigger_flow_hash(tf_payload: dict) -> str:
    """Compute a short hash for trigger flow branches, targets, and webhook fires."""
    branch_parts = []
    for b in tf_payload["branches"]:
        target_item_ids = "|".join(i["id"] for i in b["target_playlist"]["items"])
        wh = b.get("last_webhook_fire", "")
        cfg = json.dumps(b.get("trigger_config", {}), sort_keys=True)
        branch_parts.append(
            f"{b['id']}:{b['trigger_type']}:{b.get('priority', 0)}:"
            f"{b['target_playlist_id']}:{target_item_ids}:{cfg}:{wh}"
        )
    return hashlib.sha256(";".join(branch_parts).encode()).hexdigest()[:12]


def _zones_hash(zones_data: list[dict] | None) -> str:
    """Compute a short hash for zone configuration."""
    if not zones_data:
        return ""
    parts = []
    for z in zones_data:
        item_ids = "|".join(i["id"] for i in z.get("items", []))
        parts.append(f"{z['id']}:{z['playlist_id']}:{item_ids}")
    return hashlib.sha256(";".join(parts).encode()).hexdigest()[:12]


async def _get_default_settings(session: AsyncSession) -> dict:
    """Read global settings from DB, falling back to hardcoded defaults."""
    settings = await session.get(Settings, 1)
    if settings:
        return {
            "transition_duration": settings.transition_duration if settings.transition_duration is not None else 1.0,
            "transition_type": settings.transition_type if settings.transition_type is not None else "fade",
            "default_duration": settings.default_duration if settings.default_duration is not None else 10,
            "shuffle": settings.shuffle if settings.shuffle is not None else False,
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
        "layout_id": device.layout_id,
        "last_seen": device.last_seen.isoformat() if device.last_seen else None,
        "ip_address": device.ip_address,
        "status": device.status,
        "player_type": device.player_type,
        "resolution_detected": device.resolution_detected,
        "ram_mb": device.ram_mb,
        "storage_total_mb": device.storage_total_mb,
        "storage_free_mb": device.storage_free_mb,
        "capabilities_updated_at": device.capabilities_updated_at.isoformat() if device.capabilities_updated_at else None,
        "has_pairing_code": has_pairing_code,
        "created_at": device.created_at.isoformat() if device.created_at else None,
    }


@router.get("/devices/{device_id}/preflight")
async def preflight_check(
    device_id: str,
    playlist_id: str,
    request: Request,
    _admin: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    """Pre-flight check before assigning a playlist to a device."""
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    result = await session.execute(
        select(Playlist)
        .where(Playlist.id == playlist_id)
        .options(selectinload(Playlist.items).selectinload(PlaylistItem.asset).selectinload(Asset.asset_tags).selectinload(AssetTag.tag))
    )
    playlist = result.scalars().first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    checks = _run_preflight_checks(device, playlist)
    overall = _preflight_overall(checks)

    # Log to audit
    await audit(
        session, action="preflight_check", entity_type="device", entity_id=device_id,
        details={"playlist_id": playlist_id, "overall": overall, "checks": checks},
        token=_admin, request=request,
    )
    await session.commit()

    return {
        "device_id": device_id,
        "playlist_id": playlist_id,
        "overall": overall,
        "checks": checks,
    }


def _run_preflight_checks(device: Device, playlist: Playlist) -> list[dict]:
    """Run all pre-flight checks for a device/playlist pair."""
    checks = []

    # 1. Storage check
    enabled_items = [item for item in playlist.items if item.asset and item.asset.is_enabled]
    total_size_bytes = sum(item.asset.file_size or 0 for item in enabled_items)
    total_size_mb = total_size_bytes / (1024 * 1024) if total_size_bytes > 0 else 0

    if device.storage_free_mb is not None:
        if total_size_mb > device.storage_free_mb:
            checks.append({
                "check": "storage", "status": "fail",
                "message": f"Needs ~{total_size_mb:.0f} MB, only {device.storage_free_mb} MB free",
                "details": {"needed_mb": round(total_size_mb, 1), "free_mb": device.storage_free_mb},
            })
        elif total_size_mb > device.storage_free_mb * 0.9:
            checks.append({
                "check": "storage", "status": "warn",
                "message": f"Needs ~{total_size_mb:.0f} MB, {device.storage_free_mb} MB free (tight)",
                "details": {"needed_mb": round(total_size_mb, 1), "free_mb": device.storage_free_mb},
            })
        else:
            checks.append({
                "check": "storage", "status": "pass",
                "message": "Storage adequate",
                "details": {"needed_mb": round(total_size_mb, 1), "free_mb": device.storage_free_mb},
            })
    else:
        checks.append({
            "check": "storage", "status": "unknown",
            "message": "Device storage not reported",
            "details": {"needed_mb": round(total_size_mb, 1)},
        })

    # 2. RAM check (heuristic based on video duration)
    video_duration_min = sum(
        (item.asset.duration or 0) / 60
        for item in enabled_items
        if item.asset.asset_type == "video"
    )
    if device.ram_mb is not None:
        if video_duration_min > 30 and device.ram_mb < 4096:
            checks.append({
                "check": "ram", "status": "warn",
                "message": f"{video_duration_min:.0f} min video, only {device.ram_mb} MB RAM",
                "details": {"video_duration_min": round(video_duration_min, 1), "ram_mb": device.ram_mb},
            })
        elif video_duration_min > 10 and device.ram_mb < 2048:
            checks.append({
                "check": "ram", "status": "warn",
                "message": f"{video_duration_min:.0f} min video, only {device.ram_mb} MB RAM",
                "details": {"video_duration_min": round(video_duration_min, 1), "ram_mb": device.ram_mb},
            })
        else:
            checks.append({
                "check": "ram", "status": "pass",
                "message": "RAM adequate",
                "details": {"video_duration_min": round(video_duration_min, 1), "ram_mb": device.ram_mb},
            })
    else:
        checks.append({
            "check": "ram", "status": "unknown",
            "message": "Device RAM not reported",
            "details": {"video_duration_min": round(video_duration_min, 1)},
        })

    # 3. GPIO (placeholder)
    checks.append({
        "check": "gpio", "status": "not_applicable",
        "message": "GPIO triggers not implemented",
        "details": {},
    })

    # 4. Capabilities reported
    if device.capabilities_updated_at:
        checks.append({
            "check": "capabilities_reported", "status": "pass",
            "message": "Capabilities reported",
            "details": {"last_report": device.capabilities_updated_at.isoformat()},
        })
    else:
        checks.append({
            "check": "capabilities_reported", "status": "unknown",
            "message": "Device has not reported capabilities",
            "details": {},
        })

    return checks


def _preflight_overall(checks: list[dict]) -> str:
    """Compute overall pre-flight status from individual checks."""
    statuses = [c["status"] for c in checks if c["status"] != "not_applicable"]
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    if "unknown" in statuses:
        return "unknown"
    return "pass"
