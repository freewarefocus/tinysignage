import random
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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

# --- RRULE day abbreviation mapping ---
_RRULE_DAY_MAP = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


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


def _validate_recurrence_rule(value: str | None):
    """Basic validation of iCal-style RRULE string."""
    if not value:
        return
    parts = value.split(";")
    has_freq = False
    for part in parts:
        if "=" not in part:
            raise HTTPException(status_code=400, detail=f"Invalid recurrence_rule part: '{part}'")
        key, val = part.split("=", 1)
        key = key.strip().upper()
        if key == "FREQ":
            has_freq = True
            if val.strip().upper() not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
                raise HTTPException(status_code=400, detail=f"Unsupported FREQ: '{val}'")
        elif key == "BYDAY":
            for d in val.split(","):
                d = d.strip().upper()
                if d not in _RRULE_DAY_MAP:
                    raise HTTPException(status_code=400, detail=f"Invalid BYDAY value: '{d}'")
        elif key == "INTERVAL":
            if not val.strip().isdigit() or int(val.strip()) < 1:
                raise HTTPException(status_code=400, detail="INTERVAL must be a positive integer")
        elif key == "BYMONTHDAY":
            for d in val.split(","):
                d = d.strip()
                if not d.isdigit() or int(d) < 1 or int(d) > 31:
                    raise HTTPException(status_code=400, detail=f"Invalid BYMONTHDAY: '{d}'")
    if not has_freq:
        raise HTTPException(status_code=400, detail="recurrence_rule must contain FREQ")


def _parse_rrule(rule: str) -> dict:
    """Parse an RRULE string into a dict of components."""
    result = {}
    for part in rule.split(";"):
        key, val = part.split("=", 1)
        result[key.strip().upper()] = val.strip()
    return result


def _rrule_matches_date(rule_str: str, check_date: datetime, schedule_start: datetime | None) -> bool:
    """Check if a given date matches the recurrence rule.

    Supports FREQ=DAILY, WEEKLY, MONTHLY, YEARLY with BYDAY, INTERVAL, BYMONTHDAY.
    """
    rule = _parse_rrule(rule_str)
    freq = rule.get("FREQ", "").upper()
    interval = int(rule.get("INTERVAL", "1"))
    weekday = check_date.weekday()  # 0=Mon..6=Sun

    if freq == "DAILY":
        if interval > 1 and schedule_start:
            delta = (check_date - schedule_start).days
            if delta < 0 or delta % interval != 0:
                return False
        return True

    if freq == "WEEKLY":
        byday = rule.get("BYDAY")
        if byday:
            allowed_days = [_RRULE_DAY_MAP[d.strip().upper()] for d in byday.split(",") if d.strip().upper() in _RRULE_DAY_MAP]
            if weekday not in allowed_days:
                return False
        if interval > 1 and schedule_start:
            # Use Monday-aligned date difference (handles 53-week ISO years correctly)
            start_monday = schedule_start - timedelta(days=schedule_start.weekday())
            check_monday = check_date - timedelta(days=check_date.weekday())
            weeks_diff = (check_monday - start_monday).days // 7
            if weeks_diff < 0 or weeks_diff % interval != 0:
                return False
        return True

    if freq == "MONTHLY":
        bymonthday = rule.get("BYMONTHDAY")
        if bymonthday:
            allowed_days = [int(d.strip()) for d in bymonthday.split(",")]
            if check_date.day not in allowed_days:
                return False
        elif schedule_start:
            if check_date.day != schedule_start.day:
                return False
        if interval > 1 and schedule_start:
            months_diff = (check_date.year - schedule_start.year) * 12 + (check_date.month - schedule_start.month)
            if months_diff < 0 or months_diff % interval != 0:
                return False
        return True

    if freq == "YEARLY":
        if schedule_start:
            if check_date.month != schedule_start.month or check_date.day != schedule_start.day:
                return False
            if interval > 1:
                year_diff = check_date.year - schedule_start.year
                if year_diff < 0 or year_diff % interval != 0:
                    return False
        return True

    # Unknown freq — don't match
    return False


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
        "recurrence_rule": schedule.recurrence_rule,
        "priority_weight": schedule.priority_weight,
        "transition_playlist_id": schedule.transition_playlist_id,
        "transition_playlist_name": (
            schedule.transition_playlist.name
            if schedule.transition_playlist else None
        ),
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
        select(Schedule).options(
            selectinload(Schedule.playlist),
            selectinload(Schedule.transition_playlist),
        )
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
    _validate_recurrence_rule(body.get("recurrence_rule"))

    # Validate transition playlist if provided
    transition_playlist_id = body.get("transition_playlist_id")
    if transition_playlist_id:
        if not await session.get(Playlist, transition_playlist_id):
            raise HTTPException(status_code=404, detail="Transition playlist not found")

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
        recurrence_rule=body.get("recurrence_rule"),
        priority_weight=body.get("priority_weight", 1.0),
        transition_playlist_id=transition_playlist_id,
        is_active=body.get("is_active", True),
    )
    session.add(schedule)
    await session.flush()
    await audit(session, action="create", entity_type="schedule", entity_id=schedule.id,
                details={"name": name, "playlist_id": playlist_id, "target_type": target_type},
                token=_admin, request=request)
    await session.commit()

    # Re-fetch with relationships loaded
    result = await session.execute(
        select(Schedule)
        .where(Schedule.id == schedule.id)
        .options(
            selectinload(Schedule.playlist),
            selectinload(Schedule.transition_playlist),
        )
    )
    schedule = result.scalars().first()
    return _schedule_to_dict(schedule)


@router.get("/schedules/preview/timeline")
async def preview_schedule_timeline(
    device_id: str = Query(...),
    date: str = Query(None),
    _token: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    """Return a 24-hour timeline showing which playlist plays in each 30-min slot.

    Response: { date, device_id, device_name, slots: [ { time, playlist_id, playlist_name, schedule_id, schedule_name } ] }
    """
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Parse target date or default to today (UTC)
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    else:
        target_date = datetime.now(timezone.utc).replace(tzinfo=None)
    target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get device's group memberships
    result = await session.execute(
        select(DeviceGroupMembership.group_id)
        .where(DeviceGroupMembership.device_id == device_id)
    )
    group_ids = [row[0] for row in result.all()]

    # Fetch all active schedules with playlists
    result = await session.execute(
        select(Schedule)
        .where(Schedule.is_active == True)
        .options(selectinload(Schedule.playlist))
    )
    schedules = result.scalars().all()

    # Build 48 half-hour slots (00:00, 00:30, 01:00, ... 23:30)
    slots = []
    for slot_idx in range(48):
        slot_hour = slot_idx // 2
        slot_min = (slot_idx % 2) * 30
        slot_time = f"{slot_hour:02d}:{slot_min:02d}"
        check_dt = target_date.replace(hour=slot_hour, minute=slot_min)
        current_day = str(check_dt.weekday())

        matching = []
        for s in schedules:
            # Target match
            if s.target_type == "device" and s.target_id != device_id:
                continue
            if s.target_type == "group" and s.target_id not in group_ids:
                continue

            # Date range
            if s.start_date and s.start_date > check_dt:
                continue
            if s.end_date and s.end_date < check_dt:
                continue

            # Recurrence rule (takes precedence over days_of_week)
            if s.recurrence_rule:
                if not _rrule_matches_date(s.recurrence_rule, check_dt, s.start_date):
                    continue
            elif s.days_of_week:
                if current_day not in s.days_of_week.split(","):
                    continue

            # Time window
            if s.start_time and s.end_time:
                if s.start_time <= s.end_time:
                    if not (s.start_time <= slot_time < s.end_time):
                        continue
                else:
                    if not (slot_time >= s.start_time or slot_time < s.end_time):
                        continue
            elif s.start_time:
                if slot_time < s.start_time:
                    continue
            elif s.end_time:
                if slot_time >= s.end_time:
                    continue

            matching.append(s)

        if matching:
            best = _pick_best_schedule(matching)
            slots.append({
                "time": slot_time,
                "playlist_id": best.playlist_id,
                "playlist_name": best.playlist.name if best.playlist else None,
                "schedule_id": best.id,
                "schedule_name": best.name,
                "priority": best.priority,
            })
        else:
            # Falls back to device default
            slots.append({
                "time": slot_time,
                "playlist_id": device.playlist_id,
                "playlist_name": None,
                "schedule_id": None,
                "schedule_name": "Default",
                "priority": -1,
            })

    # Resolve default playlist name
    default_pl = None
    if device.playlist_id:
        default_pl = await session.get(Playlist, device.playlist_id)
    for slot in slots:
        if slot["schedule_id"] is None and default_pl:
            slot["playlist_name"] = default_pl.name

    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "device_id": device_id,
        "device_name": device.name,
        "default_playlist_id": device.playlist_id,
        "default_playlist_name": default_pl.name if default_pl else None,
        "slots": slots,
    }


@router.get("/schedules/{schedule_id}")
async def get_schedule(
    schedule_id: str,
    _admin: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Schedule)
        .where(Schedule.id == schedule_id)
        .options(
            selectinload(Schedule.playlist),
            selectinload(Schedule.transition_playlist),
        )
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
    if "recurrence_rule" in body:
        _validate_recurrence_rule(body["recurrence_rule"])

    simple_fields = {
        "name", "start_time", "end_time", "days_of_week",
        "priority", "is_active", "recurrence_rule", "priority_weight",
    }
    for key in simple_fields:
        if key in body:
            setattr(schedule, key, body[key])

    if "playlist_id" in body:
        if not await session.get(Playlist, body["playlist_id"]):
            raise HTTPException(status_code=404, detail="Playlist not found")
        schedule.playlist_id = body["playlist_id"]

    if "transition_playlist_id" in body:
        tp_id = body["transition_playlist_id"]
        if tp_id and not await session.get(Playlist, tp_id):
            raise HTTPException(status_code=404, detail="Transition playlist not found")
        schedule.transition_playlist_id = tp_id

    if "target_type" in body:
        target_type = body["target_type"]
        if target_type not in ("device", "group", "all"):
            raise HTTPException(status_code=400, detail="target_type must be device, group, or all")
        target_id = body.get("target_id") if target_type != "all" else None
        schedule.target_type = target_type
        schedule.target_id = target_id

        # Validate target exists
        if target_type == "device" and target_id:
            if not await session.get(Device, target_id):
                raise HTTPException(status_code=404, detail="Target device not found")
        elif target_type == "group" and target_id:
            if not await session.get(DeviceGroup, target_id):
                raise HTTPException(status_code=404, detail="Target group not found")

    if "start_date" in body:
        schedule.start_date = _parse_date(body["start_date"])
    if "end_date" in body:
        schedule.end_date = _parse_date(body["end_date"])

    await audit(session, action="update", entity_type="schedule", entity_id=schedule_id,
                details={"name": schedule.name, "changes": {k: v for k, v in body.items()}},
                token=_admin, request=request)
    await session.commit()

    # Re-fetch with relationships loaded
    result = await session.execute(
        select(Schedule)
        .where(Schedule.id == schedule.id)
        .options(
            selectinload(Schedule.playlist),
            selectinload(Schedule.transition_playlist),
        )
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


def _pick_best_schedule(matching: list[Schedule]) -> Schedule:
    """Pick the winning schedule from a list of matching schedules.

    Highest priority wins. When multiple schedules share the same max priority,
    use weighted random selection based on priority_weight. Ties also consider
    target specificity (device > group > all).
    """
    if len(matching) == 1:
        return matching[0]

    target_priority = {"device": 2, "group": 1, "all": 0}
    max_priority = max(s.priority for s in matching)
    top = [s for s in matching if s.priority == max_priority]

    if len(top) == 1:
        return top[0]

    # Among same-priority schedules, try target specificity first
    max_target = max(target_priority.get(s.target_type, 0) for s in top)
    most_specific = [s for s in top if target_priority.get(s.target_type, 0) == max_target]

    if len(most_specific) == 1:
        return most_specific[0]

    # Weighted random among equally-specific, equally-prioritized schedules
    weights = [s.priority_weight for s in most_specific]
    total = sum(weights)
    if total <= 0:
        return most_specific[0]
    return random.choices(most_specific, weights=weights, k=1)[0]


async def evaluate_schedule_for_device(
    device_id: str,
    session: AsyncSession,
) -> tuple[str | None, str | None]:
    """Determine the effective playlist for a device based on active schedules.

    Returns (playlist_id, transition_playlist_id) from the winning schedule,
    or (None, None) if no schedule applies.

    NOTE: Time-of-day checks use UTC. This is correct for single-timezone
    deployments where the server and admin share the same timezone. For
    multi-timezone support, each schedule would need a timezone field and
    conversion logic — deferred to a future session.
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

        # Recurrence rule takes precedence over days_of_week
        if s.recurrence_rule:
            if not _rrule_matches_date(s.recurrence_rule, now, s.start_date):
                continue
        elif s.days_of_week:
            allowed_days = s.days_of_week.split(",")
            if current_day not in allowed_days:
                continue

        # Check time window
        if s.start_time and s.end_time:
            if s.start_time <= s.end_time:
                if not (s.start_time <= current_time < s.end_time):
                    continue
            else:
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
        return None, None

    best = _pick_best_schedule(matching)
    return best.playlist_id, best.transition_playlist_id


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid date format: '{value}' (expected ISO 8601)")
