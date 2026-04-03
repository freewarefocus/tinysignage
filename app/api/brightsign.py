"""BrightSign setup bundle endpoint — generates a ZIP with autorun.brs + config.json."""

import io
import json
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.devices import _get_server_url
from app.auth import ApiToken, require_admin

router = APIRouter()

_AUTORUN_PATH = Path("brightsign/autorun.brs")


@router.get("/brightsign/setup-bundle")
async def setup_bundle(
    request: Request,
    _admin: ApiToken = Depends(require_admin),
):
    """Download a ZIP containing autorun.brs + config.json pre-filled with server URL.

    Admin extracts this to a BrightSign SD card to connect the player.
    """
    server_url = _get_server_url(request)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Include the BrightScript autorun
        if _AUTORUN_PATH.exists():
            zf.write(_AUTORUN_PATH, "autorun.brs")
        else:
            # Fallback: embed a minimal stub if the file is missing
            zf.writestr("autorun.brs", "' autorun.brs not found — see TinySignage docs\n")

        # Pre-filled config with the correct server URL
        config = {
            "server_url": server_url,
            "display_name": "BrightSign Player",
        }
        zf.writestr("config.json", json.dumps(config, indent=2) + "\n")

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=tinysignage-brightsign.zip"},
    )
