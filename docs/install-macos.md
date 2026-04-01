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

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

## Run

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

To launch TinySignage automatically when you log in, create a Launch Agent.

1. Create the plist file:

```bash
cat > ~/Library/LaunchAgents/com.tinysignage.app.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tinysignage.app</string>
    <key>WorkingDirectory</key>
    <string>/path/to/tinysignage</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/tinysignage/venv/bin/uvicorn</string>
        <string>app.main:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8080</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/tinysignage.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/tinysignage.err</string>
</dict>
</plist>
EOF
```

2. Edit the file and replace `/path/to/tinysignage` with your actual install path.

3. Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.tinysignage.app.plist
```

To stop and unload:

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
source venv/bin/activate
pip install -r requirements.txt
```

Then restart the application (or `launchctl` will restart it automatically if using the Launch Agent with `KeepAlive`).

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
