# TinySignage

Self-contained digital signage player. One Python process, one browser tab, zero cloud dependencies.

Upload images and videos through a web-based CMS, arrange them into a playlist, and a fullscreen browser player loops through them with smooth crossfade transitions. Everything runs on a single machine — a Raspberry Pi under a TV, an old PC behind a monitor, or a Docker container on whatever you have.

---

## What it does

- **Drag-and-drop media management** — upload images (JPG, PNG, WebP, GIF) and videos (MP4, WebM) with auto-generated thumbnails
- **Playlist editor** — drag to reorder, per-item duration, add/remove without deleting source files
- **Smooth playback** — dual-layer CSS crossfade transitions between items, GPU-composited
- **Offline resilient** — player caches the playlist locally and keeps playing indefinitely if the network drops
- **Web URL support** — embed any webpage as a playlist item alongside images and videos
- **Device health monitoring** — heartbeat tracking, clock drift detection, timezone mismatch warnings
- **First-boot setup wizard** — browser-based setup at first launch, no config files to hand-edit
- **Runs anywhere** — Raspberry Pi, Linux, macOS, Windows, Docker

## What it doesn't do

- No cloud account required. No sign-up. No telemetry. No phoning home.
- No online activation, no license key, no "connect to our servers to unlock your device." It works out of the box on a network with no internet at all.
- No feature gates or crippled "free tier" — this is the complete application.

---

## Quick start

```bash
git clone https://github.com/freewarefocus/tinysignage.git
cd tinysignage
```

Then pick your path:

| Method | Command | Guide |
|--------|---------|-------|
| **Docker** | `docker compose up -d` | — |
| **Python** | `pip install -r requirements.txt` then `uvicorn app.main:app --host 0.0.0.0 --port 8080` | — |
| **Raspberry Pi** | `bash install/install.sh` | [Full guide](docs/install-raspberry-pi.md) |
| **Windows** | Same as Python, see guide for details | [Full guide](docs/install-windows.md) |
| **macOS** | Same as Python, see guide for details | [Full guide](docs/install-macos.md) |

Open `http://localhost:8080/setup` to name your device, then `/cms` to manage content and `/player` for the display.

Docker data lives in `./media` and `./db` next to the compose file — visible, portable, easy to back up.

---

## How it works

```
Browser (player)  ── poll every 30s ──>  FastAPI backend  ──>  SQLite
Browser (CMS)     ── REST API ────────>       │
                                          Watchdog (health monitoring)
```

The architecture is deliberately simple:

- **Backend**: A single FastAPI process serves the API, the CMS, the player page, and media files. SQLite is the only database — no Redis, no Postgres, no message queue.
- **Player**: A static HTML page that polls the backend every 30 seconds. If the playlist hash hasn't changed, it does nothing. If the hash changed, it fetches the new playlist and swaps content at the next transition. The player manages its own playback timer — no server-push, no WebSocket.
- **Offline behavior**: The player caches the current playlist in `localStorage` and media files via browser HTTP cache. If the backend goes down or the network drops, the player keeps looping its cached content indefinitely. When connectivity returns, it picks up changes within 30–60 seconds.
- **CMS**: A Vue 3 + PrimeVue single-page app. Thumbnail grid for media, drag-and-drop playlist editing, device status, display settings. Built once during Docker build or `npm run build` — served as static files by the backend.

### Why polling instead of WebSocket

For digital signage, a 30-second update delay is invisible to viewers. Polling with local cache means the player survives network outages indefinitely — no reconnect logic, no state synchronization, no persistent connections consuming server resources. The player and backend are fully decoupled.

---

## What gets installed

TinySignage has a small, focused dependency list. No native extensions, no compiled C libraries (except Pillow for image thumbnails), no system daemons beyond what you start.

### Python dependencies (`requirements.txt`)

| Package | Version | Purpose |
|---------|---------|---------|
| FastAPI | 0.115.6 | Web framework |
| uvicorn | 0.34.0 | ASGI server |
| SQLAlchemy | 2.0.36 | Database ORM (async mode) |
| aiosqlite | 0.21.0 | SQLite async driver |
| python-multipart | 0.0.18 | File upload parsing |
| PyYAML | 6.0.2 | Config file parsing |
| Pillow | 11.1.0 | Image thumbnail generation |

**Optional**: FFmpeg (for video thumbnails). If not installed, video uploads work fine — you just don't get thumbnail previews.

### What Docker adds

The Docker image is a two-stage build:

1. **Node 22** compiles the Vue CMS into static files
2. **Python 3.11-slim** runs the backend

The final image contains Python, the pip dependencies above, `curl` (for the health check), and `ffmpeg` (for video thumbnails). The [Dockerfile](Dockerfile) is 34 lines — read it. The [docker-compose.yml](docker-compose.yml) is 11 lines. Media and database are bind-mounted volumes, not hidden inside the container.

### What the Pi installer adds

The install scripts are in `install/` and do exactly what they say in their comments. See the [Raspberry Pi install guide](docs/install-raspberry-pi.md) for details.

---

## Configuration

`config.yaml` in the project root:

```yaml
server:
  host: 0.0.0.0
  port: 8080
storage:
  media_dir: ./media
  db_path: ./db/signage.db
display:
  transition_duration: 1.0   # seconds
  transition_type: fade       # "fade" or "cut"
  default_duration: 10        # seconds per image
player:
  browser: auto
  kiosk: true
```

Display settings (transition type, duration, shuffle) can also be changed from the CMS settings page at runtime.

---

## Project layout

```
TinySignage/
├── app/
│   ├── main.py             # FastAPI app, startup, route mounts
│   ├── models.py           # SQLAlchemy models
│   ├── database.py         # Async engine, migrations, seeding
│   ├── schemas.py          # Pydantic request/response schemas
│   ├── scheduler.py        # Playlist cycling logic
│   ├── watchdog.py         # Device health monitoring
│   ├── media.py            # Thumbnail generation, content hashing
│   ├── api/                # REST API route modules
│   │   ├── assets.py       # Media CRUD, upload, replace, duplicate
│   │   ├── playlists.py    # Playlist CRUD, item management
│   │   ├── devices.py      # Device registration, polling endpoint
│   │   ├── health.py       # Heartbeat, health dashboard
│   │   ├── settings.py     # Display settings, playback control
│   │   └── setup.py        # First-boot wizard
│   └── static/             # Player HTML/JS/CSS
├── cms/                    # Vue 3 + PrimeVue CMS source
├── install/                # Pi/Linux install scripts (readable)
├── systemd/                # Systemd service units
├── media/                  # Uploaded files (gitignored)
├── db/                     # SQLite database (gitignored)
├── config.yaml             # User configuration
├── Dockerfile              # Multi-stage build (34 lines)
├── docker-compose.yml      # Single service (11 lines)
└── requirements.txt        # Python dependencies (7 packages)
```

---

## Resilience

TinySignage is designed to recover from failures without human intervention:

| Layer | What happens | Recovery |
|-------|-------------|----------|
| Network drops | Player continues from local cache | Automatic — picks up changes when network returns |
| Backend crashes | Docker restarts the container; systemd restarts the service | Automatic within seconds |
| Memory leak | Docker enforces 512MB ceiling; systemd enforces `MemoryMax` | Process killed and restarted cleanly |
| Player tab hangs | Watchdog detects missed heartbeats | Escalates through recovery tiers |

The health dashboard at `/api/health/dashboard` surfaces device status, clock drift, timezone mismatches, and missed heartbeats in plain language — not raw diagnostics.

---

## Hardware

TinySignage does not sell hardware and does not require proprietary devices. It runs on anything with a browser and a screen.

**Tested reference hardware** (Raspberry Pi 5):

| Component | Approx. cost |
|-----------|-------------|
| Raspberry Pi 5 (4GB) | ~$60 |
| Power supply | ~$12 |
| Case with heatsink | ~$12 |
| Micro HDMI cable | ~$8 |
| 32GB SD card | ~$9 |
| **Total** | **~$100** |

Also works on: any x86 mini PC, retired office PC, Mac, Linux server, or a Docker host. If it can run Python and a browser, or Docker, it can run TinySignage.

---

## Development

### Backend only

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8080
```

### CMS frontend (hot reload)

```bash
cd cms
npm install
npm run dev
```

Vite proxies `/api/*` and `/media/*` to `localhost:8080` during development.

### Full Docker build

```bash
docker compose up --build
```

---

## License

TinySignage is licensed under the [GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.html) (AGPL-3.0).

You are free to use, modify, and distribute TinySignage. If you run a modified version as a network service, the AGPL requires you to make your source code available to users of that service. Self-hosting for your own displays — modified or not — requires no special action beyond retaining the license notice.
