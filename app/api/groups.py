from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_admin
from app.database import get_session
from app.models import ApiToken, Device, DeviceGroup, DeviceGroupMembership, Playlist, Schedule

router = APIRouter()


def _group_to_dict(group: DeviceGroup, include_members: bool = False) -> dict:
    result = {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "member_count": len(group.memberships) if group.memberships else 0,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "updated_at": group.updated_at.isoformat() if group.updated_at else None,
    }
    if include_members:
        result["members"] = [
            {
                "device_id": m.device.id,
                "name": m.device.name,
                "status": m.device.status,
                "playlist_id": m.device.playlist_id,
            }
            for m in group.memberships
            if m.device
        ]
    return result


@router.get("/groups")
async def list_groups(
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(DeviceGroup).options(
            selectinload(DeviceGroup.memberships).selectinload(DeviceGroupMembership.device)
        )
    )
    groups = result.scalars().all()
    return [_group_to_dict(g) for g in groups]


@router.post("/groups", status_code=201)
async def create_group(
    body: dict,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    group = DeviceGroup(name=name, description=body.get("description"))
    session.add(group)
    await session.commit()
    # Re-fetch with eager loading to avoid lazy-load in async context
    result = await session.execute(
        select(DeviceGroup)
        .where(DeviceGroup.id == group.id)
        .options(selectinload(DeviceGroup.memberships))
    )
    group = result.scalars().first()
    return _group_to_dict(group)


@router.get("/groups/{group_id}")
async def get_group(
    group_id: str,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(DeviceGroup)
        .where(DeviceGroup.id == group_id)
        .options(
            selectinload(DeviceGroup.memberships).selectinload(DeviceGroupMembership.device)
        )
    )
    group = result.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return _group_to_dict(group, include_members=True)


@router.patch("/groups/{group_id}")
async def update_group(
    group_id: str,
    body: dict,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    group = await session.get(DeviceGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if "name" in body:
        group.name = body["name"]
    if "description" in body:
        group.description = body["description"]
    await session.commit()
    # Re-fetch with eager loading to avoid lazy-load in async context
    result = await session.execute(
        select(DeviceGroup)
        .where(DeviceGroup.id == group.id)
        .options(selectinload(DeviceGroup.memberships))
    )
    group = result.scalars().first()
    return _group_to_dict(group)


@router.delete("/groups/{group_id}")
async def delete_group(
    group_id: str,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    group = await session.get(DeviceGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Bug #3: Delete schedules targeting this group (they're inert once group is gone)
    result = await session.execute(
        select(Schedule).where(
            Schedule.target_type == "group",
            Schedule.target_id == group_id,
        )
    )
    for schedule in result.scalars().all():
        await session.delete(schedule)

    await session.delete(group)
    await session.commit()
    return {"ok": True}


@router.post("/groups/{group_id}/members")
async def add_member(
    group_id: str,
    body: dict,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    device_id = body.get("device_id")
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")

    group = await session.get(DeviceGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Check if already a member
    existing = await session.get(DeviceGroupMembership, (device_id, group_id))
    if existing:
        raise HTTPException(status_code=409, detail="Device already in group")

    membership = DeviceGroupMembership(device_id=device_id, group_id=group_id)
    session.add(membership)
    await session.commit()
    return {"ok": True}


@router.delete("/groups/{group_id}/members/{device_id}")
async def remove_member(
    group_id: str,
    device_id: str,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    membership = await session.get(DeviceGroupMembership, (device_id, group_id))
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    await session.delete(membership)
    await session.commit()
    return {"ok": True}


@router.post("/groups/{group_id}/assign-playlist")
async def assign_playlist_to_group(
    group_id: str,
    body: dict,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Push a playlist assignment to all devices in a group."""
    playlist_id = body.get("playlist_id")
    if not playlist_id:
        raise HTTPException(status_code=400, detail="playlist_id is required")

    # Bug #11: Validate playlist exists
    playlist = await session.get(Playlist, playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    result = await session.execute(
        select(DeviceGroup)
        .where(DeviceGroup.id == group_id)
        .options(
            selectinload(DeviceGroup.memberships).selectinload(DeviceGroupMembership.device)
        )
    )
    group = result.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    updated = 0
    for membership in group.memberships:
        if membership.device:
            membership.device.playlist_id = playlist_id
            updated += 1

    await session.commit()
    return {"ok": True, "updated_count": updated}
