# Installing TinySignage on Windows

Run TinySignage as a local application on Windows 10 or 11. Good for a PC behind a monitor, a spare laptop, or development.

> **First time?** See the [Getting Started](getting-started.md) guide for a complete walkthrough from install to content.

---

## Requirements

- Windows 10 or 11
- Python 3.11+ ([python.org](https://www.python.org/downloads/) — check "Add to PATH" during install)
- Git ([git-scm.com](https://git-scm.com/downloads/win))

## Install

Open PowerShell or Command Prompt:

```powershell
git clone https://github.com/freewarefocus/tinysignage.git
cd tinysignage
python install.py
```

The installer asks what to install:

1. **Everything (CMS + Player)** — manages and displays content on this machine.
2. **CMS only** — runs the content management server. Point player devices at this machine.
3. **Player only** — configures this machine to display content from a CMS running elsewhere. You'll be asked for the CMS server address.

For "Everything" and "CMS only", the installer creates a virtual environment, installs dependencies, initializes the database, and offers to generate a `start-tinysignage.bat` for easy startup and an optional Startup folder shortcut.

For scripted installs:

```powershell
# CMS server only
python install.py --mode cms --non-interactive

# Player only, pointing at a remote CMS
python install.py --mode player --server-url http://192.168.1.50:8080
```

## Run

If you didn't set up the batch file during install, start manually:

```powershell
venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

- **Setup wizard**: `http://localhost:8080/setup` (first run only)
- **CMS**: `http://localhost:8080/cms`
- **Player**: `http://localhost:8080/player` — open in a browser and press **F11** for fullscreen

## Optional: FFmpeg for video thumbnails

Video uploads work without FFmpeg — you just won't get thumbnail previews in the CMS.

Install via [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/):

```powershell
winget install Gyan.FFmpeg
```

Or download from [ffmpeg.org](https://ffmpeg.org/download.html) and add the `bin/` folder to your PATH.

Verify:

```powershell
ffmpeg -version
```

## Optional: Run on startup

If you skipped startup setup during install, you can re-run `python install.py` to generate the batch file and startup shortcut.

To also open the player in kiosk mode, add this line to `start-tinysignage.bat` after the uvicorn line (in a separate `start` command):

```batch
start "" "chrome" --kiosk http://localhost:8080/player
```

## Optional: Docker

If you prefer Docker, install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and run:

```powershell
git clone https://github.com/freewarefocus/tinysignage.git
cd tinysignage
docker compose up -d
```

Same URLs. Data lives in `./media` and `./db` next to the compose file.

## Updating

```powershell
cd path\to\tinysignage
git pull
python install.py --update
```

This reinstalls dependencies and runs database migrations. Restart the application afterward.

## Resetting the player

If you entered the wrong server URL during registration, reset the player to return to the registration screen:

```powershell
python launcher.py --reset
```

Make sure the browser is closed first -- Windows locks open files and the reset will fail if Chrome is still running.

---

## Troubleshooting

**`python` is not recognized:**
Python wasn't added to PATH during install. Reinstall from [python.org](https://www.python.org/downloads/) and check "Add Python to PATH", or use the full path (e.g., `C:\Python311\python.exe`).

**Port 8080 is already in use:**
Another application is using port 8080. Either stop that application or use a different port:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 9090
```

**Player won't go fullscreen:**
Press **F11** in your browser. For a dedicated display, use Chrome's kiosk mode:

```powershell
chrome --kiosk http://localhost:8080/player
```

**Firewall prompt on first run:**
Windows Firewall may ask to allow Python/uvicorn through the firewall. Allow it on "Private networks" if you want to access the CMS from other devices on your network.

---

## See also

- [Getting Started](getting-started.md) -- Zero-to-content walkthrough
- [Configuration](configuration.md) -- config.yaml reference
- [Managing Media](managing-media.md) -- Uploading and organizing content
- [Troubleshooting](troubleshooting.md) -- More common issues and fixes
