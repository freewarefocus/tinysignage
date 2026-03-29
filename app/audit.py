"""Audit logging — records who changed what and when."""

import json
import logging

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiToken, AuditLog

log = logging.getLogger("tinysignage.audit")


async def record(
    session: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict | None = None,
    token: ApiToken | None = None,
    request: Request | None = None,
) -> None:
    """Write an audit log entry.

    Call this after a successful mutation (post-commit or within the same
    transaction — the caller decides when to commit).
    """
    username = None
    user_id = None
    ip_address = None

    if token:
        user_id = token.user_id
        username = token.name
        if token.user and hasattr(token.user, "username"):
            username = token.user.username

    if request and request.client:
        ip_address = request.client.host

    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details) if details else None,
        user_id=user_id,
        username=username,
        ip_address=ip_address,
    )
    session.add(entry)

    log.info(
        "AUDIT %s %s %s by %s",
        action,
        entity_type,
        entity_id or "-",
        username or "system",
    )
