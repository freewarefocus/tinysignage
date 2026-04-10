import json
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit import record as audit
from app.auth import require_editor, require_viewer
from app.database import get_session
from app.models import ApiToken, Playlist, TriggerBranch, TriggerFlow

router = APIRouter()

VALID_TRIGGER_TYPES = {"keyboard", "touch_zone", "gpio", "joystick", "webhook", "timeout", "loop_count"}


def _flow_summary(flow: TriggerFlow, branch_count: int) -> dict:
    return {
        "id": flow.id,
        "name": flow.name,
        "description": flow.description,
        "branch_count": branch_count,
        "created_at": flow.created_at.isoformat() if flow.created_at else None,
        "updated_at": flow.updated_at.isoformat() if flow.updated_at else None,
    }


def _branch_to_dict(branch: TriggerBranch) -> dict:
    d = {
        "id": branch.id,
        "flow_id": branch.flow_id,
        "source_playlist_id": branch.source_playlist_id,
        "target_playlist_id": branch.target_playlist_id,
        "trigger_type": branch.trigger_type,
        "trigger_config": json.loads(branch.trigger_config) if branch.trigger_config else {},
        "priority": branch.priority,
        "created_at": branch.created_at.isoformat() if branch.created_at else None,
    }
    if branch.last_webhook_fire:
        d["last_webhook_fire"] = branch.last_webhook_fire.isoformat()
    if branch.source_playlist:
        d["source_playlist_name"] = branch.source_playlist.name
    if branch.target_playlist:
        d["target_playlist_name"] = branch.target_playlist.name
    return d


def _validate_trigger_config(trigger_config: str) -> None:
    try:
        json.loads(trigger_config)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="trigger_config must be valid JSON")


# --- TriggerFlow CRUD ---

@router.get("/trigger-flows")
async def list_flows(
    _token: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(TriggerFlow, func.count(TriggerBranch.id).label("branch_count"))
        .outerjoin(TriggerBranch, TriggerBranch.flow_id == TriggerFlow.id)
        .group_by(TriggerFlow.id)
    )
    rows = result.all()
    return [_flow_summary(flow, count) for flow, count in rows]


@router.post("/trigger-flows", status_code=201)
async def create_flow(
    body: dict,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    flow = TriggerFlow(
        name=name,
        description=body.get("description"),
    )
    session.add(flow)
    await session.flush()
    await audit(session, action="create", entity_type="trigger_flow", entity_id=flow.id,
                details={"name": name}, token=_token, request=request)
    await session.commit()
    await session.refresh(flow)
    return _flow_summary(flow, 0)


@router.get("/trigger-flows/{flow_id}")
async def get_flow(
    flow_id: str,
    _token: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(TriggerFlow)
        .where(TriggerFlow.id == flow_id)
        .options(
            selectinload(TriggerFlow.branches)
            .selectinload(TriggerBranch.source_playlist),
            selectinload(TriggerFlow.branches)
            .selectinload(TriggerBranch.target_playlist),
        )
    )
    flow = result.scalars().first()
    if not flow:
        raise HTTPException(status_code=404, detail="Trigger flow not found")
    return {
        "id": flow.id,
        "name": flow.name,
        "description": flow.description,
        "branches": [_branch_to_dict(b) for b in flow.branches],
        "created_at": flow.created_at.isoformat() if flow.created_at else None,
        "updated_at": flow.updated_at.isoformat() if flow.updated_at else None,
    }


@router.patch("/trigger-flows/{flow_id}")
async def update_flow(
    flow_id: str,
    body: dict,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    flow = await session.get(TriggerFlow, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Trigger flow not found")

    allowed = {"name", "description"}
    for key, value in body.items():
        if key in allowed:
            setattr(flow, key, value)

    await audit(session, action="update", entity_type="trigger_flow", entity_id=flow_id,
                details={"name": flow.name, "changes": {k: v for k, v in body.items() if k in allowed}},
                token=_token, request=request)
    await session.commit()
    await session.refresh(flow)
    return {
        "id": flow.id,
        "name": flow.name,
        "description": flow.description,
        "updated_at": flow.updated_at.isoformat() if flow.updated_at else None,
    }


@router.delete("/trigger-flows/{flow_id}")
async def delete_flow(
    flow_id: str,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    flow = await session.get(TriggerFlow, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Trigger flow not found")

    # Clear trigger_flow_id on any playlists referencing this flow
    result = await session.execute(
        select(Playlist).where(Playlist.trigger_flow_id == flow_id)
    )
    for p in result.scalars().all():
        p.trigger_flow_id = None

    await audit(session, action="delete", entity_type="trigger_flow", entity_id=flow_id,
                details={"name": flow.name}, token=_token, request=request)
    await session.delete(flow)
    await session.commit()
    return {"ok": True}


# --- TriggerBranch CRUD ---

@router.post("/trigger-flows/{flow_id}/branches", status_code=201)
async def add_branch(
    flow_id: str,
    body: dict,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    flow = await session.get(TriggerFlow, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Trigger flow not found")

    source_playlist_id = body.get("source_playlist_id")
    target_playlist_id = body.get("target_playlist_id")
    trigger_type = body.get("trigger_type")

    if not source_playlist_id:
        raise HTTPException(status_code=400, detail="source_playlist_id is required")
    if not target_playlist_id:
        raise HTTPException(status_code=400, detail="target_playlist_id is required")
    if not trigger_type:
        raise HTTPException(status_code=400, detail="trigger_type is required")
    if trigger_type not in VALID_TRIGGER_TYPES:
        raise HTTPException(status_code=400, detail=f"trigger_type must be one of: {', '.join(sorted(VALID_TRIGGER_TYPES))}")

    # Validate playlists exist
    source = await session.get(Playlist, source_playlist_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source playlist not found")
    target = await session.get(Playlist, target_playlist_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target playlist not found")

    trigger_config = body.get("trigger_config", "{}")
    if isinstance(trigger_config, dict):
        trigger_config_dict = trigger_config
    else:
        try:
            trigger_config_dict = json.loads(trigger_config)
        except (json.JSONDecodeError, TypeError):
            trigger_config_dict = {}

    # Auto-generate webhook token if not provided
    if trigger_type == "webhook" and not trigger_config_dict.get("token"):
        trigger_config_dict["token"] = secrets.token_hex(8)

    trigger_config = json.dumps(trigger_config_dict)
    _validate_trigger_config(trigger_config)

    branch = TriggerBranch(
        flow_id=flow_id,
        source_playlist_id=source_playlist_id,
        target_playlist_id=target_playlist_id,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        priority=body.get("priority", 0),
    )
    session.add(branch)
    await session.flush()
    await audit(session, action="create", entity_type="trigger_branch", entity_id=branch.id,
                details={"flow_id": flow_id, "trigger_type": trigger_type,
                          "source": source_playlist_id, "target": target_playlist_id},
                token=_token, request=request)
    await session.commit()

    # Re-fetch with relationships
    result = await session.execute(
        select(TriggerBranch)
        .where(TriggerBranch.id == branch.id)
        .options(
            selectinload(TriggerBranch.source_playlist),
            selectinload(TriggerBranch.target_playlist),
        )
    )
    branch = result.scalars().first()
    return _branch_to_dict(branch)


@router.patch("/trigger-branches/{branch_id}")
async def update_branch(
    branch_id: str,
    body: dict,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(TriggerBranch)
        .where(TriggerBranch.id == branch_id)
        .options(
            selectinload(TriggerBranch.source_playlist),
            selectinload(TriggerBranch.target_playlist),
        )
    )
    branch = result.scalars().first()
    if not branch:
        raise HTTPException(status_code=404, detail="Trigger branch not found")

    if "trigger_type" in body:
        if body["trigger_type"] not in VALID_TRIGGER_TYPES:
            raise HTTPException(status_code=400, detail=f"trigger_type must be one of: {', '.join(sorted(VALID_TRIGGER_TYPES))}")
        branch.trigger_type = body["trigger_type"]

    if "trigger_config" in body:
        tc = body["trigger_config"]
        if isinstance(tc, dict):
            tc = json.dumps(tc)
        _validate_trigger_config(tc)
        branch.trigger_config = tc

    if "source_playlist_id" in body:
        source = await session.get(Playlist, body["source_playlist_id"])
        if not source:
            raise HTTPException(status_code=404, detail="Source playlist not found")
        branch.source_playlist_id = body["source_playlist_id"]

    if "target_playlist_id" in body:
        target = await session.get(Playlist, body["target_playlist_id"])
        if not target:
            raise HTTPException(status_code=404, detail="Target playlist not found")
        branch.target_playlist_id = body["target_playlist_id"]

    if "priority" in body:
        branch.priority = body["priority"]

    await audit(session, action="update", entity_type="trigger_branch", entity_id=branch_id,
                details={"flow_id": branch.flow_id, "changes": body},
                token=_token, request=request)
    await session.commit()

    # Re-fetch with relationships
    result = await session.execute(
        select(TriggerBranch)
        .where(TriggerBranch.id == branch_id)
        .options(
            selectinload(TriggerBranch.source_playlist),
            selectinload(TriggerBranch.target_playlist),
        )
    )
    branch = result.scalars().first()
    return _branch_to_dict(branch)


@router.delete("/trigger-branches/{branch_id}")
async def delete_branch(
    branch_id: str,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    branch = await session.get(TriggerBranch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Trigger branch not found")

    await audit(session, action="delete", entity_type="trigger_branch", entity_id=branch_id,
                details={"flow_id": branch.flow_id, "trigger_type": branch.trigger_type},
                token=_token, request=request)
    await session.delete(branch)
    await session.commit()
    return {"ok": True}


# --- Webhook trigger (public, token-validated) ---

@router.post("/triggers/webhook/{branch_id}")
async def fire_webhook(
    branch_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    branch = await session.get(TriggerBranch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Trigger branch not found")

    if branch.trigger_type != "webhook":
        raise HTTPException(status_code=400, detail="Branch is not a webhook trigger")

    # Validate token
    try:
        config = json.loads(branch.trigger_config) if branch.trigger_config else {}
    except (json.JSONDecodeError, TypeError):
        config = {}

    expected_token = str(config.get("token", ""))
    provided_token = str(body.get("token", ""))
    if not expected_token or not provided_token or not secrets.compare_digest(provided_token, expected_token):
        raise HTTPException(status_code=403, detail="Invalid webhook token")

    branch.last_webhook_fire = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.commit()
    return {"status": "triggered"}
