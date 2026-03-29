# Backup and Restore

TinySignage supports one-click backup and restore of your entire installation, including the database and all media files.

---

## What gets backed up

A backup ZIP archive contains:

- **SQLite database** -- all configuration, playlists, devices, schedules, users, and settings
- **Media files** -- all uploaded images, videos, and thumbnails

The ZIP is a complete snapshot. Restoring it gives you an identical installation.

## What is not included

- `config.yaml` -- back this up separately if you have custom settings
- Log files
- The Python environment and application code

---

## Exporting a backup

### From the CMS

An admin user can export a backup from the CMS admin interface.

### From the API

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8080/api/backup/export \
     -o backup.zip
```

The response is a ZIP file download. Store it somewhere safe.

---

## Restoring from a backup

### From the API

```bash
curl -X POST \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -F "file=@backup.zip" \
     http://localhost:8080/api/backup/import
```

This replaces the current database and media files with the backup contents. Existing data is overwritten.

**Warning:** Restoring a backup is destructive. The current database and media are replaced entirely. Export a backup of the current state first if you want to preserve it.

---

## When to back up

- Before updating TinySignage (git pull, Docker rebuild)
- Before making major changes to schedules or device configurations
- On a regular schedule if you have important content

---

## Access control

Backup and restore operations are **admin-only**. Editor and viewer roles cannot access these endpoints.

---

## See also

- [Users and Permissions](users-and-permissions.md) -- Admin role requirement
- [Configuration](configuration.md) -- config.yaml (not included in backup)
- [API Reference](api-reference.md) -- Backup endpoints
