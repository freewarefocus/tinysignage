import hashlib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_editor, require_token, require_viewer
from app.database import get_session
from app.models import ApiToken, Asset, Device, Playlist, PlaylistItem, Schedule

router = APIRouter()


def _playlist_hash(items: list[PlaylistItem]) -> str:
    """Compute a hash representing the current playlist state."""
    parts = []
    for item in sorted(items, key=lambda i: i.order):
        asset = item.asset
        content = asset.content_hash or asset.id
        parts.append(f"{item.order}:{asset.id}:{content}:{asset.duration}:{asset.is_enabled}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _item_to_dict(item: PlaylistItem) -> dict:
    asset = item.asset
    return {
        "id": item.id,
        "playlist_id": item.playlist_id,
        "asset_id": item.asset_id,
        "order": item.order,
        "asset": {
            "id": asset.id,
            "name": asset.name,
            "asset_type": asset.asset_type,
            "uri": asset.uri,
            "duration": asset.duration,
            "is_enabled": asset.is_enabled,
            "start_date": asset.start_date.isoformat() if asset.start_date else None,
            "end_date": asset.end_date.isoformat() if asset.end_date else None,
            "mimetype": asset.mimetype,
            "thumbnail_path": asset.thumbnail_path,
            "content_hash": asset.content_hash,
        } if asset else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("/playlists")
async def list_playlists(
    _admin: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Playlist).options(
            selectinload(Playlist.items).selectinload(PlaylistItem.asset)
        )
    )
    playlists = result.scalars().all()
    return [_playlist_summary(p) for p in playlists]


def _playlist_summary(p: Playlist) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "is_default": p.is_default,
        "item_count": len(p.items),
        "hash": _playlist_hash(p.items),
        "transition_type": p.transition_type,
        "transition_duration": p.transition_duration,
        "default_duration": p.default_duration,
        "shuffle": p.shuffle,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.post("/playlists", status_code=201)
async def create_playlist(
    body: dict,
    _admin: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    playlist = Playlist(name=name)
    session.add(playlist)
    await session.commit()
    await session.refresh(playlist)
    return {
        "id": playlist.id,
        "name": playlist.name,
        "is_default": playlist.is_default,
        "item_count": 0,
        "created_at": playlist.created_at.isoformat() if playlist.created_at else None,
        "updated_at": playlist.updated_at.isoformat() if playlist.updated_at else None,
    }


@router.get("/playlists/{playlist_id}")
async def get_playlist(
    playlist_id: str,
    _admin: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Playlist)
        .where(Playlist.id == playlist_id)
        .options(
            selectinload(Playlist.items).selectinload(PlaylistItem.asset)
        )
    )
    playlist = result.scalars().first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return {
        "id": playlist.id,
        "name": playlist.name,
        "is_default": playlist.is_default,
        "hash": _playlist_hash(playlist.items),
        "items": [_item_to_dict(item) for item in playlist.items],
        "transition_type": playlist.transition_type,
        "transition_duration": playlist.transition_duration,
        "default_duration": playlist.default_duration,
        "shuffle": playlist.shuffle,
        "created_at": playlist.created_at.isoformat() if playlist.created_at else None,
        "updated_at": playlist.updated_at.isoformat() if playlist.updated_at else None,
    }


@router.patch("/playlists/{playlist_id}")
async def update_playlist(
    playlist_id: str,
    body: dict,
    _admin: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    playlist = await session.get(Playlist, playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    allowed = {"name", "transition_type", "transition_duration", "default_duration", "shuffle"}
    for key, value in body.items():
        if key in allowed:
            setattr(playlist, key, value)
    await session.commit()
    await session.refresh(playlist)
    return {
        "id": playlist.id,
        "name": playlist.name,
        "is_default": playlist.is_default,
        "transition_type": playlist.transition_type,
        "transition_duration": playlist.transition_duration,
        "default_duration": playlist.default_duration,
        "shuffle": playlist.shuffle,
    }


@router.delete("/playlists/{playlist_id}")
async def delete_playlist(
    playlist_id: str,
    _admin: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    playlist = await session.get(Playlist, playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    if playlist.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete the default playlist")

    # Bug #1: Check if any schedules reference this playlist
    result = await session.execute(
        select(Schedule).where(Schedule.playlist_id == playlist_id)
    )
    referencing_schedules = result.scalars().all()
    if referencing_schedules:
        names = ", ".join(s.name for s in referencing_schedules)
        raise HTTPException(
            status_code=409,
            detail=f"Playlist is used by schedule(s): {names}",
        )

    # Bug #2: Check if any devices are assigned this playlist
    result = await session.execute(
        select(Device).where(Device.playlist_id == playlist_id)
    )
    referencing_devices = result.scalars().all()
    if referencing_devices:
        names = ", ".join(d.name for d in referencing_devices)
        raise HTTPException(
            status_code=409,
            detail=f"Playlist is assigned to device(s): {names}",
        )

    await session.delete(playlist)
    await session.commit()
    return {"ok": True}


@router.get("/playlists/{playlist_id}/hash")
async def get_playlist_hash(
    playlist_id: str,
    _token: ApiToken = Depends(require_token),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Playlist)
        .where(Playlist.id == playlist_id)
        .options(
            selectinload(Playlist.items).selectinload(PlaylistItem.asset)
        )
    )
    playlist = result.scalars().first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return {"hash": _playlist_hash(playlist.items)}


@router.post("/playlists/{playlist_id}/items", status_code=201)
async def add_item_to_playlist(
    playlist_id: str,
    body: dict,
    _admin: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    playlist = await session.get(Playlist, playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    asset_id = body.get("asset_id")
    if not asset_id:
        raise HTTPException(status_code=400, detail="asset_id is required")

    asset = await session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Determine order: append to end by default
    result = await session.execute(
        select(PlaylistItem)
        .where(PlaylistItem.playlist_id == playlist_id)
        .order_by(PlaylistItem.order.desc())
    )
    last_item = result.scalars().first()
    order = body.get("order", (last_item.order + 1) if last_item else 0)

    item = PlaylistItem(playlist_id=playlist_id, asset_id=asset_id, order=order)
    session.add(item)
    await session.commit()

    # Re-fetch with asset loaded
    result = await session.execute(
        select(PlaylistItem)
        .where(PlaylistItem.id == item.id)
        .options(selectinload(PlaylistItem.asset))
    )
    item = result.scalars().first()
    return _item_to_dict(item)


@router.delete("/playlists/{playlist_id}/items/{item_id}")
async def remove_item_from_playlist(
    playlist_id: str,
    item_id: str,
    _admin: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PlaylistItem).where(
            PlaylistItem.id == item_id,
            PlaylistItem.playlist_id == playlist_id,
        )
    )
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Playlist item not found")
    await session.delete(item)
    await session.commit()
    return {"ok": True}


@router.post("/playlists/{playlist_id}/reorder")
async def reorder_playlist_items(
    playlist_id: str,
    body: dict,
    _admin: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    """Reorder items. Body: {"item_ids": ["id1", "id2", ...]} in desired order."""
    item_ids = body.get("item_ids", [])
    for order, item_id in enumerate(item_ids):
        result = await session.execute(
            select(PlaylistItem).where(
                PlaylistItem.id == item_id,
                PlaylistItem.playlist_id == playlist_id,
            )
        )
        item = result.scalars().first()
        if item:
            item.order = order
    await session.commit()
    return {"ok": True}
