# Architecture

TinySignage is a single-process, self-contained digital signage system. This document covers the system design, project layout, and key technical decisions.

---

## System overview

```
Browser (player.html)  <-- Poll /api/devices/{id}/playlist -->  FastAPI (uvicorn)
Browser (Vue CMS)      <-- REST /api/* (Bearer auth)       -->     |
                                                                SQLite (aiosqlite)
                                                                Alembic (migrations)
                                                                Auth middleware
                                                                Scheduler (asyncio)
                                                                Device watchdog (asyncio)

watchdog_process.py    <-- GET /health (independent process) -->   |
                          Monitors CMS + browser processes
                          RSS memory enforcement
                          Periodic memory snapshots
                          Optional scheduled reboot (Pi/Linux)
```

One FastAPI process serves everything: the REST API, the Vue CMS (as static files), the player HTML page, and uploaded media. SQLite is the only database. There are no external services, no message queues, no caches, no workers.

---

## Design decisions

### Why polling, not WebSocket

For digital signage, a 30-second update delay is invisible to viewers. Polling with local cache means:

- The player survives network outages indefinitely (no reconnect logic)
- No persistent connections consuming server resources
- No state synchronization protocol
- The player and backend are fully decoupled

### Why SQLite

SQLite is sufficient for self-hosted single-instance signage:

- No separate database process to install or manage
- Database is a single file, trivial to back up
- Performance is more than adequate for the write patterns in signage (infrequent CMS writes, frequent player reads)
- Eliminates a category of deployment problems

### Why single process

One process simplifies deployment. No process manager, no inter-process communication, no distributed locking. Systemd or Docker restarts handle crashes.

### Why no external services

TinySignage is designed for environments that may have no internet access. Every dependency is bundled or local. This also means no vendor lock-in, no API keys to manage, and no privacy concerns.

---

## Project layout

```
TinySignage/
  app/
    main.py              # FastAPI app, lifespan, route mounts, middleware
    models.py            # SQLAlchemy ORM (17 models)
    database.py          # Async engine (NullPool), migrations, seeding
    schemas.py           # Pydantic request/response schemas
    auth.py              # Token generation, hashing, role dependencies
    audit.py             # Audit logging helper
    scheduler.py         # Playlist cycling background task
    watchdog.py          # Device heartbeat monitoring (in-process async task)
    media.py             # Thumbnail generation, content hashing
    error_handlers.py    # Structured error response handlers
    logging_config.py    # File and console logging with rotation
    api/                 # REST API route modules (19 modules)
    static/              # Player HTML/JS/CSS
  cms/                   # Vue 3 + PrimeVue CMS source
    src/
      views/             # 14 CMS views
      components/        # 4 reusable components
      api/client.js      # Fetch wrapper with Bearer auth
      router/index.js    # Routes, auth guard, admin protection
  install/               # Raspberry Pi / Linux install scripts
  systemd/               # Systemd service units
  alembic/               # Database migration framework (20 migrations)
  media/                 # Uploaded files (gitignored)
  db/                    # SQLite database (gitignored)
  watchdog_process.py    # Independent process watchdog (no app/ imports)
  config.yaml            # User configuration
  Dockerfile             # Multi-stage build (35 lines)
  docker-compose.yml     # Single service definition (13 lines)
  requirements.txt       # Python dependencies (7 packages)
```

---

## Backend structure

### FastAPI app (`app/main.py`)

The application entry point configures:

- **Lifespan**: initializes the database (with Alembic migrations), starts the scheduler and watchdog background tasks
- **Static mounts**: player files, media directory, built CMS files
- **Middleware**: CORS configuration, Cache-Control headers for media
- **Routes**: `/player` (injects `server_url` meta tag), `/cms` (Vue catch-all), `/admin` (redirect), `/health`, `/setup`
- **API routers**: all 19 modules from `app/api/`

### Models (`app/models.py`)

19 SQLAlchemy models using async mapped columns:

| Model | Purpose |
|-------|---------|
| Asset | Media items (image, video, URL, HTML) |
| Playlist | Ordered content collections |
| PlaylistItem | Asset-to-playlist association with order |
| Device | Player endpoints with health tracking |
| DeviceGroup | Logical device groupings |
| DeviceGroupMembership | Device-to-group association |
| Layout | Multi-zone screen layouts |
| LayoutZone | Positioned zones within layouts |
| Schedule | Time-based playlist switching rules |
| Override | Emergency content overrides |
| TriggerFlow | Interactive trigger flow definitions |
| TriggerBranch | Trigger flow branches linking playlists |
| User | CMS user accounts with roles |
| ApiToken | Authentication tokens (session and API) |
| Tag | Media organization labels |
| AssetTag | Asset-to-tag association |
| Settings | Global display settings (singleton) |
| AuditLog | Mutation audit trail |
| SchemaVersion | Legacy migration tracking (Alembic now manages this) |

### Database (`app/database.py`)

- **Engine**: SQLAlchemy async with `aiosqlite` 0.21.0 and `NullPool` (no connection pooling for SQLite)
- **Migrations**: `init_db()` runs Alembic migrations on startup
- **Seeding**: creates default Settings, Playlist, and Device if they do not exist

### Auth (`app/auth.py`)

- **Token format**: `ts_` prefix + 48 hex chars (24 random bytes)
- **Token storage**: SHA-256 hash stored in database, plaintext never persisted
- **Password hashing**: bcrypt
- **Device registration**: keyless self-registration with admin approval gate
- **Role hierarchy**: admin (3) > editor (2) > viewer (1) > device (0)
- **Dependencies**: `require_admin`, `require_editor`, `require_viewer`, `require_device` check minimum role level

### Background tasks

- **Scheduler** (`app/scheduler.py`): async loop that manages playlist cycling. The scheduler tracks state but the player self-advances -- no server push.
- **Device watchdog** (`app/watchdog.py`): in-process async task that checks every 60 seconds and marks devices offline after 120 seconds without a heartbeat. This is lightweight heartbeat tracking only -- it does not restart processes.

### Process watchdog (`watchdog_process.py`)

A separate, independent process that monitors the CMS backend and browser player from the outside. It has zero imports from `app/` -- uses only stdlib + PyYAML -- so it keeps running even if the main application crashes.

The process watchdog is installed automatically on all platforms (systemd service on Pi/Linux, launchd agent on macOS, startup shortcut on Windows). In Docker, it exits immediately -- Docker's own healthcheck and restart policy handle recovery.

| Feature | Details |
|---------|---------|
| **CMS health check** | HTTP GET `/health` every 30s (configurable). Restarts the CMS after N consecutive failures (default 3) |
| **Browser process check** | Finds cog/chromium/chrome PID via `/proc` (Linux), `pgrep` (macOS), or PowerShell (Windows). Restarts after N consecutive failures (default 2) |
| **Browser memory limit** | Reads RSS memory of the browser process. Kills and restarts the browser if RSS exceeds `browser_memory_limit_mb` (default 1024 MB) |
| **Scheduled weekly reboot** | Full OS reboot via `sudo systemctl reboot` (Linux/Pi only). Configured by day-of-week and hour. Disabled by default. Safety net against slow kernel/GPU memory accumulation that per-process restarts cannot catch |
| **Memory snapshots** | Periodic RSS report for all TinySignage processes (CMS, browser, WPE sub-processes, GPIO bridge, watchdog self) plus system memory. Default interval: 30 minutes |
| **Platform detection** | Auto-detects docker, pi, linux, macos, or windows. Adapts process discovery and restart commands per platform |
| **Mode detection** | Auto-detects whether to monitor CMS, player, or both based on installed services/files. Override with `watchdog.mode` in config |
| **Process restart** | Linux/Pi: SIGTERM, let systemd re-launch. macOS: SIGTERM, let launchd re-launch. Windows: PowerShell `Stop-Process` filtered by command line (targets only signage processes), then re-launches via batch file or `launcher.py` |

Configuration is in the `watchdog:` section of `config.yaml` -- see [Configuration](configuration.md#watchdog).

### Error and log reporting

TinySignage follows a zero-silent-failure policy with two reporting channels:

| Channel | Backend | CMS Frontend | Player |
|---------|---------|-------------|--------|
| **User-facing** | HTTP error responses | Toast notifications via `errorBus` | Status indicator + debug overlay |
| **Debug log** | `logs/tinysignage.log` (rotating) + `logs/errors.jsonl` (ERROR+ with stack traces) | `console.error/warn` with `[ComponentName]` prefix | `PlayerLog` ring buffer in localStorage (uploaded to server on heartbeat) |

The **audit log** (`audit_logs` table) is separate from error logging -- it records who changed what (successful mutations, failed login attempts) for admin review, not debug detail.

Server-side error logs are viewable at `GET /api/logs/errors` (admin). Player logs are viewable at `GET /api/devices/{id}/player-log` (viewer+) or via the Ctrl+Shift+D debug overlay on the player.

---

## Frontend structure

### Player (`app/static/`)

Three files:

- `player.html` -- two overlay layers, zones container, splash screen, registration UI
- `player.js` -- polling, heartbeat, capability reporting, localStorage cache, playback timer, multi-zone engine, override handling, `PlayerLog` persistent ring buffer (200 entries, uploaded to server on heartbeat), debug overlay (Ctrl+Shift+D)
- `player.css` -- fullscreen layout, CSS transitions, GPU compositing, zone positioning, debug overlay styles

The player has zero build dependencies. It is vanilla HTML, CSS, and JavaScript.

### CMS (`cms/`)

Vue 3 + PrimeVue (Aura dark theme) single-page application:

- 14 views covering all CMS functionality
- 4 reusable components (AssetCard, PlaylistRow, UploadZone, MiniPlayer)
- Fetch-based API client with automatic Bearer token injection and `errorBus` for toast notifications on API errors
- Client-side route guards for authentication and admin-only pages

Built with Vite. During development, Vite proxies API and media requests to the backend.

---

## Dependencies

### Python (`requirements.txt`)

| Package | Version | Purpose |
|---------|---------|---------|
| FastAPI | 0.115.6 | Web framework |
| uvicorn | 0.34.0 | ASGI server |
| SQLAlchemy | 2.0.36 | Database ORM (async mode) |
| aiosqlite | 0.21.0 | SQLite async driver (pinned -- 0.22+ has Windows bugs) |
| python-multipart | 0.0.18 | File upload parsing |
| PyYAML | 6.0.2 | Config file parsing |
| Pillow | 11.1.0 | Image thumbnail generation |

**Optional**: FFmpeg (video thumbnails), Alembic (migrations, installed via SQLAlchemy), bcrypt (password hashing).

No native extensions except Pillow. No system daemons. No C libraries beyond what Python and Pillow require.

### Docker image

Two-stage build:
1. **Node 22-slim** compiles the Vue CMS into static files
2. **Python 3.11-slim** runs the backend with `curl` (health check) and `ffmpeg` (video thumbnails)

Final image size is minimal. The Dockerfile is 35 lines. The compose file is 13 lines.

---

## Schema overview

The database uses 17 tables managed by 17 Alembic migrations. Key relationships:

- Playlists contain PlaylistItems, which reference Assets
- Devices reference a Playlist and optionally a Layout
- Layouts contain LayoutZones, each referencing a Playlist
- Schedules reference a Playlist and target a Device, DeviceGroup, or "all"
- Overrides target a Device, DeviceGroup, or "all"
- ApiTokens reference a User and optionally a Device
- Assets have Tags via the AssetTag junction table
- Devices belong to DeviceGroups via DeviceGroupMembership
- TriggerFlows contain TriggerBranches, which link source and target Playlists
- Playlists optionally reference a TriggerFlow for interactive trigger behavior

All primary keys are UUID4 strings. All timestamps are naive UTC datetimes.

### Interactive trigger system

The trigger system is a layer above playlists. A TriggerFlow links multiple playlists via trigger-driven transitions (keyboard, touch zones, GPIO, webhooks, timeout, loop count). The player's TriggerEngine evaluates triggers client-side for instant response, with webhooks handled via server-side timestamp comparison on each poll. See [Interactive Triggers](interactive-triggers.md) for details.

---

## See also

- [API Reference](api-reference.md) -- All endpoints
- [Player Behavior](player-behavior.md) -- Player-side technical details
- [Configuration](configuration.md) -- config.yaml reference
- [Contributing](../CONTRIBUTING.md) -- Development setup and conventions
