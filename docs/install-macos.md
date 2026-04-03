# Installing TinySignage on macOS

Run TinySignage as a local application on macOS. Good for a Mac Mini behind a display, a spare laptop, or development.

> **First time?** See the [Getting Started](getting-started.md) guide for a complete walkthrough from install to content.

---

## Requirements

- macOS 12 (Monterey) or later
- Python 3.11+
- Git (included with Xcode Command Line Tools)

## Install Python

macOS ships with an older Python or none at all. Install a current version via [Homebrew](https://brew.sh/):

```bash
brew install python@3.11
```

Or download from [python.org](https://www.python.org/downloads/).

Verify:

```bash
python3 --version
```

## Install

```bash
git clone https://github.com/freewarefocus/tinysignage.git
cd tinysignage
python3 install.py
```

The installer asks what to install:

1. **Everything (CMS + Player)** — manages and displays content on this Mac.
2. **CMS only** — runs the content management server. Point player devices at this machine.
3. **Player only** — configures this Mac to display content from a CMS running elsewhere. You'll be asked for the CMS server address.

For "Everything" and "CMS only", the installer creates a virtual environment, installs dependencies, initializes the database, and offers to generate a launchd plist for auto-start.

For scripted installs:

```bash
# CMS server only
python3 install.py --mode cms --non-interactive

# Player only, pointing at a remote CMS
python3 install.py --mode player --server-url http://192.168.1.50:8080
```

## Run

If you didn't set up launchd during install, start manually:

```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

- **Setup wizard**: `http://localhost:8080/setup` (first run only)
- **CMS**: `http://localhost:8080/cms`
- **Player**: `http://localhost:8080/player` — open in a browser and press **Ctrl+Cmd+F** for fullscreen

## Optional: FFmpeg for video thumbnails

Video uploads work without FFmpeg — you just won't get thumbnail previews in the CMS.

```bash
brew install ffmpeg
```

Verify:

```bash
ffmpeg -version
```

## Optional: Run on startup with launchd

If you skipped launchd setup during install, you can generate it later by re-running `python3 install.py`.

To stop and unload an existing plist:

```bash
launchctl unload ~/Library/LaunchAgents/com.tinysignage.app.plist
```

## Optional: Docker

If you prefer Docker, install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/) and run:

```bash
git clone https://github.com/freewarefocus/tinysignage.git
cd tinysignage
docker compose up -d
```

Same URLs. Data lives in `./media` and `./db` next to the compose file.

## Updating

```bash
cd /path/to/tinysignage
git pull
python3 install.py --update
```

This reinstalls dependencies and runs database migrations. If using the Launch Agent with `KeepAlive`, the app restarts automatically.

## Resetting the player

If you entered the wrong server URL during registration, reset the player to return to the registration screen:

```bash
python3 launcher.py --reset
```

---

## Troubleshooting

**`python3` not found after Homebrew install:**
Homebrew may not be in your PATH. Run:

```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
```

Add that line to your `~/.zshrc` to make it permanent.

**Port 8080 is already in use:**
Find what's using it:

```bash
lsof -i :8080
```

Either stop that process or use a different port:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 9090
```

**macOS firewall prompt:**
macOS may ask to allow incoming connections. Click "Allow" if you want to access the CMS from other devices on your network.

**Player won't go fullscreen:**
In Safari, use **Ctrl+Cmd+F**. In Chrome, use **Cmd+Ctrl+F** or **F11** (if your keyboard has function keys). For a dedicated display, use Chrome's kiosk mode:

```bash
open -a "Google Chrome" --args --kiosk http://localhost:8080/player
```

---

## See also

- [Getting Started](getting-started.md) -- Zero-to-content walkthrough
- [Configuration](configuration.md) -- config.yaml reference
- [Managing Media](managing-media.md) -- Uploading and organizing content
- [Troubleshooting](troubleshooting.md) -- More common issues and fixes
