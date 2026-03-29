"""Audit log API — read-only query interface for audit trail."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_session
from app.models import ApiToken, AuditLog

router = APIRouter()


@router.get("/audit")
async def list_audit_logs(
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action: str = Query(None),
    entity_type: str = Query(None),
    user: str = Query(None),
    search: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    """Query audit log entries with filtering. Newest first."""
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
        count_query = count_query.where(AuditLog.entity_type == entity_type)
    if user:
        escaped_user = user.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(AuditLog.username.ilike(f"%{escaped_user}%"))
        count_query = count_query.where(AuditLog.username.ilike(f"%{escaped_user}%"))
    if search:
        escaped_search = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped_search}%"
        search_filter = AuditLog.details.ilike(pattern) | AuditLog.username.ilike(pattern)
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    if date_from:
        try:
            parsed_from = datetime.fromisoformat(date_from)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format (expected ISO 8601)")
        query = query.where(AuditLog.timestamp >= parsed_from)
        count_query = count_query.where(AuditLog.timestamp >= parsed_from)
    if date_to:
        try:
            parsed_to = datetime.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format (expected ISO 8601)")
        query = query.where(AuditLog.timestamp <= parsed_to)
        count_query = count_query.where(AuditLog.timestamp <= parsed_to)

    total = (await session.execute(count_query)).scalar()

    query = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    entries = result.scalars().all()

    return {
        "entries": [_entry_to_dict(e) for e in entries],
        "total": total,
    }


@router.get("/audit/actions")
async def list_audit_actions(
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Return distinct action values for filter dropdowns."""
    result = await session.execute(
        select(AuditLog.action).distinct().order_by(AuditLog.action)
    )
    actions = [row[0] for row in result.all()]

    result = await session.execute(
        select(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type)
    )
    entity_types = [row[0] for row in result.all()]

    return {"actions": actions, "entity_types": entity_types}


def _entry_to_dict(entry: AuditLog) -> dict:
    details = None
    if entry.details:
        try:
            details = json.loads(entry.details)
        except (json.JSONDecodeError, TypeError):
            details = entry.details

    return {
        "id": entry.id,
        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
        "user_id": entry.user_id,
        "username": entry.username,
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "details": details,
        "ip_address": entry.ip_address,
    }
