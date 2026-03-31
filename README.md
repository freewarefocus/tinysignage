# TinySignage

Self-contained digital signage player. One Python process, one browser tab, zero cloud dependencies.

Upload images and videos through a web CMS, arrange them into playlists, and a fullscreen browser player loops through them with smooth fade transitions. Everything runs on a single machine -- a Raspberry Pi under a TV, an old PC behind a monitor, or a Docker container on whatever you have.

<!-- TODO: Add screenshot or demo GIF before v1.0 ships -->
<!-- ![TinySignage CMS and Player](docs/images/tinysignage-overview.png) -->

## What it does

### Core features

- **Drag-and-drop media management** -- upload images, videos, web URLs, and HTML snippets
- **Playlist editor** -- drag to reorder, per-item duration, shuffle, preview
- **Smooth playback** -- dual-layer CSS fade transitions, GPU-composited
- **Offline resilient** -- player caches everything locally and keeps playing if the network drops
- **First-boot setup wizard** -- browser-based, no config files to hand-edit
- **Runs anywhere** -- Raspberry Pi, Linux, macOS, Windows, Docker

### Multi-screen and operations

- **Multi-device management** -- register devices, monitor health, group them, bulk-assign playlists
- **Scheduling** -- time windows, day-of-week, RRULE recurrence, priority system
- **Multi-zone layouts** -- split screens into positioned zones with independent playlists
- **Interactive triggers** -- keyboard, touch zones, GPIO buttons, webhooks, timeouts -- link playlists with trigger-driven transitions for kiosks, wayfinding, and emergency alerts
- **Emergency overrides** -- instant message or playlist push to all/group/device, auto-expiry
- **Role-based access** -- admin, editor, viewer roles with API tokens
- **Structured logging** -- backend error log, player persistent log with remote retrieval, audit trail
- **Backup and restore** -- one-click ZIP export of database and media

## What it doesn't do

- No cloud account required. No sign-up. No telemetry. No phoning home.
- No online activation, no license key, no "connect to our servers to unlock your device." It works on a network with no internet at all.
- No feature gates or crippled "free tier" -- this is the complete application.

---

## Quick start

```bash
git clone https://github.com/freewarefocus/tinysignage.git
cd tinysignage
docker compose up -d
```

Open `http://localhost:8080/setup` to create your admin account, then `/cms` to manage content and `/player` for the display.

> **New here?** Follow the [Getting Started](docs/getting-started.md) guide for a full walkthrough.

| Method | Guide |
|--------|-------|
| **Docker** | [Install with Docker](docs/install-docker.md) |
| **Raspberry Pi** | [Install on Raspberry Pi](docs/install-raspberry-pi.md) |
| **Windows** | [Install on Windows](docs/install-windows.md) |
| **macOS** | [Install on macOS](docs/install-macos.md) |

---

## How it works

```
Browser (player)  -- poll every 30s -->  FastAPI backend  -->  SQLite
Browser (CMS)     -- REST API -------->       |
                                         Watchdog (health monitoring)
```

A single FastAPI process serves the API, CMS, player, and media files. SQLite is the only database. The player polls for changes, caches everything locally, and manages its own playback timer -- no WebSocket, no server-push. See [Architecture](docs/architecture.md) for details.

---

## Display, transitions, and scaling

TinySignage uses a 3-tier cascade for display settings: **global defaults** (Settings page) can be overridden per **playlist** (playlist settings panel), which can be overridden per **item** (inline controls on each playlist row). Leaving a value as "Default" at any level inherits from the tier above.

| Setting | Options | Controls |
|---------|---------|----------|
| **Effect** (transition) | Fade, Slide, Cut | How items transition in |
| **Fade time** (transition duration) | 0 -- 30 seconds | How long the transition takes |
| **Show for** (display duration) | 1 -- 3600 seconds | How long an image/HTML item stays on screen (videos play to end) |
| **Scaling** (object-fit) | Fit inside, Fill & crop, Stretch, Original size | How images and videos fill the display area |

The cascade for scaling (`object_fit`): per-item value wins, then playlist-level default, then global default. The global default is `contain` (fit inside, may show black bars).

---

## Logs and debugging

TinySignage never fails silently. Every error surfaces through two channels: user-facing notifications and a persistent debug log.

| What you need | Where to look |
|---------------|---------------|
| **Server errors** (500s, crashes) | CMS > System Log, or `logs/errors.jsonl`, or `GET /api/logs/errors` |
| **Player issues** (poll failures, asset load errors) | Press **Ctrl+Shift+D** on the player for the debug overlay, or `GET /api/devices/{id}/player-log` for remote access |
| **Who changed what** (asset deleted, playlist modified) | CMS > Audit Log, or `GET /api/audit` |
| **Failed login attempts** | Audit Log (action: `auth_failed`) |

Player logs are especially useful for headless devices (Raspberry Pi, kiosk). The player stores a 200-entry ring buffer locally and uploads it to the server on each heartbeat, so you can debug remotely without physical access.

---

## Hardware

TinySignage runs on anything with a browser and a screen. No proprietary hardware required.

**Tested reference hardware** (Raspberry Pi 5):

| Component | Approx. cost |
|-----------|-------------|
| Raspberry Pi 5 (4GB) | ~$85 |
| Power supply | ~$15 |
| Case with heatsink | ~$15 |
| Micro HDMI cable | ~$10 |
| 16GB SD card | ~$10 |
| **Total** | **~$135** |

Also works on: any x86 mini PC, retired office PC, Mac, Linux server, or Docker host.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Zero-to-content in 10 minutes |
| [Install with Docker](docs/install-docker.md) | Docker-specific setup and management |
| [Install on Raspberry Pi](docs/install-raspberry-pi.md) | Dedicated kiosk display |
| [Install on Windows](docs/install-windows.md) | Local application on Windows |
| [Install on macOS](docs/install-macos.md) | Local application on macOS |
| [Managing Media](docs/managing-media.md) | Uploads, tags, HTML snippets, widgets |
| [Playlists](docs/playlists.md) | Creation, editing, per-playlist settings |
| [Devices](docs/devices.md) | Registration, health monitoring, groups |
| [Scheduling](docs/scheduling.md) | Time windows, recurrence, priority |
| [Multi-Zone Layouts](docs/multi-zone-layouts.md) | Split-screen zone positioning |
| [Interactive Triggers](docs/interactive-triggers.md) | Keyboard, touch, GPIO, webhook triggers |
| [GPIO Bridge](docs/gpio-bridge.md) | Physical buttons on Raspberry Pi |
| [Emergency Overrides](docs/emergency-overrides.md) | Instant override push and auto-expiry |
| [Users and Permissions](docs/users-and-permissions.md) | RBAC roles, API tokens, sessions |
| [Backup and Restore](docs/backup-and-restore.md) | ZIP export and import |
| [Configuration](docs/configuration.md) | config.yaml reference |
| [Player Behavior](docs/player-behavior.md) | Polling, caching, offline mode, transitions, persistent logging |
| [Troubleshooting](docs/troubleshooting.md) | Log locations, common issues, and fixes |
| [Architecture](docs/architecture.md) | System design, project layout, dependencies |
| [API Reference](docs/api-reference.md) | All endpoints with examples |
| [Contributing](CONTRIBUTING.md) | Dev setup, conventions, PR guidelines |

---

## License

TinySignage is licensed under the [GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.html) (AGPL-3.0).

You are free to use, modify, and distribute TinySignage. If you run a modified version as a network service, the AGPL requires you to make your source code available to users of that service. Self-hosting for your own displays -- modified or not -- requires no special action beyond retaining the license notice.
