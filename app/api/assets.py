import hashlib
import uuid
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record as audit
from app.auth import require_editor, require_viewer
from app.database import get_session
from app.media import compute_content_hash, generate_thumbnail
from app.models import ApiToken, Asset, AssetTag, Playlist, PlaylistItem, Tag

MAX_HTML_SIZE = 65536  # 64 KB

# Map MIME types to safe file extensions — prevents storing files with
# a spoofed extension (e.g. Content-Type image/png + filename evil.html).
_MIME_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/svg+xml": ".svg",
    "image/tiff": ".tiff",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/ogg": ".ogv",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/x-matroska": ".mkv",
}

_config = yaml.safe_load(Path("config.yaml").read_text())
_media_dir = Path(_config["storage"]["media_dir"])
_thumbs_dir = _media_dir / "thumbs"

router = APIRouter()


@router.get("/assets")
async def list_assets(
    tag: str | None = None,
    _admin: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    query = select(Asset).order_by(Asset.play_order)
    if tag:
        query = query.join(AssetTag).where(AssetTag.tag_id == tag)
    result = await session.execute(query)
    assets = result.scalars().all()

    # Batch-load tags for all assets
    asset_ids = [a.id for a in assets]
    tag_map: dict[str, list[dict]] = {aid: [] for aid in asset_ids}
    if asset_ids:
        tag_q = (
            select(AssetTag.asset_id, Tag.id, Tag.name, Tag.color)
            .join(Tag)
            .where(AssetTag.asset_id.in_(asset_ids))
            .order_by(Tag.name)
        )
        tag_result = await session.execute(tag_q)
        for row in tag_result:
            tag_map[row.asset_id].append(
                {"id": row.id, "name": row.name, "color": row.color}
            )

    return [_asset_to_dict(a, tags=tag_map.get(a.id, [])) for a in assets]


@router.post("/assets", status_code=201)
async def create_asset(
    request: Request,
    file: UploadFile | None = File(None),
    name: str = Form(None),
    asset_type: str = Form(None),
    url: str = Form(None),
    content: str = Form(None),
    duration: int = Form(None),
    _admin: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    # Determine next play_order
    result = await session.execute(select(func.max(Asset.play_order)))
    max_order = result.scalar()
    next_order = (max_order or 0) + 1

    if asset_type == "html" and content is not None:
        # HTML snippet asset
        if len(content.encode("utf-8")) > MAX_HTML_SIZE:
            raise HTTPException(status_code=400, detail="HTML content exceeds 64 KB limit")

        asset_id = str(uuid.uuid4())
        filename = f"{asset_id}.html"
        filepath = _media_dir / filename
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        filepath.write_text(content, encoding="utf-8")

        file_size = filepath.stat().st_size
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        asset = Asset(
            id=asset_id,
            name=name or "Custom Slide",
            asset_type="html",
            uri=filename,
            duration=duration if duration is not None else 10,
            play_order=next_order,
            mimetype="text/html",
            file_size=file_size,
            content_hash=content_hash,
        )

    elif file and file.filename:
        # File upload — streaming write for large video files
        mimetype = file.content_type or ""
        if not mimetype.startswith("image/") and not mimetype.startswith("video/"):
            raise HTTPException(status_code=400, detail="Unsupported file type")

        suffix = _MIME_TO_EXT.get(mimetype, Path(file.filename).suffix)
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
        raise HTTPException(status_code=400, detail="Provide a file, url, or html content")

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

    await audit(session, action="create", entity_type="asset", entity_id=asset.id,
                details={"name": asset.name, "type": asset.asset_type},
                token=_admin, request=request)
    await session.commit()
    await session.refresh(asset)
    return _asset_to_dict(asset)


@router.get("/assets/{asset_id}")
async def get_asset(
    asset_id: str,
    _admin: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    asset = await session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _asset_to_dict(asset)


@router.get("/assets/{asset_id}/thumbnail")
async def get_asset_thumbnail(
    asset_id: str,
    _admin: ApiToken = Depends(require_viewer),
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
    request: Request,
    _admin: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    asset = await session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Handle HTML content update
    if "content" in body and asset.asset_type == "html":
        html_content = body["content"]
        if len(html_content.encode("utf-8")) > MAX_HTML_SIZE:
            raise HTTPException(status_code=400, detail="HTML content exceeds 64 KB limit")
        filepath = _media_dir / asset.uri
        html_content = html_content.replace('\r\n', '\n').replace('\r', '\n')
        filepath.write_text(html_content, encoding="utf-8")
        asset.file_size = filepath.stat().st_size
        asset.content_hash = hashlib.sha256(html_content.encode("utf-8")).hexdigest()

    allowed = {"name", "duration", "is_enabled", "start_date", "end_date", "play_order",
                "transition_type", "transition_duration"}
    # Normalize nullable transition fields: empty string or None clears the override
    for field in ("transition_type", "transition_duration"):
        if field in body and (body[field] is None or body[field] == ""):
            body[field] = None

    # Parse date strings into datetime objects for DateTime columns
    for field in ("start_date", "end_date"):
        if field in body:
            val = body[field]
            if val is None or val == "":
                body[field] = None
            elif isinstance(val, str):
                try:
                    body[field] = datetime.fromisoformat(val)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid date format for {field}")

    changes = {}
    for key, value in body.items():
        if key in allowed:
            setattr(asset, key, value)
            changes[key] = str(value) if isinstance(value, datetime) else value
    if "content" in body and asset.asset_type == "html":
        changes["content"] = "(updated)"

    await audit(session, action="update", entity_type="asset", entity_id=asset_id,
                details={"name": asset.name, "changes": changes},
                token=_admin, request=request)
    await session.commit()
    await session.refresh(asset)
    return _asset_to_dict(asset)


@router.get("/assets/{asset_id}/content")
async def get_asset_content(
    asset_id: str,
    _admin: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    """Return the raw HTML content for an HTML asset."""
    asset = await session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.asset_type != "html":
        raise HTTPException(status_code=400, detail="Not an HTML asset")

    filepath = _media_dir / asset.uri
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="HTML file missing")

    return HTMLResponse(content=filepath.read_text(encoding="utf-8"))


@router.put("/assets/{asset_id}/replace")
async def replace_asset(
    asset_id: str,
    request: Request,
    file: UploadFile = File(...),
    _admin: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    """Replace the file for an existing asset. Keeps metadata, playlist slot, and order."""
    asset = await session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.asset_type in ("url", "html"):
        raise HTTPException(status_code=400, detail="Cannot replace a URL or HTML asset file")

    mimetype = file.content_type or ""
    if not mimetype.startswith("image/") and not mimetype.startswith("video/"):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    # Delete old file
    old_path = _media_dir / asset.uri
    old_path.unlink(missing_ok=True)

    # Write new file
    suffix = _MIME_TO_EXT.get(mimetype, Path(file.filename).suffix)
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

    await audit(session, action="replace", entity_type="asset", entity_id=asset_id,
                details={"name": asset.name, "new_file": file.filename},
                token=_admin, request=request)
    await session.commit()
    await session.refresh(asset)
    return _asset_to_dict(asset)


@router.post("/assets/{asset_id}/duplicate", status_code=201)
async def duplicate_asset(
    asset_id: str,
    request: Request,
    _admin: ApiToken = Depends(require_editor),
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
    elif asset.asset_type == "html":
        # Copy the HTML file
        src_path = _media_dir / asset.uri
        new_filename = f"{new_asset_id}.html"
        dst_path = _media_dir / new_filename
        if src_path.exists():
            import shutil
            shutil.copy2(src_path, dst_path)
            new_asset.uri = new_filename
            new_asset.file_size = dst_path.stat().st_size
            new_asset.content_hash = compute_content_hash(dst_path)
        else:
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

    await audit(session, action="duplicate", entity_type="asset", entity_id=new_asset.id,
                details={"name": new_asset.name, "source_id": asset_id},
                token=_admin, request=request)
    await session.commit()
    await session.refresh(new_asset)
    return _asset_to_dict(new_asset)


@router.delete("/assets/{asset_id}")
async def delete_asset(
    asset_id: str,
    request: Request,
    _admin: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    asset = await session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    asset_name = asset.name
    # Delete file if not a URL asset
    if asset.asset_type != "url":
        filepath = _media_dir / asset.uri
        filepath.unlink(missing_ok=True)
        # Delete thumbnail
        if asset.thumbnail_path:
            thumb_path = _thumbs_dir / asset.thumbnail_path
            thumb_path.unlink(missing_ok=True)

    await audit(session, action="delete", entity_type="asset", entity_id=asset_id,
                details={"name": asset_name}, token=_admin, request=request)
    await session.delete(asset)
    await session.commit()
    return {"ok": True}


@router.post("/assets/reorder")
async def reorder_assets(
    items: list[dict],
    request: Request,
    _admin: ApiToken = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    for item in items:
        asset = await session.get(Asset, item["id"])
        if asset:
            asset.play_order = item["play_order"]
    await audit(session, action="reorder", entity_type="asset", entity_id=None,
                details={"count": len(items)}, token=_admin, request=request)
    await session.commit()
    return {"ok": True}


def _asset_to_dict(asset: Asset, tags: list[dict] | None = None) -> dict:
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
        "transition_type": asset.transition_type,
        "transition_duration": asset.transition_duration,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
        "tags": tags if tags is not None else [],
    }
