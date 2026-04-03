"""MRSS (Media RSS) feed endpoint for BrightSign and other signage players."""

from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.devices import _get_server_url
from app.api.overrides import evaluate_override_for_device
from app.api.schedules import evaluate_schedule_for_device
from app.auth import _lookup_token
from app.database import get_session
from app.models import Asset, AssetTag, Device, Playlist, PlaylistItem

router = APIRouter()

# MRSS-compatible asset types (HTML/URL not supported by MRSS consumers)
_MRSS_ASSET_TYPES = {"image", "video"}


@router.get("/devices/{device_id}/mrss")
async def mrss_feed(
    device_id: str,
    request: Request,
    token: str = Query(..., description="API token (ts_xxx)"),
    session: AsyncSession = Depends(get_session),
):
    """Return an MRSS XML feed of the device's current playlist.

    Designed for BrightSign and other signage players that consume MRSS natively.
    Only image and video assets are included (HTML/URL not MRSS-compatible).
    """
    # Authenticate via query-string token
    api_token = await _lookup_token(token, session)

    # Allow device tokens (matching device) or admin/viewer tokens
    if api_token.role == "device":
        if api_token.device_id != device_id:
            raise HTTPException(status_code=403, detail="Token not authorized for this device")
    elif api_token.role not in ("admin", "editor", "viewer"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Update last_seen (lightweight heartbeat)
    device.last_seen = now
    if device.status not in ("pending",):
        device.status = "online"
    await session.commit()

    if device.status == "pending":
        return Response(
            content=_build_mrss_xml("TinySignage - Pending", [], ""),
            media_type="application/rss+xml",
        )

    server_url = _get_server_url(request)

    # Evaluate overrides
    active_override = await evaluate_override_for_device(device_id, session)
    effective_playlist_id = None

    if active_override and active_override.content_type == "playlist":
        effective_playlist_id = active_override.content
    else:
        # Normal flow: schedules then device default
        scheduled_id, _ = await evaluate_schedule_for_device(device_id, session)
        effective_playlist_id = scheduled_id or device.playlist_id

    if not effective_playlist_id:
        return Response(
            content=_build_mrss_xml("TinySignage - No Playlist", [], server_url),
            media_type="application/rss+xml",
        )

    result = await session.execute(
        select(Playlist)
        .where(Playlist.id == effective_playlist_id)
        .options(
            selectinload(Playlist.items)
            .selectinload(PlaylistItem.asset)
            .selectinload(Asset.asset_tags)
            .selectinload(AssetTag.tag)
        )
    )
    playlist = result.scalars().first()
    if not playlist:
        return Response(
            content=_build_mrss_xml("TinySignage - Unknown Playlist", [], server_url),
            media_type="application/rss+xml",
        )

    # Filter to enabled, in-schedule, MRSS-compatible assets
    items = []
    for item in playlist.items:
        asset = item.asset
        if not asset or not asset.is_enabled:
            continue
        if asset.asset_type not in _MRSS_ASSET_TYPES:
            continue
        if asset.start_date and asset.start_date > now:
            continue
        if asset.end_date and asset.end_date < now:
            continue
        items.append(item)

    title = f"TinySignage - {playlist.name}"
    xml = _build_mrss_xml(title, items, server_url)
    return Response(content=xml, media_type="application/rss+xml")


def _build_mrss_xml(title: str, items: list, server_url: str) -> bytes:
    """Build MRSS XML bytes from playlist items."""
    rss = Element("rss", version="2.0")
    rss.set("xmlns:media", "http://search.yahoo.com/mrss/")

    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = title

    for item in items:
        asset = item.asset
        entry = SubElement(channel, "item")
        SubElement(entry, "title").text = asset.name

        media_url = f"{server_url}/media/{asset.uri}" if server_url else asset.uri
        attrs = {
            "url": media_url,
            "type": asset.mimetype or _guess_mimetype(asset.asset_type, asset.uri),
        }

        duration = item.duration or asset.duration
        if duration:
            attrs["duration"] = str(duration)

        if asset.file_size:
            attrs["fileSize"] = str(asset.file_size)

        SubElement(entry, "media:content", **attrs)

    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(rss, encoding="unicode").encode("utf-8")


def _guess_mimetype(asset_type: str, uri: str) -> str:
    """Fallback mimetype guessing for assets without stored mimetype."""
    if asset_type == "video":
        return "video/mp4"
    ext = uri.rsplit(".", 1)[-1].lower() if "." in uri else ""
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "svg": "image/svg+xml",
    }.get(ext, "image/jpeg")
