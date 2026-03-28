import uuid
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_session
from app.media import compute_content_hash, generate_thumbnail
from app.models import ApiToken, Asset, Playlist, PlaylistItem

_config = yaml.safe_load(Path("config.yaml").read_text())
_media_dir = Path(_config["storage"]["media_dir"])
_thumbs_dir = _media_dir / "thumbs"

router = APIRouter()


@router.get("/assets")
async def list_assets(
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Asset).order_by(Asset.play_order))
    assets = result.scalars().all()
    return [_asset_to_dict(a) for a in assets]


@router.post("/assets", status_code=201)
async def create_asset(
    file: UploadFile | None = File(None),
    name: str = Form(None),
    asset_type: str = Form(None),
    url: str = Form(None),
    duration: int = Form(None),
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    # Determine next play_order
    result = await session.execute(select(func.max(Asset.play_order)))
    max_order = result.scalar()
    next_order = (max_order or 0) + 1

    if file and file.filename:
        # File upload — streaming write for large video files
        mimetype = file.content_type or ""
        if not mimetype.startswith("image/") and not mimetype.startswith("video/"):
            raise HTTPException(status_code=400, detail="Unsupported file type")

        suffix = Path(file.filename).suffix
        filename = f"{uuid.uuid4()}{suffix}"
        filepath = _media_dir / filename

        file_size = 0
        try:
            with open(filepath, "wb") as f:
                while chunk := await file.read(1024 * 1024):  # 1MB chunks
                    f.write(chunk)
                    file_size += len(chunk)
        except Exception:
            filepath.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail="File upload failed")

        if not asset_type:
            if mimetype.startswith("image/"):
                asset_type = "image"
            elif mimetype.startswith("video/"):
                asset_type = "video"

        default_dur = 0 if asset_type == "video" else 10
        asset_id = str(uuid.uuid4())
        asset = Asset(
            id=asset_id,
            name=name or file.filename,
            asset_type=asset_type,
            uri=filename,
            duration=duration if duration is not None else default_dur,
            play_order=next_order,
            mimetype=mimetype,
            file_size=file_size,
        )

        # Generate content hash and thumbnail
        asset.content_hash = compute_content_hash(filepath)
        thumb = generate_thumbnail(filepath, _thumbs_dir, asset_type, asset.id)
        if thumb:
            asset.thumbnail_path = thumb

    elif url:
        # URL asset
        asset = Asset(
            name=name or url,
            asset_type="url",
            uri=url,
            duration=duration or 10,
            play_order=next_order,
        )
    else:
        raise HTTPException(status_code=400, detail="Provide a file or url")

    session.add(asset)
    await session.flush()

    # Also add to default playlist
    result = await session.execute(
        select(Playlist).where(Playlist.is_default == True)
    )
    default_playlist = result.scalars().first()
    if default_playlist:
        item = PlaylistItem(
            playlist_id=default_playlist.id,
            asset_id=asset.id,
            order=next_order,
        )
        session.add(item)

    await session.commit()
    await session.refresh(asset)
    return _asset_to_dict(asset)


@router.get("/assets/{asset_id}")
async def get_asset(
    asset_id: str,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    asset = await session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _asset_to_dict(asset)


@router.get("/assets/{asset_id}/thumbnail")
async def get_asset_thumbnail(
    asset_id: str,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    asset = await session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not asset.thumbnail_path:
        raise HTTPException(status_code=404, detail="No thumbnail available")

    thumb_path = _thumbs_dir / asset.thumbnail_path
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file missing")

    return FileResponse(thumb_path, media_type="image/jpeg")


@router.patch("/assets/{asset_id}")
async def update_asset(
    asset_id: str,
    body: dict,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    asset = await session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    allowed = {"name", "duration", "is_enabled", "start_date", "end_date", "play_order"}
    for key, value in body.items():
        if key in allowed:
            setattr(asset, key, value)

    await session.commit()
    await session.refresh(asset)
    return _asset_to_dict(asset)


@router.put("/assets/{asset_id}/replace")
async def replace_asset(
    asset_id: str,
    file: UploadFile = File(...),
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Replace the file for an existing asset. Keeps metadata, playlist slot, and order."""
    asset = await session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.asset_type == "url":
        raise HTTPException(status_code=400, detail="Cannot replace a URL asset file")

    mimetype = file.content_type or ""
    if not mimetype.startswith("image/") and not mimetype.startswith("video/"):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    # Delete old file
    old_path = _media_dir / asset.uri
    old_path.unlink(missing_ok=True)

    # Write new file
    suffix = Path(file.filename).suffix
    filename = f"{uuid.uuid4()}{suffix}"
    filepath = _media_dir / filename

    file_size = 0
    try:
        with open(filepath, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                f.write(chunk)
                file_size += len(chunk)
    except Exception:
        filepath.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="File upload failed")

    # Update asset
    asset.uri = filename
    asset.mimetype = mimetype
    asset.file_size = file_size
    asset.content_hash = compute_content_hash(filepath)

    # Regenerate thumbnail
    thumb = generate_thumbnail(filepath, _thumbs_dir, asset.asset_type, asset.id)
    asset.thumbnail_path = thumb  # None if generation failed

    await session.commit()
    await session.refresh(asset)
    return _asset_to_dict(asset)


@router.post("/assets/{asset_id}/duplicate", status_code=201)
async def duplicate_asset(
    asset_id: str,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Duplicate an asset. Copies the file, creates a new asset and playlist item."""
    asset = await session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Determine next play_order
    result = await session.execute(select(func.max(Asset.play_order)))
    max_order = result.scalar()
    next_order = (max_order or 0) + 1

    new_asset_id = str(uuid.uuid4())
    new_asset = Asset(
        id=new_asset_id,
        name=f"{asset.name} (copy)",
        asset_type=asset.asset_type,
        duration=asset.duration,
        play_order=next_order,
        is_enabled=asset.is_enabled,
        mimetype=asset.mimetype,
    )

    if asset.asset_type == "url":
        new_asset.uri = asset.uri
    else:
        # Copy the media file
        src_path = _media_dir / asset.uri
        if src_path.exists():
            suffix = src_path.suffix
            new_filename = f"{uuid.uuid4()}{suffix}"
            dst_path = _media_dir / new_filename
            import shutil
            shutil.copy2(src_path, dst_path)
            new_asset.uri = new_filename
            new_asset.file_size = dst_path.stat().st_size
            new_asset.content_hash = compute_content_hash(dst_path)

            # Generate thumbnail for the copy
            thumb = generate_thumbnail(dst_path, _thumbs_dir, asset.asset_type, new_asset.id)
            if thumb:
                new_asset.thumbnail_path = thumb
        else:
            new_asset.uri = asset.uri

    session.add(new_asset)
    await session.flush()

    # Add to default playlist
    result = await session.execute(
        select(Playlist).where(Playlist.is_default == True)
    )
    default_playlist = result.scalars().first()
    if default_playlist:
        item = PlaylistItem(
            playlist_id=default_playlist.id,
            asset_id=new_asset.id,
            order=next_order,
        )
        session.add(item)

    await session.commit()
    await session.refresh(new_asset)
    return _asset_to_dict(new_asset)


@router.delete("/assets/{asset_id}")
async def delete_asset(
    asset_id: str,
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    asset = await session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Delete file if not a URL asset
    if asset.asset_type != "url":
        filepath = _media_dir / asset.uri
        filepath.unlink(missing_ok=True)
        # Delete thumbnail
        if asset.thumbnail_path:
            thumb_path = _thumbs_dir / asset.thumbnail_path
            thumb_path.unlink(missing_ok=True)

    await session.delete(asset)
    await session.commit()
    return {"ok": True}


@router.post("/assets/reorder")
async def reorder_assets(
    items: list[dict],
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    for item in items:
        asset = await session.get(Asset, item["id"])
        if asset:
            asset.play_order = item["play_order"]
            # Also update matching PlaylistItems in default playlist
            result = await session.execute(
                select(PlaylistItem).where(PlaylistItem.asset_id == asset.id)
            )
            for pi in result.scalars().all():
                pi.order = item["play_order"]
    await session.commit()
    return {"ok": True}


def _asset_to_dict(asset: Asset) -> dict:
    return {
        "id": asset.id,
        "name": asset.name,
        "asset_type": asset.asset_type,
        "uri": asset.uri,
        "duration": asset.duration,
        "play_order": asset.play_order,
        "is_enabled": asset.is_enabled,
        "start_date": asset.start_date.isoformat() if asset.start_date else None,
        "end_date": asset.end_date.isoformat() if asset.end_date else None,
        "mimetype": asset.mimetype,
        "file_size": asset.file_size,
        "thumbnail_path": asset.thumbnail_path,
        "content_hash": asset.content_hash,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
    }
