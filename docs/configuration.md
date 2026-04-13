# Configuration

TinySignage is configured through `config.yaml` in the project root and through runtime settings in the CMS.

---

## config.yaml

The configuration file is read at startup. Changes require restarting the application.

```yaml
server:
  host: 0.0.0.0
  port: 8080
  https:
    enabled: false
    cert_file: ./certs/cert.pem
    key_file: ./certs/key.pem
    auto_generate_self_signed: true

storage:
  media_dir: ./media
  db_path: ./db/signage.db
  warning_threshold_mb: 500

display:
  transition_duration: 1.0
  transition_type: fade
  default_duration: 10

player:
  browser: auto
  kiosk: true

cors:
  allowed_origins:
    - '*'

logging:
  level: INFO
  log_dir: ./logs

watchdog:
  enabled: true
  check_interval: 30
  startup_grace: 60
  cms_fail_threshold: 3
  browser_memory_limit_mb: 1024
  browser_fail_threshold: 2
  log_file: ./logs/watchdog.log
  memory_log_interval: 1800
  scheduled_reboot_day: null
  scheduled_reboot_hour: 3
```

### Full reference

| Section | Key | Type | Default | Description |
|---------|-----|------|---------|-------------|
| `server` | `host` | string | `0.0.0.0` | Bind address |
| `server` | `port` | integer | `8080` | Bind port (same port serves HTTP or HTTPS depending on `https.enabled`) |
| `server` | `https.enabled` | boolean | `false` | Serve the CMS and player over HTTPS. HTTPS-only mode — plain HTTP stops responding when enabled |
| `server` | `https.cert_file` | string | `./certs/cert.pem` | Path to TLS certificate (PEM) |
| `server` | `https.key_file` | string | `./certs/key.pem` | Path to TLS private key (PEM, created with mode `0o600`) |
| `server` | `https.auto_generate_self_signed` | boolean | `true` | Generate a 10-year self-signed cert on startup if `cert_file`/`key_file` don't exist |
| `storage` | `media_dir` | string | `./media` | Directory for uploaded media files |
| `storage` | `db_path` | string | `./db/signage.db` | SQLite database file path |
| `storage` | `warning_threshold_mb` | integer | `500` | Storage warning threshold in MB |
| `display` | `transition_duration` | float | `1.0` | Default transition duration in seconds |
| `display` | `transition_type` | string | `fade` | Default transition type (`fade`, `slide`, `cut`) |
| `display` | `default_duration` | integer | `10` | Default display duration per image in seconds |
| `player` | `browser` | string | `auto` | Browser to launch for kiosk mode |
| `player` | `kiosk` | boolean | `true` | Launch player in kiosk (fullscreen) mode |
| `cors` | `allowed_origins` | list | `['*']` | CORS allowed origins |
| `logging` | `level` | string | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `logging` | `log_dir` | string | `./logs` | Directory for log files |
| `watchdog` | `enabled` | boolean | `true` | Master switch for the process watchdog |
| `watchdog` | `check_interval` | integer | `30` | Seconds between health checks |
| `watchdog` | `startup_grace` | integer | `60` | Seconds after startup before checks begin (gives the CMS time to initialize) |
| `watchdog` | `mode` | string | `auto` | What to monitor: `auto` (detect from installed services), `cms`, `player`, or `both` |
| `watchdog` | `cms_fail_threshold` | integer | `3` | Consecutive CMS health check failures before restart |
| `watchdog` | `browser_memory_limit_mb` | integer | `1024` | Browser RSS memory limit in MB. Set to `0` to disable memory monitoring |
| `watchdog` | `browser_fail_threshold` | integer | `2` | Consecutive browser-not-found checks before restart |
| `watchdog` | `log_file` | string | `./logs/watchdog.log` | Watchdog log file path (rotating, 5 MB x 3 backups) |
| `watchdog` | `memory_log_interval` | integer | `1800` | Seconds between memory snapshot log entries. Set to `0` to disable |
| `watchdog` | `scheduled_reboot_day` | integer/null | `null` | Day of week for scheduled system reboot (0=Mon .. 6=Sun). `null` = disabled. Linux/Pi only |
| `watchdog` | `scheduled_reboot_hour` | integer | `3` | Hour (0-23) for the scheduled reboot |

### Additional runtime keys

These keys are managed by TinySignage and should not be edited manually:

| Key | Description |
|-----|-------------|
| `device_id` | Auto-generated UUID for this installation's default device |
| `server_url` | Base URL for the CMS server. Used by the kiosk launcher (`launcher.py`) to know where to point the browser. For player-only installs, this is the remote CMS address (e.g. `http://museum-cms.local:8080`). For all-in-one installs, defaults to `http://localhost:8080`. Also injected as a meta tag into the player HTML for split deployments |
| `display_name` | Friendly name for this installation (set during install) |

---

## HTTPS (optional)

By default, TinySignage serves the CMS and player over plain HTTP. This is fine when the server and browser are on the same trusted network. If you access the CMS from across the internet, a shared cafe network, or any link you don't fully control, enable HTTPS so passwords and content aren't sent in the clear.

**Two ways to turn it on:**

1. **During first-boot setup** — tick the **"Advanced: Enable HTTPS"** checkbox in the setup wizard. TinySignage generates a self-signed certificate and writes the correct values into `config.yaml` for you.
2. **After setup** — edit `config.yaml`, set `server.https.enabled: true`, and restart. On next start, TinySignage auto-generates a cert into `./certs/` if one doesn't already exist.

**What to expect:**

- **A browser warning on first visit.** Self-signed certificates aren't trusted by browsers, so you'll see a "Your connection is not private" page. Click **Advanced → Proceed** once; the browser remembers the exception.
- **HTTPS-only mode.** Once enabled, plain `http://` requests stop responding. There's no automatic HTTP→HTTPS redirect.
- **Same port.** HTTPS runs on the same port as HTTP (8080 by default). Change `server.port` if you want the conventional `8443`.
- **Check the fingerprint.** The CMS **Settings → Network & Security** panel shows the SHA-256 fingerprint of the active certificate, handy if you want to pin it or verify it across devices.
- **Persistence in Docker.** The `./certs` directory is volume-mounted, so self-generated certs survive `docker compose down && up`.

**Providing your own certificate:**

TinySignage doesn't fetch certs from Let's Encrypt or any ACME service. If you want to use a real cert (e.g. from your own CA), point `cert_file` and `key_file` at the PEM files, set `auto_generate_self_signed: false`, and restart. The files must be readable by the user running TinySignage.

---

## CMS runtime settings

Display settings can also be changed from the CMS **Settings** page without editing `config.yaml` or restarting:

- Transition type
- Transition duration
- Default image duration
- Shuffle mode

These runtime settings are stored in the database and take effect immediately. They override the `display` section of `config.yaml`.

Per-playlist settings override runtime settings. Per-asset transition settings override per-playlist settings.

### Settings priority (highest to lowest)

1. Per-asset transition overrides
2. Per-playlist settings
3. CMS runtime settings (database)
4. `config.yaml` display defaults

---

## Docker-specific notes

In Docker, `config.yaml` is bind-mounted:

```yaml
volumes:
  - ./config.yaml:/app/config.yaml
  - ./certs:/app/certs
```

Edit the file on the host and restart the container to apply changes. The `media_dir` and `db_path` paths in the config refer to container paths (`/app/media`, `/app/db`), which are mapped to host directories via the other volume mounts. The `./certs` mount is what lets self-generated HTTPS certificates survive `docker compose down && up`.

## Raspberry Pi notes

The installer generates a `config.env` file with the `SECRET_KEY` for session security. The `config.yaml` defaults work for most Pi installations.

For **player-only** Pi installs (`--mode player`), the installer sets `server_url` to the remote CMS address you provide. The kiosk launcher reads this value to point Chromium at the correct server — no local backend runs on the device.

For **CMS-only** Pi installs (`--mode cms`), no player service is configured. The `server_url` is set to `http://localhost:8080`.

---

## See also

- [Getting Started](getting-started.md) -- Initial setup walkthrough
- [Install with Docker](install-docker.md) -- Docker volume configuration
- [Player Behavior](player-behavior.md) -- How display settings affect playback
- [Troubleshooting](troubleshooting.md) -- Configuration-related issues
