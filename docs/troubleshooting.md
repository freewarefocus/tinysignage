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

### Watchdog logs

The process watchdog runs as a separate process and has its own log:

| Log | Location | What it contains |
|-----|----------|-----------------|
| **Watchdog log** | `logs/watchdog.log` | Health check results, process restarts, memory snapshots (rotating, 5 MB x 3 backups) |
| **systemd journal** (Pi/Linux) | `journalctl -u signage-watchdog` | Same output via stderr |

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
Another application is using port 8080. Either stop it, or edit `config.yaml` to use a different port:
```yaml
server:
  host: 0.0.0.0
  port: 9090
```
Then start TinySignage with `python -m app.server`.

---

## HTTPS issues

**Browser shows "Your connection is not private" / "not secure":**
Expected on first visit when HTTPS is enabled with a self-signed certificate. Click **Advanced → Proceed to localhost (unsafe)** once; the browser remembers the exception. The warning does not mean your connection is unencrypted — it only means the certificate is not signed by a public certificate authority. To verify the certificate, open **CMS → Settings → Network & Security → Technical details** and compare the SHA-256 fingerprint against `openssl x509 -in certs/cert.pem -noout -fingerprint -sha256`.

**Plain `http://localhost:8080` stops responding after enabling HTTPS:**
This is intentional. TinySignage is HTTPS-only when `server.https.enabled: true` — there is no HTTP→HTTPS redirect. Use `https://127.0.0.1:8080` instead. To go back to HTTP, edit `config.yaml` and set `server.https.enabled: false`, then restart.

**Player can't connect after enabling HTTPS:**
The kiosk launcher (`launcher.py`) auto-detects the cert and passes the right Chromium flags to accept it. If you see a cert warning in the kiosk browser, make sure:
1. `config.yaml` has the new `https://` scheme in `server_url` (the setup wizard writes this automatically, but `--mode player` installs need it set manually)
2. The `cryptography` Python package is installed — without it, `launcher.py` falls back to a blunter `--ignore-certificate-errors` flag that still works but is less targeted
3. For split deployments, the remote CMS cert isn't locally readable, so the launcher uses the fallback flag automatically

**`certs/cert.pem: permission denied`:**
The private key (`certs/key.pem`) is written with mode `0o600`. If you run the server as a different user than the one that created the cert, either `chown` the files or regenerate them by deleting `certs/` and restarting (TinySignage will recreate them).

**Docker: HTTPS works once, then breaks after `docker compose down`:**
The `./certs` directory must be bind-mounted so the generated cert persists across container rebuilds. Check that `docker-compose.yml` includes `- ./certs:/app/certs` under `volumes`. If you upgraded from an older version, add that line manually.

**Want to use a real certificate (not self-signed):**
Point `server.https.cert_file` and `server.https.key_file` at your PEM files, set `server.https.auto_generate_self_signed: false`, and restart. TinySignage won't touch the files. Let's Encrypt/ACME is not built in — use `certbot` or similar to manage renewals externally.

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
The player has no stored device token. On a local install (Raspberry Pi), the player should auto-pair via local bootstrap — if you see the registration form instead, check that `device_id` exists in `config.yaml` and that the server is running. For remote players, enter the server URL and a display name, then submit. The device will appear as "pending" in the CMS Devices page. An admin must approve it before it can show content.

**Player registered with wrong server URL:**
If you entered the wrong server address during registration, reset the player from the command line:

- **Windows / macOS:** `python launcher.py --reset`
- **Raspberry Pi:**
  ```bash
  sudo systemctl stop signage-player-lite
  python3 /opt/tinysignage/launcher.py --reset
  sudo systemctl restart signage-player-lite
  ```

This deletes the browser profile and returns the player to the registration screen on next launch. You need local (command-line) access to the device -- there is no remote reset.

**Player stuck on "Connecting..." or shows red status dot:**
The player cannot reach the backend. Verify:
1. The backend is running (`curl -k https://127.0.0.1:8080/health` should return `{"status": "ok"}`)
2. The player URL is correct (the port and hostname must match the running server)
3. No firewall is blocking the connection

**Player not updating after CMS changes:**
The player polls every 30 seconds. Wait at least 30 seconds. If content still does not update, press **Ctrl+Shift+D** on the player to open the debug log and look for poll errors. You can also check `GET /api/devices/{id}/player-log?level=warn` remotely. Try a hard refresh (Ctrl+Shift+R).

**Player won't go fullscreen:**
Use the browser's fullscreen shortcut: **F11** (most browsers), **Ctrl+Cmd+F** (Safari on macOS). For a dedicated display, use Chrome's kiosk mode:
```bash
chrome --kiosk https://127.0.0.1:8080/player
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
Make sure the server is bound to `0.0.0.0` (not `127.0.0.1`). Check your firewall settings. On Windows, allow Python through the firewall and make sure your network is set to Private, not Public — see [Windows firewall setup](install-windows.md#allow-through-windows-firewall) for step-by-step instructions. On macOS, allow incoming connections when prompted.

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

## Watchdog issues

**Watchdog log location:**
The process watchdog writes to `logs/watchdog.log` (rotating, 5 MB x 3 backups) and to stderr. On Pi/Linux: `journalctl -u signage-watchdog`. On macOS: `~/Library/LaunchAgents/com.tinysignage.watchdog.plist` stdout goes to `logs/watchdog.log`.

**Watchdog keeps restarting the CMS during startup:**
The watchdog has a startup grace period (default 60 seconds) where it skips health checks. If your CMS takes longer to initialize (large database, slow SD card), increase `watchdog.startup_grace` in `config.yaml`.

**Watchdog not running on Pi:**
Check the service status:
```bash
sudo systemctl status signage-watchdog
```
If the service doesn't exist, re-run the installer with `--update` -- it self-heals missing watchdog services.

**Watchdog incorrectly restarting the browser:**
The watchdog auto-detects what to monitor based on installed services. If it's monitoring a browser that isn't your signage player, set `watchdog.mode` explicitly in `config.yaml`:
```yaml
watchdog:
  mode: cms    # Only monitor the CMS, not the browser
```

**Disabling the watchdog:**
```yaml
watchdog:
  enabled: false
```
Or stop the service: `sudo systemctl stop signage-watchdog` (Pi/Linux).

**Memory snapshots not appearing in the log:**
Memory snapshots are logged every 30 minutes by default. Check `watchdog.memory_log_interval` in `config.yaml`. Set to `0` to disable.

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
