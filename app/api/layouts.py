from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit import record as audit
from app.auth import require_editor, require_viewer
from app.database import get_session
from app.models import ApiToken, Layout, LayoutZone, Playlist

router = APIRouter()

VALID_ZONE_TYPES = {"main", "ticker", "sidebar", "pip"}


def _layout_to_dict(layout: Layout) -> dict:
    return {
        "id": layout.id,
        "name": layout.name,
        "description": layout.description,
        "zone_count": len(layout.zones) if layout.zones else 0,
        "zones": [_zone_to_dict(z) for z in layout.zones] if layout.zones else [],
        "created_at": layout.created_at.isoformat() if layout.created_at else None,
        "updated_at": layout.updated_at.isoformat() if layout.updated_at else None,
    }


def _zone_to_dict(zone: LayoutZone) -> dict:
    return {
        "id": zone.id,
        "layout_id": zone.layout_id,
        "name": zone.name,
        "zone_type": zone.zone_type,
        "x_percent": zone.x_percent,
        "y_percent": zone.y_percent,
        "width_percent": zone.width_percent,
        "height_percent": zone.height_percent,
        "z_index": zone.z_index,
        "playlist_id": zone.playlist_id,
        "created_at": zone.created_at.isoformat() if zone.created_at else None,
    }


# --- Layout CRUD ---

@router.get("/layouts")
async def list_layouts(
    _token: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Layout).options(selectinload(Layout.zones))
    )
    layouts = result.scalars().all()
    return [_layout_to_dict(l) for l in layouts]


@router.post("/layouts", status_code=201)
async def create_layout(
    body: dict,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    layout = Layout(
        name=name,
        description=body.get("description"),
    )
    session.add(layout)
    await session.flush()
    await audit(session, action="create", entity_type="layout", entity_id=layout.id,
                details={"name": name}, token=_token, request=request)
    await session.commit()

    # Re-fetch with zones loaded
    result = await session.execute(
        select(Layout).where(Layout.id == layout.id).options(selectinload(Layout.zones))
    )
    layout = result.scalars().first()
    return _layout_to_dict(layout)


@router.get("/layouts/{layout_id}")
async def get_layout(
    layout_id: str,
    _token: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Layout).where(Layout.id == layout_id).options(selectinload(Layout.zones))
    )
    layout = result.scalars().first()
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")
    return _layout_to_dict(layout)


@router.patch("/layouts/{layout_id}")
async def update_layout(
    layout_id: str,
    body: dict,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    layout = await session.get(Layout, layout_id)
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")

    allowed = {"name", "description"}
    for key, value in body.items():
        if key in allowed:
            setattr(layout, key, value)

    await audit(session, action="update", entity_type="layout", entity_id=layout_id,
                details={"name": layout.name, "changes": {k: v for k, v in body.items() if k in allowed}},
                token=_token, request=request)
    await session.commit()

    # Re-fetch with zones
    result = await session.execute(
        select(Layout).where(Layout.id == layout_id).options(selectinload(Layout.zones))
    )
    layout = result.scalars().first()
    return _layout_to_dict(layout)


@router.delete("/layouts/{layout_id}")
async def delete_layout(
    layout_id: str,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Layout).where(Layout.id == layout_id).options(selectinload(Layout.zones))
    )
    layout = result.scalars().first()
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")

    await audit(session, action="delete", entity_type="layout", entity_id=layout_id,
                details={"name": layout.name}, token=_token, request=request)
    await session.delete(layout)
    await session.commit()
    return {"ok": True}


# --- Zone CRUD ---

@router.get("/layouts/{layout_id}/zones")
async def list_zones(
    layout_id: str,
    _token: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    layout = await session.get(Layout, layout_id)
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")

    result = await session.execute(
        select(LayoutZone).where(LayoutZone.layout_id == layout_id)
    )
    zones = result.scalars().all()
    return [_zone_to_dict(z) for z in zones]


@router.post("/layouts/{layout_id}/zones", status_code=201)
async def create_zone(
    layout_id: str,
    body: dict,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    layout = await session.get(Layout, layout_id)
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")

    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    zone_type = body.get("zone_type", "main")
    if zone_type not in VALID_ZONE_TYPES:
        raise HTTPException(status_code=400, detail=f"zone_type must be one of: {', '.join(VALID_ZONE_TYPES)}")

    playlist_id = body.get("playlist_id")
    if playlist_id:
        playlist = await session.get(Playlist, playlist_id)
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

    zone = LayoutZone(
        layout_id=layout_id,
        name=name,
        zone_type=zone_type,
        x_percent=body.get("x_percent", 0.0),
        y_percent=body.get("y_percent", 0.0),
        width_percent=body.get("width_percent", 100.0),
        height_percent=body.get("height_percent", 100.0),
        z_index=body.get("z_index", 0),
        playlist_id=playlist_id,
    )
    session.add(zone)
    await session.flush()
    await audit(session, action="create", entity_type="layout_zone", entity_id=zone.id,
                details={"layout_id": layout_id, "name": name, "zone_type": zone_type},
                token=_token, request=request)
    await session.commit()
    await session.refresh(zone)
    return _zone_to_dict(zone)


@router.patch("/layouts/{layout_id}/zones/{zone_id}")
async def update_zone(
    layout_id: str,
    zone_id: str,
    body: dict,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(LayoutZone).where(
            LayoutZone.id == zone_id,
            LayoutZone.layout_id == layout_id,
        )
    )
    zone = result.scalars().first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    allowed = {"name", "zone_type", "x_percent", "y_percent", "width_percent",
               "height_percent", "z_index", "playlist_id"}
    for key, value in body.items():
        if key in allowed:
            if key == "zone_type" and value not in VALID_ZONE_TYPES:
                raise HTTPException(status_code=400, detail=f"zone_type must be one of: {', '.join(VALID_ZONE_TYPES)}")
            if key == "playlist_id" and value:
                playlist = await session.get(Playlist, value)
                if not playlist:
                    raise HTTPException(status_code=404, detail="Playlist not found")
            setattr(zone, key, value)

    await audit(session, action="update", entity_type="layout_zone", entity_id=zone_id,
                details={"layout_id": layout_id, "changes": {k: v for k, v in body.items() if k in allowed}},
                token=_token, request=request)
    await session.commit()
    await session.refresh(zone)
    return _zone_to_dict(zone)


@router.delete("/layouts/{layout_id}/zones/{zone_id}")
async def delete_zone(
    layout_id: str,
    zone_id: str,
    request: Request,
    _token: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(LayoutZone).where(
            LayoutZone.id == zone_id,
            LayoutZone.layout_id == layout_id,
        )
    )
    zone = result.scalars().first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    await audit(session, action="delete", entity_type="layout_zone", entity_id=zone_id,
                details={"layout_id": layout_id, "name": zone.name},
                token=_token, request=request)
    await session.delete(zone)
    await session.commit()
    return {"ok": True}
