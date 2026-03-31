# Troubleshooting

Common issues and fixes for TinySignage. For platform-specific issues, also see the install guides: [Raspberry Pi](install-raspberry-pi.md), [Windows](install-windows.md), [macOS](install-macos.md), [Docker](install-docker.md).

---

## Checking logs

Before troubleshooting specific issues, know where to find diagnostic information. TinySignage has three log channels:

### Backend logs

| Log | Location | What it contains |
|-----|----------|-----------------|
| **Application log** | `logs/tinysignage.log` | All INFO+ messages, rotating (5 MB x 3 backups) |
| **Error log** | `logs/errors.jsonl` | ERROR+ with stack traces and request context (JSON, one entry per line) |
| **Console output** | stdout/stderr | Same as application log, useful in Docker (`docker compose logs`) |

The error log is also viewable in the CMS at **System > System Log** (admin only), or via `GET /api/logs/errors`.

### Player logs

The player stores a persistent ring buffer (last 200 entries) in the browser's localStorage. Three ways to access it:

1. **Debug overlay** -- press **Ctrl+Shift+D** on the player screen to open a full-screen log viewer with Refresh, Clear, and Close buttons
2. **Remote API** -- `GET /api/devices/{id}/player-log` (requires viewer+ auth). Supports `?level=error` and `?search=poll` filters. Useful for headless devices (Raspberry Pi, kiosk) where you cannot open a browser console
3. **Browser DevTools** -- Application tab > Local Storage > `tinysignage_player_log`

The player uploads its log to the server after each successful heartbeat, so remote logs are at most 60 seconds behind.

### Audit log

The audit log (CMS > Audit Log, admin only) records **who changed what** -- it is not an error log. Use it to track:

- Who deleted an asset, modified a playlist, or changed device settings
- Failed login attempts (`auth_failed` action with username and IP)
- Timeline of CMS mutations for compliance or debugging user-reported issues

---

## Installation issues

**`pip install` fails with compilation errors:**
TinySignage's Python dependencies are all pure-Python except Pillow (image thumbnails). If Pillow fails to install, try upgrading pip first: `pip install --upgrade pip`. On Linux, you may need `libjpeg-dev` and `zlib1g-dev` (`sudo apt install libjpeg-dev zlib1g-dev`).

**`alembic upgrade head` fails:**
Make sure you are running Alembic from the project root directory (where `alembic.ini` is). If the database is corrupted, delete `db/signage.db` and run the command again -- a fresh database will be created.

**Port 8080 already in use:**
Another application is using port 8080. Either stop it, or start TinySignage on a different port:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 9090
```

---

## Setup wizard issues

**Setup page shows "already completed":**
The setup wizard only runs once. To re-run it, delete `db/.setup_done` and restart the application.

**Setup page is blank or won't load:**
Wait 10-15 seconds for the application to fully initialize. Check the application logs for errors.

---

## Player issues

**Player shows a black screen:**
The backend may still be starting. The player retries every 30 seconds -- give it a minute. Check that the backend is running and accessible at the URL shown in the browser's address bar.

**Player shows registration form:**
The player has no stored device token. Enter the server URL and a display name, then submit. The device will appear as "pending" in the CMS Devices page. An admin must approve it before it can show content.

**Player stuck on "Connecting..." or shows red status dot:**
The player cannot reach the backend. Verify:
1. The backend is running (`curl http://localhost:8080/health` should return `{"status": "ok"}`)
2. The player URL is correct (the port and hostname must match the running server)
3. No firewall is blocking the connection

**Player not updating after CMS changes:**
The player polls every 30 seconds. Wait at least 30 seconds. If content still does not update, press **Ctrl+Shift+D** on the player to open the debug log and look for poll errors. You can also check `GET /api/devices/{id}/player-log?level=warn` remotely. Try a hard refresh (Ctrl+Shift+R).

**Player won't go fullscreen:**
Use the browser's fullscreen shortcut: **F11** (most browsers), **Ctrl+Cmd+F** (Safari on macOS). For a dedicated display, use Chrome's kiosk mode:
```bash
chrome --kiosk http://localhost:8080/player
```

**Video plays but no sound:**
Most browsers require user interaction before autoplaying video with sound. For digital signage, content is typically silent. If you need audio, ensure the user has interacted with the page at least once.

---

## Media issues

**Upload fails with no error message in the UI:**
Check the browser console (F12 > Console) for `[UploadZone]` errors. Also check `logs/errors.jsonl` or the CMS System Log for server-side errors. Verify that the `media/` directory exists and is writable, and check disk space.

**No thumbnails for uploaded videos:**
FFmpeg is required for video thumbnails. Install it:
- Docker: FFmpeg is included in the image
- Raspberry Pi: `sudo apt install ffmpeg`
- macOS: `brew install ffmpeg`
- Windows: `winget install Gyan.FFmpeg`

Verify with `ffmpeg -version`. Video uploads work without FFmpeg -- you just do not get thumbnail previews.

**Images display rotated in the player:**
Some cameras embed EXIF orientation data. Pillow reads EXIF data for thumbnails, but the player relies on the browser for rendering. Most modern browsers handle EXIF orientation correctly.

---

## Network issues

**Can't access CMS from another device on the network:**
Make sure the server is bound to `0.0.0.0` (not `127.0.0.1`). Check your firewall settings. On Windows, allow Python through the firewall. On macOS, allow incoming connections when prompted.

**Can't reach `tinysignage.local` (Raspberry Pi):**
mDNS (Avahi) may not be running, or your client device does not support `.local` discovery. Use the Pi's IP address instead:
```bash
hostname -I
```

---

## Database issues

**Database locked errors:**
SQLite allows only one writer at a time. These errors are usually transient and resolve on the next request. If persistent, check for runaway processes that might be holding the database open.

**Database corrupted or won't open:**
Export a backup first if possible. Then delete `db/signage.db` and restart the application. The database is recreated with the setup wizard. Restore from your most recent backup.

**Want to re-run the setup wizard:**
Delete `db/.setup_done` and restart. The setup wizard will appear at `/setup`.

---

## Performance issues

**CMS is slow to load:**
The CMS is a Vue single-page app that loads once and then uses API calls. If the initial load is slow, check your network speed between the browser and the server. The CMS build is served as static files -- subsequent loads are fast due to browser caching.

**Player transitions are choppy:**
Check device hardware. Transitions use CSS opacity with GPU compositing, which works well on most hardware. Reduce transition duration or switch to `cut` transitions on low-powered devices. Very large images (8K+) may cause performance issues -- resize them before uploading.

**High memory usage:**
The Docker container is limited to 512MB by default. The systemd service unit also sets a `MemoryMax`. If you have many large media files, the server may need more memory for thumbnail generation. Increase the limit in `docker-compose.yml` or the systemd unit.

---

## Docker-specific issues

**Container exits immediately:**
Check logs with `docker compose logs signage`. Common causes: port conflict, missing config.yaml, database permission issues.

**Changes to config.yaml not taking effect:**
config.yaml is read at startup. Restart the container after editing:
```bash
docker compose restart signage
```

**Build fails during npm install:**
Check your internet connection. The first build downloads dependencies. Subsequent builds use Docker's layer cache.

---

## See also

- [Install with Docker](install-docker.md) -- Docker setup and management
- [Install on Raspberry Pi](install-raspberry-pi.md) -- Pi-specific troubleshooting
- [Install on Windows](install-windows.md) -- Windows-specific troubleshooting
- [Install on macOS](install-macos.md) -- macOS-specific troubleshooting
- [Configuration](configuration.md) -- Settings reference
- [Player Behavior](player-behavior.md) -- How the player works
