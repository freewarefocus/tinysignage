import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit import record as audit
from app.auth import require_editor, require_viewer
from app.database import get_session
from app.models import (
    ApiToken,
    Device,
    DeviceGroup,
    DeviceGroupMembership,
    Playlist,
    Schedule,
)

router = APIRouter()


def _validate_time_format(value: str | None, field_name: str):
    """Validate HH:MM format with range checks."""
    if value is None:
        return
    if not re.match(r"^\d{2}:\d{2}$", value):
        raise HTTPException(status_code=400, detail=f"{field_name} must be HH:MM format")
    hh, mm = int(value[:2]), int(value[3:])
    if hh < 0 or hh > 23:
        raise HTTPException(status_code=400, detail=f"{field_name} hour must be 00-23")
    if mm < 0 or mm > 59:
        raise HTTPException(status_code=400, detail=f"{field_name} minute must be 00-59")


def _validate_days_of_week(value: str | None):
    """Validate comma-separated day digits 0-6."""
    if value is None:
        return
    parts = value.split(",")
    for part in parts:
        part = part.strip()
        if not part.isdigit() or int(part) < 0 or int(part) > 6:
            raise HTTPException(
                status_code=400,
                detail=f"days_of_week must be comma-separated digits 0-6, got '{part}'",
            )


def _schedule_to_dict(schedule: Schedule) -> dict:
    return {
        "id": schedule.id,
        "name": schedule.name,
        "playlist_id": schedule.playlist_id,
        "playlist_name": schedule.playlist.name if schedule.playlist else None,
        "target_type": schedule.target_type,
        "target_id": schedule.target_id,
        "start_time": schedule.start_time,
        "end_time": schedule.end_time,
        "days_of_week": schedule.days_of_week,
        "start_date": schedule.start_date.isoformat() if schedule.start_date else None,
        "end_date": schedule.end_date.isoformat() if schedule.end_date else None,
        "priority": schedule.priority,
        "is_active": schedule.is_active,
        "created_at": schedule.created_at.isoformat() if schedule.created_at else None,
        "updated_at": schedule.updated_at.isoformat() if schedule.updated_at else None,
    }


@router.get("/schedules")
async def list_schedules(
    _admin: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Schedule).options(selectinload(Schedule.playlist))
    )
    schedules = result.scalars().all()
    return [_schedule_to_dict(s) for s in schedules]


@router.post("/schedules", status_code=201)
async def create_schedule(
    body: dict,
    request: Request,
    _admin: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    playlist_id = body.get("playlist_id")
    if not playlist_id:
        raise HTTPException(status_code=400, detail="playlist_id is required")

    playlist = await session.get(Playlist, playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    target_type = body.get("target_type", "all")
    if target_type not in ("device", "group", "all"):
        raise HTTPException(status_code=400, detail="target_type must be device, group, or all")

    target_id = body.get("target_id")
    if target_type != "all" and not target_id:
        raise HTTPException(status_code=400, detail="target_id required for device/group targets")

    # Validate target exists
    if target_type == "device" and target_id:
        if not await session.get(Device, target_id):
            raise HTTPException(status_code=404, detail="Target device not found")
    elif target_type == "group" and target_id:
        if not await session.get(DeviceGroup, target_id):
            raise HTTPException(status_code=404, detail="Target group not found")

    _validate_time_format(body.get("start_time"), "start_time")
    _validate_time_format(body.get("end_time"), "end_time")
    _validate_days_of_week(body.get("days_of_week"))

    schedule = Schedule(
        name=name,
        playlist_id=playlist_id,
        target_type=target_type,
        target_id=target_id if target_type != "all" else None,
        start_time=body.get("start_time"),
        end_time=body.get("end_time"),
        days_of_week=body.get("days_of_week"),
        start_date=_parse_date(body.get("start_date")),
        end_date=_parse_date(body.get("end_date")),
        priority=body.get("priority", 0),
        is_active=body.get("is_active", True),
    )
    session.add(schedule)
    await session.flush()
    await audit(session, action="create", entity_type="schedule", entity_id=schedule.id,
                details={"name": name, "playlist_id": playlist_id, "target_type": target_type},
                token=_admin, request=request)
    await session.commit()

    # Re-fetch with playlist loaded
    result = await session.execute(
        select(Schedule)
        .where(Schedule.id == schedule.id)
        .options(selectinload(Schedule.playlist))
    )
    schedule = result.scalars().first()
    return _schedule_to_dict(schedule)


@router.get("/schedules/{schedule_id}")
async def get_schedule(
    schedule_id: str,
    _admin: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Schedule)
        .where(Schedule.id == schedule_id)
        .options(selectinload(Schedule.playlist))
    )
    schedule = result.scalars().first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return _schedule_to_dict(schedule)


@router.patch("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    body: dict,
    request: Request,
    _admin: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    schedule = await session.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if "start_time" in body:
        _validate_time_format(body["start_time"], "start_time")
    if "end_time" in body:
        _validate_time_format(body["end_time"], "end_time")
    if "days_of_week" in body:
        _validate_days_of_week(body["days_of_week"])

    simple_fields = {"name", "start_time", "end_time", "days_of_week", "priority", "is_active"}
    for key in simple_fields:
        if key in body:
            setattr(schedule, key, body[key])

    if "playlist_id" in body:
        if not await session.get(Playlist, body["playlist_id"]):
            raise HTTPException(status_code=404, detail="Playlist not found")
        schedule.playlist_id = body["playlist_id"]

    if "target_type" in body:
        target_type = body["target_type"]
        if target_type not in ("device", "group", "all"):
            raise HTTPException(status_code=400, detail="target_type must be device, group, or all")
        schedule.target_type = target_type
        schedule.target_id = body.get("target_id") if target_type != "all" else None

    if "start_date" in body:
        schedule.start_date = _parse_date(body["start_date"])
    if "end_date" in body:
        schedule.end_date = _parse_date(body["end_date"])

    await audit(session, action="update", entity_type="schedule", entity_id=schedule_id,
                details={"name": schedule.name, "changes": {k: v for k, v in body.items()}},
                token=_admin, request=request)
    await session.commit()

    # Re-fetch with playlist loaded
    result = await session.execute(
        select(Schedule)
        .where(Schedule.id == schedule.id)
        .options(selectinload(Schedule.playlist))
    )
    schedule = result.scalars().first()
    return _schedule_to_dict(schedule)


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    request: Request,
    _admin: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    schedule = await session.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await audit(session, action="delete", entity_type="schedule", entity_id=schedule_id,
                details={"name": schedule.name}, token=_admin, request=request)
    await session.delete(schedule)
    await session.commit()
    return {"ok": True}


async def evaluate_schedule_for_device(
    device_id: str,
    session: AsyncSession,
) -> str | None:
    """Determine the effective playlist for a device based on active schedules.

    Returns the playlist_id from the highest-priority active schedule
    that matches the device right now, or None if no schedule applies
    (in which case the device's default playlist_id should be used).
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    current_time = now.strftime("%H:%M")
    current_day = str(now.weekday())  # 0=Mon..6=Sun

    # Find all groups this device belongs to
    result = await session.execute(
        select(DeviceGroupMembership.group_id)
        .where(DeviceGroupMembership.device_id == device_id)
    )
    group_ids = [row[0] for row in result.all()]

    # Fetch all active schedules
    result = await session.execute(
        select(Schedule).where(Schedule.is_active == True)
    )
    schedules = result.scalars().all()

    matching = []
    for s in schedules:
        # Check target match
        if s.target_type == "device" and s.target_id != device_id:
            continue
        if s.target_type == "group" and s.target_id not in group_ids:
            continue
        # target_type "all" always matches

        # Check date range
        if s.start_date and s.start_date > now:
            continue
        if s.end_date and s.end_date < now:
            continue

        # Check day of week
        if s.days_of_week:
            allowed_days = s.days_of_week.split(",")
            if current_day not in allowed_days:
                continue

        # Check time window
        if s.start_time and s.end_time:
            if s.start_time <= s.end_time:
                # Normal window: e.g. 09:00-17:00
                if not (s.start_time <= current_time < s.end_time):
                    continue
            else:
                # Overnight window: e.g. 22:00-06:00
                if not (current_time >= s.start_time or current_time < s.end_time):
                    continue
        elif s.start_time:
            if current_time < s.start_time:
                continue
        elif s.end_time:
            if current_time >= s.end_time:
                continue

        matching.append(s)

    if not matching:
        return None

    # Highest priority wins; ties broken by most specific target
    target_priority = {"device": 2, "group": 1, "all": 0}
    best = max(matching, key=lambda s: (s.priority, target_priority.get(s.target_type, 0)))
    return best.playlist_id


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None
