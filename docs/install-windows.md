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

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

## Run

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

To launch TinySignage automatically when you log in:

1. Create a batch file (e.g., `start-tinysignage.bat`) in the project folder:

```batch
@echo off
cd /d "%~dp0"
call venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

2. Press **Win + R**, type `shell:startup`, press Enter
3. Create a shortcut to `start-tinysignage.bat` in the Startup folder

To also open the player in kiosk mode, add this line to the batch file after the uvicorn line (in a separate `start` command), or create a second shortcut:

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
venv\Scripts\activate
pip install -r requirements.txt
```

Then restart the application.

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

**Need to reconfigure the player?**
Add `?reset` to the player URL to clear stored credentials and return to the registration screen:

```
http://localhost:8080/player?reset
```

---

## See also

- [Getting Started](getting-started.md) -- Zero-to-content walkthrough
- [Configuration](configuration.md) -- config.yaml reference
- [Managing Media](managing-media.md) -- Uploading and organizing content
- [Troubleshooting](troubleshooting.md) -- More common issues and fixes
