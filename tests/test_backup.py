"""Tests for backup export/import endpoints. [FT-15.*]"""

import io
import json
import zipfile

from tests.factories import create_asset, create_token
from tests.helpers import auth_header


async def test_export_backup(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/backup/export", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"  # ZIP magic bytes


async def test_export_backup_viewer_forbidden(client, session):
    _, token = await create_token(session, role="viewer")
    await session.commit()
    resp = await client.get("/api/backup/export", headers=auth_header(token))
    assert resp.status_code == 403


async def test_import_backup_invalid_file(client, session):
    _, token = await create_token(session)
    await session.commit()
    files = {"file": ("backup.zip", io.BytesIO(b"not a zip"), "application/zip")}
    resp = await client.post(
        "/api/backup/import", files=files, headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_import_backup_viewer_forbidden(client, session):
    _, token = await create_token(session, role="viewer")
    await session.commit()
    files = {"file": ("backup.zip", io.BytesIO(b"fake"), "application/zip")}
    resp = await client.post(
        "/api/backup/import", files=files, headers=auth_header(token),
    )
    assert resp.status_code == 403


async def test_export_roundtrip(client, session):
    """Export includes DB, config.yaml, and manifest; import restores them."""
    await create_asset(session, name="roundtrip.png")
    _, token = await create_token(session)
    await session.commit()

    # Export
    resp = await client.get("/api/backup/export", headers=auth_header(token))
    assert resp.status_code == 200

    # Verify ZIP contents
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert "manifest.json" in names
    assert "signage.db" in names
    assert "config.yaml" in names

    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["app"] == "TinySignage"
    assert manifest["config_file"] == "config.yaml"

    # Re-import and verify success
    files = {"file": ("backup.zip", io.BytesIO(resp.content), "application/zip")}
    resp2 = await client.post(
        "/api/backup/import", files=files, headers=auth_header(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "ok"
