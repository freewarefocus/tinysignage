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
python -m app.server
```

- **Setup wizard**: `http://localhost:8080/setup` (first run only)
- **CMS**: `http://localhost:8080/cms`
- **Player**: `http://localhost:8080/player` — open in a browser and press **F11** for fullscreen

## Connecting remote devices (CMS-only installs)

If you installed in CMS-only mode, your player devices (Raspberry Pi, another PC, etc.) need to reach this machine over the network. Three things to get right:

### Find your IP address

Open PowerShell and run:

```powershell
ipconfig
```

Look for **IPv4 Address** under your active adapter (Wi-Fi or Ethernet). It looks like `192.168.1.50`.

You can also find it in **Settings → Network & Internet** — click your connection and look for "IPv4 address".

Your server URL for remote devices is:

```
https://<your-ip>:8080
```

For example: `https://192.168.1.50:8080`

### Allow through Windows Firewall

The first time you start TinySignage, Windows shows a firewall prompt. Click **Allow access** and make sure **Private networks** is checked.

If you missed the prompt or clicked "Cancel":

1. Open **Windows Security → Firewall & network protection**
2. Click **Allow an app through firewall**
3. Click **Change settings**, then **Allow another app → Browse**
4. Navigate to your TinySignage folder and select `venv\Scripts\python.exe`
5. Check the **Private** box, then click **OK**

> **Private vs Public networks:** Windows blocks more traffic on Public networks. If your home or office network is set to Public, remote devices won't be able to connect even with the firewall rule above. To switch: **Settings → Network & Internet → Wi-Fi** (or Ethernet) → click your network → set **Network profile type** to **Private network**.

### Browser certificate warning

When you open the CMS from another PC's browser using `https://192.168.1.50:8080`, you'll see a "Your connection is not private" warning. This is normal — TinySignage uses a self-signed certificate.

Click **Advanced → Proceed** to continue. The browser remembers your choice so you won't see the warning again.

Player devices (Raspberry Pi, kiosk PCs) handle this automatically — no action needed on their end.

## Optional: FFmpeg for video thumbnails

The installer offers to install FFmpeg automatically via winget. If you skipped that prompt or need to install it manually:

```powershell
winget install Gyan.FFmpeg
```

Or download from [ffmpeg.org](https://ffmpeg.org/download.html) and add the `bin/` folder to your PATH. Close and reopen your terminal after installing, then verify with `ffmpeg -version`. Restart TinySignage afterward. Without FFmpeg, video uploads still work but won't show preview thumbnails.

## Optional: Run on startup

The installer offers two autostart options:

**Background service (Task Scheduler)** — starts at boot, no login required. Best for headless CMS servers or kiosks that reboot unattended. Requires running the installer as Administrator. To manage or remove:

```powershell
# View tasks
taskschd.msc

# Remove from command line
schtasks /delete /tn "TinySignage" /f
schtasks /delete /tn "TinySignage Watchdog" /f
```

**Startup folder shortcut** — starts when you log in. Simpler, no admin needed, but the CMS won't start until someone signs in after a reboot.

If you skipped startup setup during install, re-run `python install.py` to generate the batch file and choose a startup method.

To also open the player in kiosk mode, add this line to `start-tinysignage.bat` after the `python -m app.server` line (in a separate `start` command):

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
python install.py --update
```

`--update` pulls the latest code, reinstalls dependencies, and runs database migrations. Restart the application afterward.

If the automatic `git pull` fails (for example, offline or a diverged branch), `--update` prints the git error and continues with the dependency/database steps. To skip git entirely: `python install.py --update --no-pull`.

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
Another application is using port 8080. Either stop that application or edit `config.yaml` to use a different port:

```yaml
server:
  host: 0.0.0.0
  port: 9090
```

Then start the app:

```powershell
python -m app.server
```

**Player won't go fullscreen:**
Press **F11** in your browser. For a dedicated display, use Chrome's kiosk mode:

```powershell
chrome --kiosk http://localhost:8080/player
```

**Remote devices can't reach the CMS:**
Check that the server is running, then verify:
1. Your firewall allows Python on private networks — see [Allow through Windows Firewall](#allow-through-windows-firewall) above
2. Your network profile is set to **Private**, not Public (**Settings → Network & Internet** → click your connection → Network profile type)
3. You're using the correct IP address — run `ipconfig` and look for **IPv4 Address**

**Antivirus blocks or slows TinySignage:**
Some antivirus software (Windows Defender, Norton, McAfee, etc.) may quarantine `venv\Scripts\python.exe` or flag the server as suspicious. Check your antivirus quarantine list and restore any blocked files. If uploads are slow or files disappear from `media\`, add the TinySignage folder to your antivirus exclusion list.

---

## See also

- [Getting Started](getting-started.md) -- Zero-to-content walkthrough
- [Configuration](configuration.md) -- config.yaml reference
- [Managing Media](managing-media.md) -- Uploading and organizing content
- [Troubleshooting](troubleshooting.md) -- More common issues and fixes
