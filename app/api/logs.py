"""API endpoints for reading and clearing the error log."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from app.auth import require_admin
from app.models import ApiToken

router = APIRouter()

ERRORS_FILE = Path("logs/errors.jsonl")


@router.get("/logs/errors")
async def get_error_logs(
    _admin: ApiToken = Depends(require_admin),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    level: str = Query(None),
    search: str = Query(None),
):
    """Read parsed entries from errors.jsonl, newest first."""
    if not ERRORS_FILE.exists():
        return {"entries": [], "total": 0}

    entries = []
    for line in ERRORS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Filter by level
        if level and entry.get("level", "").upper() != level.upper():
            continue
        # Filter by search text
        if search:
            search_lower = search.lower()
            searchable = f"{entry.get('message', '')} {entry.get('module', '')} {entry.get('traceback', '')}".lower()
            if search_lower not in searchable:
                continue
        entries.append(entry)

    # Newest first
    entries.reverse()
    total = len(entries)
    page = entries[offset : offset + limit]
    return {"entries": page, "total": total}


@router.delete("/logs/errors")
async def clear_error_logs(
    _admin: ApiToken = Depends(require_admin),
):
    """Clear the error log file."""
    if ERRORS_FILE.exists():
        ERRORS_FILE.write_text("", encoding="utf-8")
    return {"status": "cleared"}
