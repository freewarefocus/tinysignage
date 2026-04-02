# Installing TinySignage on Raspberry Pi

Dedicated kiosk display -- boots straight into fullscreen playback, managed via the CMS from any browser on the network.

> **First time?** See the [Getting Started](getting-started.md) guide for a complete walkthrough from install to content.

---

## Requirements

- Raspberry Pi 4 or 5 (2GB+ RAM)
- **Raspberry Pi OS Lite (Bookworm or later)** — recommended for dedicated signage
- Network connection (Ethernet or WiFi)
- HDMI display

> **Why Lite?** Pi OS Lite has no desktop environment, which means faster boot times, lower memory usage, and fewer unnecessary services — ideal for a single-purpose signage display. The installer sets up a minimal kiosk compositor (`cage`) that runs Chromium fullscreen without a full desktop.
>
> Pi OS with Desktop also works — the installer detects which variant you're running and adjusts automatically.

## Install

Update the system first — a fresh Pi OS image can be months behind on security patches and package versions:

```bash
sudo apt update && sudo apt upgrade -y
```

Then install TinySignage:

```bash
sudo apt install -y git
git clone https://github.com/freewarefocus/tinysignage.git
cd tinysignage
bash install/install.sh
```

The installer will ask you for a **display name** (e.g. "Lobby TV"). This name is used both as the player's friendly name in the CMS and as the `.local` network address (sanitized to `lobby-tv.local`). For multiple displays, just give each Pi a different name.

The installer then automatically moves the project to `/opt/tinysignage` so the service user can access it.

This runs two shell scripts — both readable in `install/` before you execute them:

| Script | What it does |
|--------|-------------|
| `install/01-system.sh` | Moves project to `/opt/tinysignage`, installs apt packages, creates a dedicated `tinysignage` service user, sets hostname, enables mDNS (`.local`), installs systemd units, sets GPU memory on Pi |
| `install/02-app.sh` | Creates a Python venv, installs pip dependencies, builds the CMS frontend, creates directories, generates a random `SECRET_KEY`, initializes the database |

## Reboot

The installer enables both services to start on boot automatically. Reboot to apply the hostname, GPU memory, and watchdog changes:

```bash
sudo reboot
```

After reboot, both services start automatically:

- **CMS**: `http://<hostname>.local:8080/cms` (from any device on the network)
- **Player**: Launches in kiosk mode on the Pi's display automatically, auto-pairs with the server (no manual registration needed)

## What gets installed

System packages via apt: `python3`, `python3-venv`, `nodejs`, `npm`, `chromium`, `ffmpeg`, `avahi-daemon`, `curl`. On Pi OS Lite, the installer also adds `cage` (a lightweight Wayland kiosk compositor) to run Chromium fullscreen without a desktop environment. Node.js is used at install time to build the CMS frontend.

A dedicated `tinysignage` service user is created — no application code runs as root. Systemd units include security hardening: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, and a 512MB memory ceiling.

## Updating

```bash
cd /opt/tinysignage
sudo -u tinysignage git pull
sudo systemctl restart signage-app
```

The player reconnects automatically within 30 seconds.

## Resetting the player

If you entered the wrong server URL during registration, reset the player to return to the registration screen:

```bash
sudo systemctl stop signage-player-lite
python3 /opt/tinysignage/launcher.py --reset
sudo systemctl restart signage-player-lite
```

---

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

---

## Production Hardening (24/7 Displays)

If the Pi will run unattended (shop window, lobby, menu board), these steps reduce the chance of needing a physical visit.

### Hardware watchdog (enabled by installer)

The installer enables the Pi's built-in hardware watchdog (`bcm2835_wdt`). If the OS completely freezes — kernel panic, OOM lockup — the watchdog chip reboots the Pi automatically within ~14 seconds. The systemd service also has a `WatchdogSec=120` setting that restarts the player if Chromium becomes unresponsive.

No action needed — the installer configures both automatically.

### Read-only root filesystem (OverlayFS)

SD card corruption is the #1 cause of Pi signage failures. Making the root filesystem read-only prevents writes from wearing out the card or leaving corrupted files after a power loss.

Enable it via `raspi-config`:

```bash
sudo raspi-config
# Performance Options → Overlay File System → Enable
```

**Important:** TinySignage stores its database and uploaded media in `/home/tinysignage/TinySignage/data/`. This directory must remain writable. After enabling OverlayFS, either:
- Keep the data directory on a separate writable partition, or
- Bind-mount the data directory to a tmpfs or USB drive

If you just need basic protection and don't want to deal with partition layouts, skip OverlayFS and use a high-endurance SD card (see below).

### SD card selection

Standard consumer SD cards are not designed for continuous writes. Use an endurance-rated card:

- **SanDisk High Endurance** (recommended) — rated for 20,000+ hours of continuous recording
- **Samsung PRO Endurance** — similar rating, widely available

For the most reliable setup, boot from an **NVMe SSD** via USB or the Pi 5's M.2 HAT. This eliminates SD card failure entirely.

### Power supply

Use a **regulated 5V/3A power supply** (the official Raspberry Pi PSU or equivalent). Phone chargers and cheap USB supplies cause undervoltage that corrupts the SD card and crashes the GPU. The Pi's lightning bolt icon (⚡) on screen means the supply is inadequate.

### Cooling

A Pi running 24/7 with Chromium and GPU compositing will thermal throttle without cooling. At minimum, use a **passive heatsink case** (e.g., Flirc, Argon NEO). Active cooling (fan) is not required for signage workloads but doesn't hurt.

---

## See also

- [Getting Started](getting-started.md) -- Zero-to-content walkthrough
- [Configuration](configuration.md) -- config.yaml reference
- [Managing Media](managing-media.md) -- Uploading and organizing content
- [Troubleshooting](troubleshooting.md) -- More common issues and fixes
