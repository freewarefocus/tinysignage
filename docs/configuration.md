# Configuration

TinySignage is configured through `config.yaml` in the project root and through runtime settings in the CMS.

---

## config.yaml

The configuration file is read at startup. Changes require restarting the application.

```yaml
server:
  host: 0.0.0.0
  port: 8080

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
```

### Full reference

| Section | Key | Type | Default | Description |
|---------|-----|------|---------|-------------|
| `server` | `host` | string | `0.0.0.0` | Bind address |
| `server` | `port` | integer | `8080` | Bind port |
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

### Additional runtime keys

These keys are managed by TinySignage and should not be edited manually:

| Key | Description |
|-----|-------------|
| `device_id` | Auto-generated UUID for this installation's default device |
| `server_url` | Base URL for the CMS server. Used by the kiosk launcher (`launcher.py`) to know where to point the browser. For player-only installs, this is the remote CMS address (e.g. `http://museum-cms.local:8080`). For all-in-one installs, defaults to `http://localhost:8080`. Also injected as a meta tag into the player HTML for split deployments |
| `display_name` | Friendly name for this installation (set during install) |

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
```

Edit the file on the host and restart the container to apply changes. The `media_dir` and `db_path` paths in the config refer to container paths (`/app/media`, `/app/db`), which are mapped to host directories via the other volume mounts.

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
