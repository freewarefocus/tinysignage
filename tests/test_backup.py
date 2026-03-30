"""Tests for backup export/import endpoints. [FT-15.*]"""

import io

from tests.factories import create_token
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
