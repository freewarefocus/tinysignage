"""Backup & restore — export/import ZIP of database + media."""

import json
import logging
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.auth import require_admin
from app.database import engine, get_session
from app.models import ApiToken

log = logging.getLogger("tinysignage.backup")

router = APIRouter(prefix="/backup", tags=["backup"])

_config_path = Path("config.yaml")
_config = yaml.safe_load(_config_path.read_text())
_db_path = Path(_config["storage"]["db_path"]).resolve()
_media_dir = Path(_config["storage"]["media_dir"]).resolve()


@router.get("/export")
async def export_backup(
    request: Request,
    token: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Export a ZIP archive containing the database and all media files.
    Admin-only.
    """
    # Create a consistent SQLite snapshot using the backup API
    zip_tf = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    zip_path = Path(zip_tf.name)
    zip_tf.close()
    backup_tf = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    backup_db_path = Path(backup_tf.name)
    backup_tf.close()

    try:
        src_conn = sqlite3.connect(str(_db_path))
        dst_conn = sqlite3.connect(str(backup_db_path))
        src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()
    except Exception as e:
        backup_db_path.unlink(missing_ok=True)
        zip_path.unlink(missing_ok=True)
        log.error("Database backup failed: %s", e)
        raise HTTPException(status_code=500, detail="Database backup failed")

    # Build manifest
    manifest = {
        "version": "1.0",
        "app": "TinySignage",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "db_file": "signage.db",
        "media_dir": "media",
    }

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            zf.write(backup_db_path, "signage.db")

            if _media_dir.exists():
                for file_path in _media_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = (
                            Path("media") / file_path.relative_to(_media_dir)
                        ).as_posix()
                        zf.write(file_path, arcname)
    except Exception as e:
        log.error("ZIP creation failed: %s", e)
        zip_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Backup creation failed")
    finally:
        backup_db_path.unlink(missing_ok=True)

    # Audit log
    zip_size = zip_path.stat().st_size
    await audit.record(
        session,
        action="export",
        entity_type="backup",
        details={"size_bytes": zip_size},
        token=token,
        request=request,
    )
    await session.commit()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"tinysignage-backup-{timestamp}.zip"

    def iterfile():
        try:
            with open(zip_path, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk
        finally:
            zip_path.unlink(missing_ok=True)

    return StreamingResponse(
        iterfile(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
async def import_backup(
    request: Request,
    file: UploadFile,
    token: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Import a backup ZIP archive, replacing the database and media files.
    Admin-only. Server restart recommended after restore.
    """
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip archive")

    # Stream upload to temp file (handles large backups)
    tmp_tf = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp_path = Path(tmp_tf.name)
    tmp_tf.close()
    try:
        with open(tmp_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

        return await _process_import(tmp_path, file.filename, request, token, session)
    finally:
        tmp_path.unlink(missing_ok=True)


async def _process_import(
    zip_path: Path,
    filename: str,
    request: Request,
    token: ApiToken,
    session: AsyncSession,
) -> dict:
    """Validate and apply an imported backup ZIP."""
    # Validate ZIP
    try:
        zf = zipfile.ZipFile(str(zip_path))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file")

    try:
        # Validate manifest
        if "manifest.json" not in zf.namelist():
            raise HTTPException(
                status_code=400,
                detail="Missing manifest.json — not a valid TinySignage backup",
            )

        manifest = json.loads(zf.read("manifest.json"))
        if manifest.get("app") != "TinySignage":
            raise HTTPException(
                status_code=400, detail="Not a TinySignage backup file"
            )

        db_name = manifest.get("db_file", "signage.db")
        if db_name not in zf.namelist():
            raise HTTPException(
                status_code=400,
                detail=f"Missing database file '{db_name}' in archive",
            )

        # Extract to temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Zip-slip protection: validate all paths stay within target
            for info in zf.infolist():
                target = (tmpdir_path / info.filename).resolve()
                try:
                    target.relative_to(tmpdir_path.resolve())
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid archive: path traversal detected",
                    )

            zf.extractall(tmpdir_path)
            zf.close()

            # Validate the extracted database
            extracted_db = tmpdir_path / db_name
            try:
                conn = sqlite3.connect(str(extracted_db))
                tables = [
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                ]
                conn.close()
                if "assets" not in tables:
                    raise HTTPException(
                        status_code=400,
                        detail="Database does not contain expected TinySignage tables",
                    )
            except sqlite3.Error as e:
                log.error("Invalid database in backup archive: %s", e)
                raise HTTPException(
                    status_code=400, detail="Invalid database file in backup archive"
                )

            # Audit log BEFORE destructive operations (current DB still valid)
            await audit.record(
                session,
                action="import",
                entity_type="backup",
                details={
                    "filename": filename,
                    "manifest_created_at": manifest.get("created_at"),
                },
                token=token,
                request=request,
            )
            await session.commit()
            await session.close()

            # Dispose async engine so no connections hold the DB file open.
            # Concurrent requests will fail during import — a server restart
            # is required after restore for full reliability.
            await engine.dispose()

            # Replace database using sqlite3 backup API (atomic copy)
            try:
                src_conn = sqlite3.connect(str(extracted_db))
                dst_conn = sqlite3.connect(str(_db_path))
                src_conn.backup(dst_conn)
                dst_conn.close()
                src_conn.close()
            except sqlite3.Error as e:
                log.error("Database restore failed: %s", e)
                raise HTTPException(
                    status_code=500, detail="Database restore failed"
                )

            # Replace media files
            extracted_media = tmpdir_path / "media"
            if extracted_media.exists():
                if _media_dir.exists():
                    shutil.rmtree(_media_dir)
                _media_dir.mkdir(parents=True, exist_ok=True)
                (_media_dir / "thumbs").mkdir(parents=True, exist_ok=True)

                for item in extracted_media.rglob("*"):
                    if item.is_file():
                        dest = _media_dir / item.relative_to(extracted_media)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dest)

            log.info("Backup restored from %s", filename)

    except HTTPException:
        raise
    except Exception as e:
        log.error("Backup import failed: %s", e)
        raise HTTPException(status_code=500, detail="Backup import failed")
    finally:
        try:
            zf.close()
        except Exception:
            pass

    return {
        "status": "ok",
        "message": "Backup restored successfully. Please restart the server for all changes to take effect.",
        "manifest": manifest,
    }
