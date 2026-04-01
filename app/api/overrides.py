"""Emergency override API — admin-only CRUD for emergency override templates."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import false as sa_false

from app.audit import record as audit
from app.auth import require_admin
from app.database import get_session
from app.models import (
    ApiToken,
    Device,
    DeviceGroup,
    DeviceGroupMembership,
    Override,
    Playlist,
    PlaylistItem,
)

router = APIRouter()


def _override_to_dict(override: Override) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    effective_active = override.is_active and not (override.expires_at and override.expires_at <= now)
    return {
        "id": override.id,
        "name": override.name,
        "content_type": override.content_type,
        "content": override.content,
        "target_type": override.target_type,
        "target_id": override.target_id,
        "created_by": override.created_by,
        "creator_name": (
            override.creator.display_name or override.creator.username
            if override.creator else None
        ),
        "is_active": effective_active,
        "created_at": override.created_at.isoformat() if override.created_at else None,
        "activated_at": override.activated_at.isoformat() if override.activated_at else None,
        "expires_at": override.expires_at.isoformat() if override.expires_at else None,
        "duration_minutes": override.duration_minutes,
    }


@router.get("/overrides")
async def list_overrides(
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Override)
        .options(selectinload(Override.creator))
        .order_by(Override.created_at.desc())
    )
    overrides = result.scalars().all()
    return [_override_to_dict(o) for o in overrides]


@router.post("/overrides", status_code=201)
async def create_override(
    body: dict,
    request: Request,
    token: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    content_type = body.get("content_type", "").strip()
    if content_type not in ("message", "playlist"):
        raise HTTPException(status_code=400, detail="content_type must be 'message' or 'playlist'")

    content = body.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Content is required")

    target_type = body.get("target_type", "all").strip()
    if target_type not in ("all", "group", "device"):
        raise HTTPException(status_code=400, detail="target_type must be 'all', 'group', or 'device'")

    target_id = body.get("target_id")
    if target_type == "all":
        target_id = None
    elif not target_id:
        raise HTTPException(status_code=400, detail="target_id required for device/group target")

    # Validate target exists
    if target_type == "device" and target_id:
        device = await session.get(Device, target_id)
        if not device:
            raise HTTPException(status_code=400, detail="Target device not found")
    elif target_type == "group" and target_id:
        group = await session.get(DeviceGroup, target_id)
        if not group:
            raise HTTPException(status_code=400, detail="Target group not found")

    # Validate playlist exists if content_type is playlist
    if content_type == "playlist":
        playlist = await session.get(Playlist, content)
        if not playlist:
            raise HTTPException(status_code=400, detail="Playlist not found")

    # Parse duration_minutes (stored on template, used at activation time)
    duration_minutes = body.get("duration_minutes")
    if duration_minutes is not None:
        try:
            duration_minutes = int(duration_minutes)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid duration_minutes")

    override = Override(
        name=name,
        content_type=content_type,
        content=content,
        target_type=target_type,
        target_id=target_id,
        created_by=token.user_id,
        duration_minutes=duration_minutes,
        is_active=False,
        expires_at=None,
        activated_at=None,
    )
    session.add(override)
    await session.flush()

    await audit(
        session,
        action="create",
        entity_type="override",
        entity_id=override.id,
        details={
            "name": name,
            "content_type": content_type,
            "target_type": target_type,
            "target_id": target_id,
            "duration_minutes": duration_minutes,
        },
        token=token,
        request=request,
    )
    await session.commit()

    # Reload with relationship
    result = await session.execute(
        select(Override)
        .where(Override.id == override.id)
        .options(selectinload(Override.creator))
    )
    override = result.scalars().first()
    return _override_to_dict(override)


@router.get("/overrides/{override_id}")
async def get_override(
    override_id: str,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Override)
        .where(Override.id == override_id)
        .options(selectinload(Override.creator))
    )
    override = result.scalars().first()
    if not override:
        raise HTTPException(status_code=404, detail="Override not found")
    return _override_to_dict(override)


@router.patch("/overrides/{override_id}")
async def update_override(
    override_id: str,
    body: dict,
    request: Request,
    token: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Override)
        .where(Override.id == override_id)
        .options(selectinload(Override.creator))
    )
    override = result.scalars().first()
    if not override:
        raise HTTPException(status_code=404, detail="Override not found")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    changes = {}

    # Activation / deactivation
    if "is_active" in body:
        new_active = bool(body["is_active"])

        if new_active and not override.is_active:
            # Activate
            override.is_active = True
            override.activated_at = now
            if override.duration_minutes:
                override.expires_at = now + timedelta(minutes=override.duration_minutes)
            else:
                override.expires_at = None
            changes["is_active"] = True
            changes["activated_at"] = override.activated_at.isoformat()
            changes["expires_at"] = override.expires_at.isoformat() if override.expires_at else None

            await audit(
                session,
                action="activate",
                entity_type="override",
                entity_id=override_id,
                details={"name": override.name, "changes": changes},
                token=token,
                request=request,
            )
            await session.commit()
            await session.refresh(override)
            result = await session.execute(
                select(Override)
                .where(Override.id == override_id)
                .options(selectinload(Override.creator))
            )
            override = result.scalars().first()
            return _override_to_dict(override)

        elif not new_active and override.is_active:
            # Deactivate
            override.is_active = False
            override.expires_at = None
            changes["is_active"] = False

            await audit(
                session,
                action="deactivate",
                entity_type="override",
                entity_id=override_id,
                details={"name": override.name, "changes": changes},
                token=token,
                request=request,
            )
            await session.commit()
            await session.refresh(override)
            result = await session.execute(
                select(Override)
                .where(Override.id == override_id)
                .options(selectinload(Override.creator))
            )
            override = result.scalars().first()
            return _override_to_dict(override)

    # Edit fields — only allowed when inactive
    editable_fields = {"name", "content_type", "content", "target_type", "target_id", "duration_minutes"}
    edit_keys = editable_fields & body.keys()
    if edit_keys:
        if override.is_active:
            raise HTTPException(status_code=400, detail="Cannot edit an active override. Deactivate it first.")

        for key in edit_keys:
            setattr(override, key, body[key])
            changes[key] = body[key]

        await audit(
            session,
            action="update",
            entity_type="override",
            entity_id=override_id,
            details={"name": override.name, "changes": changes},
            token=token,
            request=request,
        )

    await session.commit()
    await session.refresh(override)

    result = await session.execute(
        select(Override)
        .where(Override.id == override_id)
        .options(selectinload(Override.creator))
    )
    override = result.scalars().first()
    return _override_to_dict(override)


@router.delete("/overrides/{override_id}")
async def delete_override(
    override_id: str,
    request: Request,
    token: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    override = await session.get(Override, override_id)
    if not override:
        raise HTTPException(status_code=404, detail="Override not found")

    if override.is_active:
        raise HTTPException(status_code=400, detail="Cannot delete an active override. Deactivate it first.")

    await audit(
        session,
        action="delete",
        entity_type="override",
        entity_id=override_id,
        details={"name": override.name},
        token=token,
        request=request,
    )
    await session.delete(override)
    await session.commit()
    return {"ok": True}


async def evaluate_override_for_device(
    device_id: str,
    session: AsyncSession,
) -> Override | None:
    """Find the most relevant active override targeting this device.

    Returns the Override object if one applies, or None.
    Overrides take absolute priority over schedules.
    This is a read-only evaluation — it does not modify the database.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Find groups this device belongs to
    grp_result = await session.execute(
        select(DeviceGroupMembership.group_id)
        .where(DeviceGroupMembership.device_id == device_id)
    )
    group_ids = [row[0] for row in grp_result.all()]

    # Filter by target in SQL: only load overrides that could apply to this device
    target_filter = or_(
        Override.target_type == "all",
        (Override.target_type == "device") & (Override.target_id == device_id),
        (Override.target_type == "group") & (Override.target_id.in_(group_ids)) if group_ids else sa_false(),
    )
    result = await session.execute(
        select(Override).where(
            Override.is_active == True,
            target_filter,
            # Exclude already-expired overrides at the SQL level
            or_(Override.expires_at.is_(None), Override.expires_at > now),
        )
    )
    overrides = result.scalars().all()

    if not overrides:
        return None

    # Most specific target wins; ties broken by most recently activated
    target_priority = {"device": 2, "group": 1, "all": 0}
    best = max(overrides, key=lambda o: (target_priority.get(o.target_type, 0), o.activated_at or o.created_at))
    return best
