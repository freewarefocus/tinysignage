import shutil
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_viewer
from app.database import get_session
from app.models import ApiToken, Asset

_config = yaml.safe_load(Path("config.yaml").read_text())
_media_dir = Path(_config["storage"]["media_dir"])

router = APIRouter()


@router.get("/storage")
async def storage_overview(
    _token: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    """Storage dashboard: total usage, per-asset breakdown, disk info."""
    # Disk stats for the media partition
    disk = shutil.disk_usage(_media_dir.resolve())
    disk_total_mb = round(disk.total / (1024 * 1024), 1)
    disk_used_mb = round(disk.used / (1024 * 1024), 1)
    disk_free_mb = round(disk.free / (1024 * 1024), 1)

    # Per-asset file sizes from DB
    result = await session.execute(
        select(Asset).order_by(Asset.file_size.desc().nullslast())
    )
    assets = result.scalars().all()

    total_media_bytes = 0
    asset_list = []
    for a in assets:
        size = a.file_size or 0
        total_media_bytes += size
        asset_list.append({
            "id": a.id,
            "name": a.name,
            "asset_type": a.asset_type,
            "file_size": size,
            "file_size_mb": round(size / (1024 * 1024), 2) if size else 0,
        })

    total_media_mb = round(total_media_bytes / (1024 * 1024), 2)

    # Thumbnail directory size
    thumbs_dir = _media_dir / "thumbs"
    thumbs_bytes = sum(f.stat().st_size for f in thumbs_dir.iterdir() if f.is_file()) if thumbs_dir.exists() else 0
    thumbs_mb = round(thumbs_bytes / (1024 * 1024), 2)

    # Warning threshold from config
    warning_mb = _config.get("storage", {}).get("warning_threshold_mb", 500)

    return {
        "disk": {
            "total_mb": disk_total_mb,
            "used_mb": disk_used_mb,
            "free_mb": disk_free_mb,
        },
        "media": {
            "total_bytes": total_media_bytes,
            "total_mb": total_media_mb,
            "thumbnails_mb": thumbs_mb,
            "asset_count": len(asset_list),
        },
        "warning_threshold_mb": warning_mb,
        "warning_active": disk_free_mb < warning_mb,
        "assets": asset_list,
    }
