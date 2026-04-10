# Installing TinySignage on Raspberry Pi

Dedicated kiosk display -- boots straight into fullscreen playback, managed via the CMS from any browser on the network.

> **First time?** See the [Getting Started](getting-started.md) guide for a complete walkthrough from install to content.

---

## Requirements

- Raspberry Pi 4 or 5 (2GB+ RAM)
- **Raspberry Pi OS Lite (Bookworm or later)** — recommended for dedicated signage
- Network connection (Ethernet or WiFi)
- HDMI display (not needed for CMS-only installs)

> **Why Lite?** Pi OS Lite has no desktop environment, which means faster boot times, lower memory usage, and fewer unnecessary services — ideal for a single-purpose signage display. The installer sets up `cog` (WPE WebKit), a lightweight kiosk browser that composites directly on the GPU without a full desktop.
>
> Pi OS with Desktop also works — the installer detects which variant you're running and adjusts automatically.

## Install

Update the system first — a fresh Pi OS image can be months behind on security patches and package versions:

```bash
sudo apt update && sudo apt upgrade -y
```

Then install TinySignage:

```bash
sudo apt install -y git python3
git clone https://github.com/freewarefocus/tinysignage.git
cd tinysignage
sudo python3 install.py
```

### Choosing what to install

The installer asks what you'd like to install:

1. **Everything (CMS + Player)** — manages and displays content on the same device. Best for a single Pi behind a screen (e.g. a coffee shop menu board).
2. **CMS only** — runs the server that manages playlists, schedules, and media. Install this on one device, then point your player screens at it.
3. **Player only** — turns this Pi into a display that connects to a CMS running elsewhere. Much lighter -- no Python venv, no database, just Chromium in kiosk mode.

After choosing, the installer asks for a **display name** (e.g. "Lobby TV"). This name is used both as the player's friendly name in the CMS and as the `.local` network address (sanitized to `lobby-tv.local`). For multiple displays, just give each Pi a different name.

For player-only installs, you'll also be asked for the **CMS server address** (e.g. `http://museum-cms.local:8080`).

### Scripted/headless installs

```bash
# Everything on one device (default)
sudo python3 install.py --non-interactive --display-name "Lobby TV"

# CMS server only
sudo python3 install.py --mode cms --non-interactive --display-name "Signage Server"

# Player-only display pointing at a remote CMS
sudo python3 install.py --mode player --non-interactive --display-name "Gallery 3" \
    --server-url http://museum-cms.local:8080
```

### Typical setups

**One screen, one Pi** (coffee shop, small office):
Install "Everything" on a single Pi. The CMS and player both run on the same device.

**Multiple screens, one central CMS** (museum, hotel, school):
Install "CMS only" on one Pi (or any server). Install "Player only" on each display Pi, pointing them all at the CMS server address.

## Reboot

The installer enables services to start on boot automatically. Reboot to apply the hostname, GPU memory, and watchdog changes:

```bash
sudo reboot
```

After reboot:

- **Everything mode**: CMS at `http://<hostname>.local:8080/cms`, player launches on the Pi's display automatically
- **CMS-only mode**: CMS at `http://<hostname>.local:8080/cms` — no local player
- **Player-only mode**: Chromium launches in kiosk mode, connected to the remote CMS

## What gets installed

What the installer sets up depends on the mode:

| | Everything | CMS Only | Player Only |
|---|---|---|---|
| Python venv + pip dependencies | Yes | Yes | No |
| SQLite database | Yes | Yes | No |
| ffmpeg (video thumbnails) | Yes | Yes | No |
| Kiosk browser (cog/WPE preferred, Chromium fallback) | Yes | No | Yes |
| Transparent cursor theme | Yes | No | Yes |
| `signage-app` systemd service | Yes | Yes | No |
| `signage-player` systemd service | Yes | No | Yes |

All modes install: `python3`, `avahi-daemon` (mDNS), `curl`. A dedicated `tinysignage` service user is created in every mode — no application code runs as root.

Player-only installs are very lightweight: no Python virtual environment, no database, no pip dependencies. The launcher script uses system `python3` and `python3-yaml` (installed via apt).

Systemd units for the CMS backend include security hardening: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, and a 512MB memory ceiling. The CMS frontend is pre-built and included in the repo — no Node.js required.

## Updating

```bash
sudo python3 /opt/tinysignage/install.py --update
```

`--update` pulls the latest code, reinstalls dependencies, runs database migrations, and restarts services. The player reconnects automatically within 30 seconds.

If the automatic `git pull` fails (for example, the clone uses SSH and the service user has no keys), `--update` prints the git error and continues with the dependency/database/restart steps. To skip git entirely:

```bash
sudo python3 /opt/tinysignage/install.py --update --no-pull
```

## Resetting the player

If you entered the wrong server URL during registration, reset the player to return to the registration screen:

```bash
sudo systemctl stop signage-player
python3 /opt/tinysignage/launcher.py --reset
sudo systemctl restart signage-player
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

**Important:** TinySignage stores its database and uploaded media in `/opt/tinysignage/db/` and `/opt/tinysignage/media/`. These directories must remain writable. After enabling OverlayFS, either:
- Keep the data directories on a separate writable partition, or
- Bind-mount them to a tmpfs or USB drive

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
