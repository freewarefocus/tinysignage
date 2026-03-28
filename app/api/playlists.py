import hashlib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import Asset, Playlist, PlaylistItem

router = APIRouter()


def _playlist_hash(items: list[PlaylistItem]) -> str:
    """Compute a hash representing the current playlist state."""
    parts = []
    for item in sorted(items, key=lambda i: i.order):
        asset = item.asset
        content = asset.content_hash or asset.id
        parts.append(f"{item.order}:{asset.id}:{content}")
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
async def list_playlists(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Playlist).options(
            selectinload(Playlist.items).selectinload(PlaylistItem.asset)
        )
    )
    playlists = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "is_default": p.is_default,
            "item_count": len(p.items),
            "hash": _playlist_hash(p.items),
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in playlists
    ]


@router.post("/playlists", status_code=201)
async def create_playlist(body: dict, session: AsyncSession = Depends(get_session)):
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
async def get_playlist(playlist_id: str, session: AsyncSession = Depends(get_session)):
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
        "created_at": playlist.created_at.isoformat() if playlist.created_at else None,
        "updated_at": playlist.updated_at.isoformat() if playlist.updated_at else None,
    }


@router.patch("/playlists/{playlist_id}")
async def update_playlist(
    playlist_id: str, body: dict, session: AsyncSession = Depends(get_session)
):
    playlist = await session.get(Playlist, playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    if "name" in body:
        playlist.name = body["name"]
    await session.commit()
    await session.refresh(playlist)
    return {"id": playlist.id, "name": playlist.name, "is_default": playlist.is_default}


@router.delete("/playlists/{playlist_id}")
async def delete_playlist(playlist_id: str, session: AsyncSession = Depends(get_session)):
    playlist = await session.get(Playlist, playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    if playlist.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete the default playlist")
    await session.delete(playlist)
    await session.commit()
    return {"ok": True}


@router.get("/playlists/{playlist_id}/hash")
async def get_playlist_hash(playlist_id: str, session: AsyncSession = Depends(get_session)):
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
    playlist_id: str, body: dict, session: AsyncSession = Depends(get_session)
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
    playlist_id: str, item_id: str, session: AsyncSession = Depends(get_session)
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
    playlist_id: str, body: dict, session: AsyncSession = Depends(get_session)
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
