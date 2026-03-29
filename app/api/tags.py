import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

from app.audit import record as audit
from app.auth import require_editor, require_viewer
from app.database import get_session
from app.models import ApiToken, Asset, AssetTag, Tag

router = APIRouter()


@router.get("/tags")
async def list_tags(
    _token: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Tag).order_by(Tag.name))
    tags = result.scalars().all()

    # Get asset counts per tag
    count_q = (
        select(AssetTag.tag_id, func.count(AssetTag.asset_id).label("cnt"))
        .group_by(AssetTag.tag_id)
    )
    count_result = await session.execute(count_q)
    counts = {row.tag_id: row.cnt for row in count_result}

    return [
        {
            "id": t.id,
            "name": t.name,
            "color": t.color,
            "asset_count": counts.get(t.id, 0),
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tags
    ]


@router.post("/tags", status_code=201)
async def create_tag(
    body: dict,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tag name is required")
    if len(name) > 100:
        raise HTTPException(status_code=400, detail="Tag name too long (max 100)")

    # Check uniqueness
    existing = await session.execute(select(Tag).where(Tag.name == name))
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Tag name already exists")

    color = body.get("color", "#7c83ff")
    if not _COLOR_RE.match(color):
        raise HTTPException(status_code=400, detail="Color must be a hex color like #7c83ff")
    tag = Tag(name=name, color=color)
    session.add(tag)

    await audit(session, action="create", entity_type="tag", entity_id=tag.id,
                details={"name": name, "color": color},
                token=_token, request=request)
    await session.commit()
    await session.refresh(tag)
    return {"id": tag.id, "name": tag.name, "color": tag.color,
            "asset_count": 0, "created_at": tag.created_at.isoformat()}


@router.patch("/tags/{tag_id}")
async def update_tag(
    tag_id: str,
    body: dict,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    tag = await session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    changes = {}
    if "name" in body:
        name = body["name"].strip()
        if not name:
            raise HTTPException(status_code=400, detail="Tag name is required")
        # Check uniqueness against other tags
        existing = await session.execute(
            select(Tag).where(Tag.name == name, Tag.id != tag_id)
        )
        if existing.scalars().first():
            raise HTTPException(status_code=409, detail="Tag name already exists")
        tag.name = name
        changes["name"] = name
    if "color" in body:
        if not _COLOR_RE.match(body["color"]):
            raise HTTPException(status_code=400, detail="Color must be a hex color like #7c83ff")
        tag.color = body["color"]
        changes["color"] = body["color"]

    await audit(session, action="update", entity_type="tag", entity_id=tag_id,
                details=changes, token=_token, request=request)
    await session.commit()
    await session.refresh(tag)
    return {"id": tag.id, "name": tag.name, "color": tag.color,
            "created_at": tag.created_at.isoformat()}


@router.delete("/tags/{tag_id}")
async def delete_tag(
    tag_id: str,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    tag = await session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    tag_name = tag.name
    await audit(session, action="delete", entity_type="tag", entity_id=tag_id,
                details={"name": tag_name}, token=_token, request=request)
    await session.delete(tag)
    await session.commit()
    return {"ok": True}


@router.post("/assets/{asset_id}/tags")
async def add_tag_to_asset(
    asset_id: str,
    body: dict,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    tag_id = body.get("tag_id")
    if not tag_id:
        raise HTTPException(status_code=400, detail="tag_id is required")

    asset = await session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    tag = await session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Check if already tagged
    existing = await session.execute(
        select(AssetTag).where(AssetTag.asset_id == asset_id, AssetTag.tag_id == tag_id)
    )
    if existing.scalars().first():
        return {"ok": True}  # Idempotent

    at = AssetTag(asset_id=asset_id, tag_id=tag_id)
    session.add(at)
    await audit(session, action="tag", entity_type="asset", entity_id=asset_id,
                details={"tag_id": tag_id, "tag_name": tag.name},
                token=_token, request=request)
    await session.commit()
    return {"ok": True}


@router.delete("/assets/{asset_id}/tags/{tag_id}")
async def remove_tag_from_asset(
    asset_id: str,
    tag_id: str,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AssetTag).where(AssetTag.asset_id == asset_id, AssetTag.tag_id == tag_id)
    )
    at = result.scalars().first()
    if not at:
        raise HTTPException(status_code=404, detail="Tag not assigned to this asset")

    tag = await session.get(Tag, tag_id)
    await audit(session, action="untag", entity_type="asset", entity_id=asset_id,
                details={"tag_id": tag_id, "tag_name": tag.name if tag else None},
                token=_token, request=request)
    await session.delete(at)
    await session.commit()
    return {"ok": True}


@router.get("/assets/{asset_id}/tags")
async def get_asset_tags(
    asset_id: str,
    _token: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    asset = await session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    result = await session.execute(
        select(Tag).join(AssetTag).where(AssetTag.asset_id == asset_id).order_by(Tag.name)
    )
    tags = result.scalars().all()
    return [{"id": t.id, "name": t.name, "color": t.color} for t in tags]
