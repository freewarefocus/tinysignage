# Installing TinySignage on Raspberry Pi

Dedicated kiosk display — boots straight into fullscreen playback, managed via the CMS from any browser on the network.

---

## Requirements

- Raspberry Pi 4 or 5 (2GB+ RAM)
- Raspberry Pi OS (Bookworm or later)
- Network connection (Ethernet or WiFi)
- HDMI display

## Install

```bash
git clone https://github.com/freewarefocus/tinysignage.git
cd tinysignage
bash install/install.sh
```

This runs two shell scripts — both readable in `install/` before you execute them:

| Script | What it does |
|--------|-------------|
| `install/01-system.sh` | Installs apt packages, creates a dedicated `tinysignage` service user, enables mDNS (`tinysignage.local`), installs systemd units, sets GPU memory on Pi |
| `install/02-app.sh` | Creates a Python venv, installs pip dependencies, creates directories, generates a random `SECRET_KEY`, initializes the database |

## Start the services

```bash
sudo systemctl start signage-app signage-player
```

- **CMS**: `http://tinysignage.local:8080/cms` (from any device on the network)
- **Player**: Launches in kiosk mode on the Pi's display automatically

To start on boot:

```bash
sudo systemctl enable signage-app signage-player
```

## What gets installed

System packages via apt: `python3`, `python3-venv`, `chromium-browser`, `ffmpeg`, `avahi-daemon`, `curl`.

A dedicated `tinysignage` service user is created — no application code runs as root. Systemd units include security hardening: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, and a 512MB memory ceiling.

## Updating

```bash
cd /path/to/tinysignage
git pull
sudo systemctl restart signage-app
```

The player reconnects automatically within 30 seconds.

## Troubleshooting

**Player shows a black screen after boot:**
The backend may still be starting. The player retries every 30 seconds — give it a minute. Check the backend:

```bash
sudo systemctl status signage-app
```

**Can't reach `tinysignage.local`:**
mDNS (Avahi) may not be running, or your client device doesn't support `.local` discovery. Use the Pi's IP address instead:

```bash
hostname -I
```

**Video plays but no thumbnail in the CMS:**
FFmpeg is required for video thumbnails. Verify it's installed:

```bash
ffmpeg -version
```

If missing: `sudo apt install ffmpeg`
