#!/usr/bin/env python3
"""TinySignage cross-platform installer.

Usage:
    python3 install.py              # Interactive install
    python3 install.py --update     # Update (git pull + deps + db + restart)
    python3 install.py --update --no-pull  # Update without git pull
    python3 install.py --non-interactive --display-name "Lobby TV"  # Scripted Pi

--update does a 'git pull --ff-only' in the install directory as its first
step. If the pull fails (offline, dirty tree, SSH without keys, diverged
branch, ...) the installer prints the git error and continues with the
dependency/database/restart steps because those are still valuable self-heals.
Pass --no-pull to skip git entirely.

Requires Python 3.9+. Uses only the standard library (runs before venv exists).
"""

import argparse
import glob
import os
import platform
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import textwrap
import ssl
import urllib.parse
import urllib.request
import urllib.error

# =========================================================================
# Constants & templates
# =========================================================================

MIN_PYTHON = (3, 9)
SERVICE_USER = "tinysignage"
TARGET_DIR = "/opt/tinysignage"
DEFAULT_PORT = 8080

DB_INIT_SCRIPT = textwrap.dedent("""\
    import asyncio
    from app.database import init_db, engine
    async def setup():
        await init_db()
        await engine.dispose()
    asyncio.run(setup())
""")

# --- Systemd unit templates (Pi) ----------------------------------------

SYSTEMD_APP = """\
[Unit]
Description=TinySignage Backend
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={install_dir}
ExecStart={install_dir}/venv/bin/python -m app.server
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths={install_dir}/media {install_dir}/db {install_dir}/logs {install_dir}/certs {install_dir}/config.yaml {install_dir}/config.env
MemoryMax=512M

[Install]
WantedBy=multi-user.target
"""

def _build_player_unit(lite, standalone, install_dir, user, browser_engine="chromium"):
    """Build a systemd unit for the player service.

    lite:           True for Pi OS Lite (cage/Wayland), False for X11/Desktop
    standalone:     True for player-only (no local backend), False for co-located
    browser_engine: "cog" for WPE WebKit, "chromium" for Chromium+cage
    """
    if standalone:
        after = "network-online.target"
        wants = "network-online.target"
    elif lite:
        after = "signage-app.service multi-user.target"
        wants = "signage-app.service"
    else:
        after = "signage-app.service graphical.target"
        wants = "signage-app.service"

    python_bin = "/usr/bin/python3" if standalone else f"{install_dir}/venv/bin/python"

    if lite and browser_engine == "cog":
        # cog does its own DRM/KMS compositing — no cage needed
        return textwrap.dedent(f"""\
            [Unit]
            Description=TinySignage Player (WPE WebKit — Lite)
            After={after}
            Wants={wants}
            StartLimitIntervalSec=300
            StartLimitBurst=5

            [Service]
            Type=simple
            User={user}
            WorkingDirectory={install_dir}

            # cog does DRM/KMS compositing directly on this TTY
            TTYPath=/dev/tty1
            StandardInput=tty-force
            StandardOutput=journal
            StandardError=journal

            RuntimeDirectory=tinysignage
            Environment=XDG_RUNTIME_DIR=/run/tinysignage

            ExecStartPre=/bin/sleep 5
            ExecStart={python_bin} {install_dir}/launcher.py
            WatchdogSec=120
            MemoryMax=512M
            Restart=on-failure
            RestartSec=10

            [Install]
            WantedBy=multi-user.target
        """)
    elif lite:
        return textwrap.dedent(f"""\
            [Unit]
            Description=TinySignage Player (Kiosk Browser — Lite)
            After={after}
            Wants={wants}
            StartLimitIntervalSec=300
            StartLimitBurst=5

            [Service]
            Type=simple
            User={user}
            WorkingDirectory={install_dir}

            # cage creates its own Wayland session on this TTY
            TTYPath=/dev/tty1
            StandardInput=tty-force
            StandardOutput=journal
            StandardError=journal

            RuntimeDirectory=tinysignage
            Environment=XDG_RUNTIME_DIR=/run/tinysignage

            ExecStartPre=/bin/sleep 5
            ExecStart=/usr/bin/cage -d -s -- {python_bin} {install_dir}/launcher.py
            WatchdogSec=120
            MemoryMax=1024M
            Restart=on-failure
            RestartSec=10

            [Install]
            WantedBy=multi-user.target
        """)
    else:
        wanted_by = "graphical.target"
        return textwrap.dedent(f"""\
            [Unit]
            Description=TinySignage Player (Kiosk Browser)
            After={after}
            Wants={wants}
            StartLimitIntervalSec=60
            StartLimitBurst=5

            [Service]
            Type=simple
            User={user}
            WorkingDirectory={install_dir}
            Environment=DISPLAY=:0
            Environment=XCURSOR_THEME=hidden
            Environment=XCURSOR_SIZE=1
            ExecStartPre=/bin/sleep 5
            ExecStart={python_bin} {install_dir}/launcher.py
            MemoryMax=1024M
            Restart=on-failure
            RestartSec=10

            [Install]
            WantedBy={wanted_by}
        """)

# --- Systemd user service (desktop Linux) --------------------------------

SYSTEMD_USER = """\
[Unit]
Description=TinySignage Backend
After=network.target

[Service]
Type=simple
WorkingDirectory={install_dir}
ExecStart={install_dir}/venv/bin/python -m app.server
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
"""

# --- macOS launchd plist -------------------------------------------------

LAUNCHD_PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tinysignage.app</string>
    <key>WorkingDirectory</key>
    <string>{install_dir}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{install_dir}/venv/bin/python</string>
        <string>-m</string>
        <string>app.server</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{install_dir}/logs/tinysignage.log</string>
    <key>StandardErrorPath</key>
    <string>{install_dir}/logs/tinysignage.err</string>
</dict>
</plist>
"""

# --- Windows batch file --------------------------------------------------

WINDOWS_BAT = """\
@echo off
cd /d "{install_dir}"
call "{install_dir}\\venv\\Scripts\\activate"
python -m app.server
"""

# --- Xcursor constants ---------------------------------------------------

XCURSOR_MAGIC = 0x72756358      # "Xcur" little-endian
XCURSOR_VERSION = 0x00010000
XCURSOR_IMAGE_TYPE = 0xFFFD0002

CURSOR_NAMES = [
    # Core pointers
    "default", "left_ptr", "arrow", "top_left_arrow",
    # Links / clickable
    "pointer", "hand", "hand1", "hand2", "pointing_hand",
    # Text
    "text", "ibeam", "xterm",
    # Busy / wait
    "wait", "watch", "progress", "left_ptr_watch", "half-busy",
    # Move / drag
    "move", "fleur", "grabbing", "grab", "dnd-move", "dnd-copy",
    "dnd-link", "dnd-none", "dnd-ask",
    # Resize edges
    "n-resize", "s-resize", "e-resize", "w-resize",
    "ne-resize", "nw-resize", "se-resize", "sw-resize",
    "top_side", "bottom_side", "left_side", "right_side",
    "top_left_corner", "top_right_corner",
    "bottom_left_corner", "bottom_right_corner",
    # Resize axes
    "ns-resize", "ew-resize", "nesw-resize", "nwse-resize",
    "row-resize", "col-resize",
    "sb_v_double_arrow", "sb_h_double_arrow",
    "size_ver", "size_hor", "size_fdiag", "size_bdiag", "size_all",
    # Crosshair
    "crosshair", "cross", "tcross", "cross_reverse",
    # Forbidden
    "not-allowed", "no-drop", "circle", "forbidden", "X_cursor",
    # Help
    "help", "question_arrow", "whats_this",
    # Context menu
    "context-menu",
    # Misc
    "copy", "alias", "cell", "vertical-text", "zoom-in", "zoom-out",
    "all-scroll", "pencil", "pirate", "plus",
    "up_arrow", "right_arrow", "left_arrow", "down_arrow",
    "based_arrow_up", "based_arrow_down",
]


# =========================================================================
# Detection
# =========================================================================

def detect_platform():
    """Detect: 'pi', 'linux', 'macos', or 'windows'."""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    if system == "linux":
        # Check for Raspberry Pi
        for path in ["/proc/device-tree/model", "/proc/cpuinfo"]:
            try:
                with open(path) as f:
                    content = f.read().lower()
                if "raspberry pi" in content or "bcm" in content:
                    return "pi"
            except (FileNotFoundError, PermissionError):
                pass
        return "linux"
    error_exit(f"Unsupported platform: {system}")


def is_pi_lite():
    """True if running Pi OS Lite (no desktop environment)."""
    try:
        r = subprocess.run(
            ["systemctl", "get-default"],
            capture_output=True, text=True, timeout=5,
        )
        return "multi-user.target" in r.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def detect_desktop_user():
    """Return the Pi desktop autologin user (e.g. 'pi').

    Looked up in this order:
      1. lightdm autologin-user
      2. /etc/systemd/system/getty@tty1.service.d/autologin.conf (raspi-config style)
      3. First /etc/passwd entry with UID 1000
      4. Fallback: 'pi'
    """
    # 1. lightdm
    for p in ("/etc/lightdm/lightdm.conf",
              "/etc/lightdm/lightdm.conf.d/50-pi.conf"):
        try:
            with open(p) as f:
                for line in f:
                    m = re.match(r"\s*autologin-user\s*=\s*(\S+)", line)
                    if m:
                        return m.group(1)
        except FileNotFoundError:
            pass
    # 2. raspi-config getty autologin override
    try:
        with open("/etc/systemd/system/getty@tty1.service.d/autologin.conf") as f:
            m = re.search(r"--autologin\s+(\S+)", f.read())
            if m:
                return m.group(1)
    except FileNotFoundError:
        pass
    # 3. UID 1000
    try:
        import pwd
        for entry in pwd.getpwall():
            if entry.pw_uid == 1000:
                return entry.pw_name
    except (ImportError, KeyError):
        pass
    # 4. fallback
    return "pi"


def _remove_legacy_player_user_unit(desktop_user):
    """Remove any leftover broken systemd user-unit player install.

    The previous installer wrote a user unit wired to
    graphical-session.target, which labwc never activates — so the unit
    sat 'enabled but never run'. Clean it up before installing the
    XDG autostart replacement so we don't leave dead state behind.
    """
    import pwd
    try:
        pw = pwd.getpwnam(desktop_user)
    except KeyError:
        return
    user_systemd = os.path.join(pw.pw_dir, ".config", "systemd", "user")
    unit_path = os.path.join(user_systemd, "signage-player.service")
    if os.path.isfile(unit_path) or os.path.islink(unit_path):
        try:
            os.remove(unit_path)
            info(f"Removed legacy user unit: {unit_path}")
        except OSError as e:
            warn(f"Could not remove {unit_path}: {e}")
    # Sweep every *.target.wants/signage-player.service symlink.
    pattern = os.path.join(user_systemd, "*.target.wants", "signage-player.service")
    for link in glob.glob(pattern):
        try:
            os.remove(link)
            info(f"Removed legacy enable symlink: {link}")
        except OSError as e:
            warn(f"Could not remove {link}: {e}")


def _get_primary_ip():
    """Return this machine's primary outbound IPv4 address, or None.

    Used so the installer can print an IP-based CMS URL alongside the
    mDNS one — Windows clients often fail to resolve *.local, so giving
    users both forms means they always have a working address.

    Uses the UDP-socket trick: connect() on a UDP socket doesn't send
    any packet, it just picks the routing interface, which we then read
    back with getsockname(). Target 192.0.2.1 is TEST-NET-1 (RFC 5737),
    so it can't collide with anything real.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("192.0.2.1", 1))
            ip = s.getsockname()[0]
        finally:
            s.close()
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    return None


def _write_player_wrapper_script(install_dir, python_bin):
    """Write the kiosk launcher wrapper script used by XDG autostart.

    A small wrapper avoids the brittle quoting rules of inline `Exec=sh -c`
    in .desktop files, and gives us a `while true` loop that replaces the
    crash-recovery role of `Restart=always` from the old systemd unit.
    `launcher.py` ends with `os.execvp(chromium, …)`, so when chromium
    exits, the `sh` parent's wait returns and the loop relaunches it.
    """
    scripts_dir = os.path.join(install_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    script_path = os.path.join(scripts_dir, "run-player.sh")
    content = textwrap.dedent(f"""\
        #!/bin/sh
        # Auto-generated by install.py. Do not edit — will be overwritten.
        # TinySignage kiosk player launcher for Pi OS Desktop XDG autostart.
        # cd into the install dir so launcher.py can find config.yaml even
        # though XDG autostart runs us with cwd=$HOME.
        sleep 5
        cd {install_dir} || exit 1
        while true; do
            XCURSOR_THEME=hidden XCURSOR_SIZE=1 {python_bin} {install_dir}/launcher.py
            sleep 5
        done
    """)
    with open(script_path, "w") as f:
        f.write(content)
    os.chmod(script_path, 0o755)
    # Match the rest of install_dir (chowned to SERVICE_USER later, but we
    # set it explicitly here so the file is correct even before that step).
    try:
        import pwd
        pw = pwd.getpwnam(SERVICE_USER)
        os.chown(script_path, pw.pw_uid, pw.pw_gid)
    except (ImportError, KeyError):
        pass
    return script_path


def _install_player_autostart(install_dir, desktop_user, standalone):
    """Install the kiosk player as an XDG autostart entry for `desktop_user`.

    We do NOT use a systemd user unit here. The previous attempt wired a
    user unit to graphical-session.target, but Pi OS Desktop's labwc/
    wayfire session never activates that target, so the unit was never
    invoked. lxsession-xdg-autostart (shipped by raspberrypi-ui-mods)
    reliably picks up ~/.config/autostart/*.desktop entries on every
    desktop session, with the full graphical environment inherited
    automatically.
    """
    import pwd
    try:
        pw = pwd.getpwnam(desktop_user)
    except KeyError:
        warn(f"Desktop user '{desktop_user}' not found — skipping player autostart")
        return
    uid, gid = pw.pw_uid, pw.pw_gid

    # 1. Clean up any leftover broken user-unit install first.
    _remove_legacy_player_user_unit(desktop_user)

    # 2. Pick the python interpreter (matches the deleted helper's logic).
    python_bin = "/usr/bin/python3" if standalone \
        else f"{install_dir}/venv/bin/python"

    # 3. Write the wrapper script that the .desktop file will exec.
    _write_player_wrapper_script(install_dir, python_bin)

    # 4. Ensure ~du/.config/autostart/ exists and is owned by the user.
    autostart_dir = os.path.join(pw.pw_dir, ".config", "autostart")
    os.makedirs(autostart_dir, exist_ok=True)
    # Targeted ownership fix — only chown the dirs we created if they're
    # currently root-owned. Avoids the recursive `chown -R .config` pattern
    # which can clobber unrelated user-owned files.
    config_dir = os.path.join(pw.pw_dir, ".config")
    for d in (config_dir, autostart_dir):
        try:
            if os.stat(d).st_uid == 0:
                os.chown(d, uid, gid)
        except OSError:
            pass

    # 5. Write the .desktop file.
    desktop_path = os.path.join(autostart_dir, "signage-player.desktop")
    desktop_content = textwrap.dedent(f"""\
        [Desktop Entry]
        Type=Application
        Version=1.0
        Name=TinySignage Player
        Comment=Kiosk browser for digital signage
        Exec={install_dir}/scripts/run-player.sh
        X-GNOME-Autostart-enabled=true
        NoDisplay=true
        Terminal=false
    """)
    with open(desktop_path, "w") as f:
        f.write(desktop_content)
    os.chmod(desktop_path, 0o644)
    os.chown(desktop_path, uid, gid)

    # 6. Sanity check: warn if no XDG autostart launcher is on the system.
    if not (shutil.which("lxsession-xdg-autostart") or shutil.which("dex")):
        warn(
            "No XDG autostart launcher found (lxsession-xdg-autostart / dex). "
            "The kiosk player may not start automatically. "
            "Try: sudo apt install lxsession"
        )

    info(f"Installed signage-player autostart for {desktop_user}: {desktop_path}")


def _enable_pi_autologin(lite):
    """Enable autologin via raspi-config so a session exists at boot."""
    if not shutil.which("raspi-config"):
        warn("raspi-config not found — cannot configure autologin automatically")
        return
    target = "B2" if lite else "B4"  # B2=console autologin, B4=desktop autologin
    run_cmd(["raspi-config", "nonint", "do_boot_behaviour", target], check=False)
    info(f"Enabled {'console' if lite else 'desktop'} autologin")


def find_boot_config():
    """Return the Pi boot config path, or None."""
    for p in ["/boot/firmware/config.txt", "/boot/config.txt"]:
        if os.path.isfile(p):
            return p
    return None


def check_python_version():
    """Exit if Python is too old."""
    if sys.version_info < MIN_PYTHON:
        error_exit(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required "
            f"(found {platform.python_version()}).\n"
            "  Fix: brew install python@3.11  (macOS)\n"
            "       sudo apt install python3  (Linux/Pi)\n"
            "       Download from python.org  (Windows)"
        )


# =========================================================================
# Utilities
# =========================================================================

def run_cmd(cmd, cwd=None, check=True, capture=False, env=None):
    """Run a subprocess. On failure (if check), print error and exit."""
    kwargs = {"cwd": cwd}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    if env:
        full_env = os.environ.copy()
        full_env.update(env)
        kwargs["env"] = full_env
    try:
        result = subprocess.run(cmd, **kwargs)
    except FileNotFoundError:
        if check:
            error_exit(f"Command not found: {cmd[0]}")
        return None
    if check and result.returncode != 0:
        cmd_str = " ".join(str(c) for c in cmd)
        msg = f"Command failed: {cmd_str}"
        if capture and result.stderr:
            msg += f"\n{result.stderr.strip()}"
        error_exit(msg)
    return result


def run_as_user(user, cmd, cwd=None, check=True, capture=False):
    """Run a command as a different user via runuser (Linux only)."""
    return run_cmd(
        ["runuser", "-u", user, "--"] + list(cmd),
        cwd=cwd, check=check, capture=capture,
    )


def sanitize_hostname(name):
    """Convert a display name to a valid DNS hostname."""
    h = name.lower()
    h = re.sub(r"[ _]", "-", h)
    h = re.sub(r"[^a-z0-9-]", "", h)
    h = re.sub(r"-{2,}", "-", h)
    h = h.strip("-")[:63]
    return h or "tinysignage"


def prompt_input(message, default=None):
    """Prompt for text input with an optional default."""
    suffix = f" [{default}]: " if default else ": "
    try:
        value = input(message + suffix).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)
    return value or default


def prompt_yn(message, default=True):
    """Prompt for yes/no."""
    suffix = " [Y/n]: " if default else " [y/N]: "
    try:
        value = input(message + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)
    if not value:
        return default
    return value in ("y", "yes")


def prompt_mode():
    """Prompt for install mode: both, cms, or player."""
    while True:
        print("What would you like to install?\n")
        print("  1. Everything — CMS + Player on this device")
        print("     Best for a single device that manages AND displays content.")
        print("     Example: a coffee shop with one screen behind the counter.\n")
        print("  2. CMS only — content management server")
        print("     Runs the server that manages playlists, schedules, and media.")
        print("     Install this once, then point all your player screens at it.\n")
        print("  3. Player only — display screen")
        print("     Turns this device into a display that connects to a CMS.")
        print("     You'll need a CMS server already set up somewhere.\n")
        try:
            choice = input("Choice [1]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(1)
        mode = {"": "both", "1": "both", "2": "cms", "3": "player"}.get(choice)
        if mode is not None:
            return mode
        print("  Please enter 1, 2, or 3.\n")


def prompt_server_url():
    """Prompt for the CMS server URL (player-only mode)."""
    print("\nEnter the address of your CMS server.")
    print("This is the device where you installed the TinySignage CMS.\n")
    print("  Examples:  http://192.168.1.50:8080")
    print("             http://lobby-tv.local:8080\n")
    while True:
        url = prompt_input("CMS server address")
        if url:
            break
        print("  A server address is required for player-only installs.")
    url = url.rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    parsed = urllib.parse.urlparse(url)
    if not parsed.port:
        suggested = f"{url}:{DEFAULT_PORT}"
        info(f"No port specified — did you mean {suggested} ?")
        if prompt_yn(f"Use {suggested} instead?", default=True):
            url = suggested
    return url


def _urlopen_tolerant(url, timeout=5):
    """urlopen wrapper that accepts self-signed certs on https:// URLs.

    These are health checks, not auth-bearing calls, so disabling cert
    verification is safe. Returns the response object.
    """
    req = urllib.request.Request(url, method="GET")
    if url.lower().startswith("https://"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return urllib.request.urlopen(req, timeout=timeout)


def validate_server_url(url):
    """Check if the CMS server is reachable. Warns but does not block."""
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        warn(f"'{url}' doesn't look like a valid URL.")
        info("Expected format: http://192.168.1.50:8080 or http://hostname.local:8080")
        return
    try:
        resp = _urlopen_tolerant(f"{url}/health", timeout=5)
        if resp.status == 200:
            info(f"CMS server at {url} is reachable")
            return
    except (urllib.error.URLError, OSError):
        pass
    warn(f"Could not reach CMS server at {url}")
    info("This is OK if the server is on a different network or not running yet.")
    info("Make sure the address is correct before the player connects.")


def step(number, total, message):
    print(f"[{number}/{total}] {message}")


def info(message):
    print(f"  {message}")


def warn(message):
    print(f"  WARNING: {message}")


def error_exit(message):
    print(f"\nERROR: {message}", file=sys.stderr)
    sys.exit(1)


def _check_python_version(path):
    """Return True if the interpreter at path is Python 3.9+."""
    try:
        out = subprocess.check_output(
            [path, "--version"], stderr=subprocess.STDOUT, text=True, timeout=5
        ).strip()
        # e.g. "Python 3.11.4"
        m = re.search(r'(\d+)\.(\d+)', out)
        if m and (int(m.group(1)), int(m.group(2))) >= MIN_PYTHON:
            return True
    except (subprocess.CalledProcessError, FileNotFoundError, OSError, subprocess.TimeoutExpired):
        pass
    return False


def find_python():
    """Find the best available Python 3.9+ interpreter (full path)."""
    for name in ["python3.13", "python3.12", "python3.11", "python3.10", "python3.9", "python3"]:
        path = shutil.which(name)
        if path and _check_python_version(path):
            return path
    if sys.platform == "win32":
        path = shutil.which("python")
        if path and _check_python_version(path):
            return path
    return sys.executable


def get_venv_python(install_dir):
    if sys.platform == "win32":
        return os.path.join(install_dir, "venv", "Scripts", "python.exe")
    return os.path.join(install_dir, "venv", "bin", "python")


def get_venv_pip(install_dir):
    if sys.platform == "win32":
        return os.path.join(install_dir, "venv", "Scripts", "pip.exe")
    return os.path.join(install_dir, "venv", "bin", "pip")


# =========================================================================
# Xcursor generation (inlined from install/create_hidden_cursors.py)
# =========================================================================

def build_xcursor_image():
    """Build a minimal valid Xcursor file: single 1x1 transparent image."""
    header_size = 16
    image_offset = header_size + 12  # one TOC entry
    image_header_size = 36

    data = struct.pack("<IIII", XCURSOR_MAGIC, header_size, XCURSOR_VERSION, 1)
    data += struct.pack("<III", XCURSOR_IMAGE_TYPE, 1, image_offset)
    data += struct.pack(
        "<IIIIIIIII",
        image_header_size, XCURSOR_IMAGE_TYPE, 1,  # nominal size
        1, 1, 1, 0, 0, 0,  # version, w, h, xhot, yhot, delay
    )
    data += struct.pack("<I", 0x00000000)  # 1 ARGB pixel, fully transparent
    return data


def install_cursor_theme():
    """Install transparent cursor theme for kiosk mode (requires root)."""
    cursor_dir = "/usr/share/icons/hidden/cursors"
    os.makedirs(cursor_dir, exist_ok=True)

    image_data = build_xcursor_image()
    for name in CURSOR_NAMES:
        with open(os.path.join(cursor_dir, name), "wb") as f:
            f.write(image_data)

    with open("/usr/share/icons/hidden/index.theme", "w") as f:
        f.write("[Icon Theme]\n")
        f.write("Name=Hidden\n")
        f.write("Comment=Transparent cursor theme for kiosk mode\n")

    info(f"Installed {len(CURSOR_NAMES)} transparent cursor files")


# =========================================================================
# Pi system setup
# =========================================================================

def pi_move_to_opt(source_dir, non_interactive=False):
    """Move install directory to /opt/tinysignage if not already there."""
    if os.path.realpath(source_dir) == os.path.realpath(TARGET_DIR):
        return TARGET_DIR
    print(f"Moving install from {source_dir} to {TARGET_DIR}...")
    if os.path.isdir(TARGET_DIR):
        has_db = os.path.isfile(os.path.join(TARGET_DIR, "db", "signage.db"))
        has_media = os.path.isdir(os.path.join(TARGET_DIR, "media"))
        if has_db or has_media:
            warn(f"{TARGET_DIR} already exists with data:")
            if has_db:
                info("  - Database (db/signage.db)")
            if has_media:
                media_count = sum(
                    1 for f in os.listdir(os.path.join(TARGET_DIR, "media"))
                    if not f.startswith(".") and f != "thumbs"
                )
                if media_count:
                    info(f"  - Media files ({media_count} items)")
            if not non_interactive:
                if not prompt_yn("Replace existing install? (data will be lost)", default=False):
                    error_exit("Install cancelled. Back up your data and try again.")
            else:
                info("Non-interactive mode — replacing existing install")
        shutil.rmtree(TARGET_DIR)
    shutil.copytree(source_dir, TARGET_DIR)
    # Verify the copy before removing the source
    key_files = ["config.yaml", "install.py", "requirements.txt"]
    if all(os.path.isfile(os.path.join(TARGET_DIR, f)) for f in key_files):
        shutil.rmtree(source_dir)
        # If we were running from inside source_dir, our CWD just got
        # deleted — any subprocess we spawn will print
        # `getcwd() failed: No such file or directory`. Move into the
        # new install dir so child processes have a valid CWD.
        try:
            os.chdir(TARGET_DIR)
        except OSError:
            pass
    else:
        warn(f"Copy verification failed — source preserved at {source_dir}")
    info(f"Install directory is now {TARGET_DIR}")
    return TARGET_DIR


def _configure_labwc_rc_xml(home_dir, uid, gid):
    """Configure labwc rc.xml to hide the cursor.

    Two mechanisms (defense-in-depth):
    1. <cursor><theme>hidden</theme><size>1</size></cursor> — makes the
       desktop cursor transparent (works for labwc itself, but Wayland
       clients like cog can override with their own cursor).
    2. <keyboard><keybind key="A-W-h"><action name="HideCursor"/>
       </keybind></keyboard> — compositor-level action that hides the
       cursor regardless of what the client sets. Triggered from labwc
       autostart via wtype (see _configure_labwc_autostart).
    """
    import xml.etree.ElementTree as ET

    labwc_dir = os.path.join(home_dir, ".config", "labwc")
    rc_path = os.path.join(labwc_dir, "rc.xml")

    try:
        os.makedirs(labwc_dir, exist_ok=True)
        if os.path.isfile(rc_path):
            try:
                tree = ET.parse(rc_path)
                root = tree.getroot()
            except ET.ParseError as e:
                warn(f"Could not parse {rc_path}: {e} — skipping rc.xml cursor config")
                return
        else:
            root = ET.Element("labwc_config")
            tree = ET.ElementTree(root)

        # --- <cursor> theme (defense layer 1) ---
        cursor_el = root.find("cursor")
        if cursor_el is None:
            cursor_el = ET.SubElement(root, "cursor")

        theme_el = cursor_el.find("theme")
        if theme_el is None:
            theme_el = ET.SubElement(cursor_el, "theme")
        theme_el.text = "hidden"

        size_el = cursor_el.find("size")
        if size_el is None:
            size_el = ET.SubElement(cursor_el, "size")
        size_el.text = "1"

        # --- <keyboard> keybind for HideCursor action (defense layer 2) ---
        keyboard_el = root.find("keyboard")
        if keyboard_el is None:
            keyboard_el = ET.SubElement(root, "keyboard")

        # Check if we already added the HideCursor keybind
        hide_cursor_exists = False
        for kb in keyboard_el.findall("keybind"):
            if kb.get("key") == "A-W-h":
                for action in kb.findall("action"):
                    if action.get("name") == "HideCursor":
                        hide_cursor_exists = True
                        break
            if hide_cursor_exists:
                break

        if not hide_cursor_exists:
            kb_el = ET.SubElement(keyboard_el, "keybind")
            kb_el.set("key", "A-W-h")
            action_el = ET.SubElement(kb_el, "action")
            action_el.set("name", "HideCursor")

        ET.indent(tree, space="  ")
        tree.write(rc_path, xml_declaration=True, encoding="UTF-8")

        try:
            os.chown(labwc_dir, uid, gid)
        except OSError:
            pass
        try:
            os.chown(rc_path, uid, gid)
        except OSError:
            pass
        info("labwc rc.xml cursor hiding configured")
    except Exception as e:
        warn(f"Could not configure labwc rc.xml: {e}")


# Marker comments used to identify lines we add to labwc autostart
_LABWC_AUTOSTART_MARKER = "# TinySignage cursor hide"


def _configure_labwc_autostart(home_dir, uid, gid):
    """Add cursor-hiding commands to labwc autostart.

    Uses wtype to trigger the HideCursor keybind defined in rc.xml, and
    swayidle to re-trigger it after any mouse movement (1s timeout).
    This hides cog/WPE's own cursor which ignores XCURSOR_THEME.
    """
    labwc_dir = os.path.join(home_dir, ".config", "labwc")
    autostart_path = os.path.join(labwc_dir, "autostart")

    # The commands we want in autostart
    lines_to_add = [
        f"{_LABWC_AUTOSTART_MARKER}\n",
        "sleep 1 && wtype -M alt -M logo -P h &\n",
        "swayidle -w timeout 1 'wtype -M alt -M logo -P h' &\n",
    ]

    try:
        os.makedirs(labwc_dir, exist_ok=True)

        existing = ""
        if os.path.isfile(autostart_path):
            with open(autostart_path) as f:
                existing = f.read()

        if _LABWC_AUTOSTART_MARKER in existing:
            return  # already configured

        with open(autostart_path, "a") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.writelines(lines_to_add)

        try:
            os.chown(labwc_dir, uid, gid)
        except OSError:
            pass
        try:
            os.chown(autostart_path, uid, gid)
        except OSError:
            pass
        info("labwc autostart cursor hiding configured")
    except Exception as e:
        warn(f"Could not configure labwc autostart: {e}")


def pi_system_setup(install_dir, display_name, hostname, lite, mode="both", port=DEFAULT_PORT):
    """All Pi system-level steps (requires root)."""
    total = 6

    # --- [1] apt packages ---
    step(1, total, "Installing system packages...")
    packages = ["python3", "avahi-daemon", "curl"]
    if mode in ("both", "cms"):
        packages.extend(["python3-venv", "python3-pip", "ffmpeg"])
    browser_engine = "chromium"  # track which engine gets installed
    if mode in ("both", "player"):
        if mode == "player":
            packages.append("python3-yaml")  # launcher.py needs PyYAML
        # Two-phase browser install: prefer cog (WPE WebKit), fall back to chromium
        run_cmd(["apt-get", "update", "-qq"])
        # Try cog first — lighter engine for embedded kiosks
        cog_packages = [
            "cog",
            "gstreamer1.0-plugins-good",
            "gstreamer1.0-plugins-bad",
            "gstreamer1.0-libav",
            "wtype",      # trigger labwc keybinds from scripts (cursor hiding)
            "swayidle",   # re-hide cursor after mouse movement
        ]
        cog_result = run_cmd(
            ["apt-get", "install", "-y", "-qq"] + packages + cog_packages,
            env={"DEBIAN_FRONTEND": "noninteractive"},
            check=False,
            capture=True,
        )
        if cog_result and cog_result.returncode == 0:
            browser_engine = "cog"
            info("Installed cog (WPE WebKit) — lightweight kiosk browser")
        else:
            # cog not available — fall back to chromium
            info("cog not available, falling back to Chromium")
            packages.append("chromium")
            if lite:
                info("Detected Pi OS Lite — will install kiosk compositor (cage)")
                packages.extend(["cage", "xwayland"])
            run_cmd(
                ["apt-get", "install", "-y", "-qq"] + packages,
                env={"DEBIAN_FRONTEND": "noninteractive"},
            )
    else:
        run_cmd(["apt-get", "update", "-qq"])
        run_cmd(
            ["apt-get", "install", "-y", "-qq"] + packages,
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )

    # --- [2] Service user ---
    step(2, total, "Creating service user...")
    r = run_cmd(["id", SERVICE_USER], capture=True, check=False)
    if r and r.returncode == 0:
        info(f"User '{SERVICE_USER}' already exists")
    else:
        run_cmd([
            "useradd", "--system", "--create-home",
            "--shell", "/bin/bash", SERVICE_USER,
        ])
        run_cmd(["usermod", "-aG", "video", SERVICE_USER])
        info(f"Created user '{SERVICE_USER}'")
    if lite:
        run_cmd(["usermod", "-aG", "input,render", SERVICE_USER])

    # --- [3] Hostname & mDNS ---
    step(3, total, "Configuring hostname and mDNS...")
    if hostname:
        current = platform.node()
        if hostname != current:
            run_cmd(["hostnamectl", "set-hostname", hostname])
            hosts_path = "/etc/hosts"
            with open(hosts_path) as f:
                content = f.read()
            if f"127.0.1.1" in content and current in content:
                content = re.sub(
                    rf"127\.0\.1\.1\s+.*{re.escape(current)}.*",
                    f"127.0.1.1\t{hostname}",
                    content,
                )
            else:
                content = content.rstrip("\n") + f"\n127.0.1.1\t{hostname}\n"
            with open(hosts_path, "w") as f:
                f.write(content)
            info(f"Hostname set to: {hostname}")
        else:
            info(f"Hostname already set to: {hostname}")

    if os.path.isdir("/etc/avahi"):
        run_cmd(["systemctl", "enable", "avahi-daemon"])
        run_cmd(["systemctl", "start", "avahi-daemon"])
        info(f"mDNS enabled — reachable at {hostname or platform.node()}.local")

    # --- [4] Systemd units (generated from templates — no sed patching) ---
    step(4, total, "Installing systemd units...")
    services = []

    if mode in ("both", "cms"):
        with open("/etc/systemd/system/signage-app.service", "w") as f:
            f.write(SYSTEMD_APP.format(install_dir=install_dir, user=SERVICE_USER, port=port))
        services.append("signage-app")

    if mode in ("both", "player"):
        standalone = (mode == "player")
        if lite:
            if browser_engine == "cog":
                info("Using Lite kiosk service (cog/WPE on tty1 — no cage needed)")
            else:
                info("Using Lite kiosk service (cage + Chromium on tty1)")
            unit = _build_player_unit(lite, standalone, install_dir, SERVICE_USER,
                                      browser_engine=browser_engine)
            with open("/etc/systemd/system/signage-player.service", "w") as f:
                f.write(unit)
            services.append("signage-player")
            # Both cog and cage need sole ownership of tty1 — kick getty off it.
            run_cmd(["systemctl", "disable", "--now", "getty@tty1.service"],
                    check=False)
            run_cmd(["systemctl", "mask", "getty@tty1.service"], check=False)
        else:
            # Pi OS Desktop: the player must run inside the desktop user's
            # graphical session. A systemd user unit bound to
            # graphical-session.target does not work here — labwc never
            # activates that target. Use an XDG autostart entry instead;
            # lxsession-xdg-autostart picks it up reliably under labwc.
            desktop_user = detect_desktop_user()
            info(f"Installing player autostart for desktop user '{desktop_user}'")
            _install_player_autostart(install_dir, desktop_user, standalone)

        # Make sure the Pi actually boots into a session at all.
        _enable_pi_autologin(lite)

    run_cmd(["systemctl", "daemon-reload"])
    if services:
        run_cmd(["systemctl", "enable"] + services)

    # --- [5] Transparent cursor theme ---
    step(5, total, "Installing transparent cursor theme...")
    if mode in ("both", "player"):
        install_cursor_theme()
    else:
        info("Skipped (no player on this device)")

    # Set cursor theme in labwc environment (Pi OS Desktop with Wayland).
    # Lite uses cage (no labwc), so this is meaningless there.
    if mode in ("both", "player") and not lite and shutil.which("labwc"):
        try:
            import pwd
            desktop_user = detect_desktop_user()
            pw = pwd.getpwnam(desktop_user)
            uid, gid = pw.pw_uid, pw.pw_gid
            labwc_dir = os.path.join(pw.pw_dir, ".config", "labwc")
            labwc_env = os.path.join(labwc_dir, "environment")
            os.makedirs(labwc_dir, exist_ok=True)
            needs_cursor = True
            if os.path.isfile(labwc_env):
                with open(labwc_env) as f:
                    if "XCURSOR_THEME" in f.read():
                        needs_cursor = False
            if needs_cursor:
                with open(labwc_env, "a") as f:
                    f.write("XCURSOR_THEME=hidden\n")
                    f.write("XCURSOR_SIZE=1\n")
            # Targeted ownership — only the dir we created and the file we
            # may have written. Avoids the broad recursive chown.
            try:
                os.chown(labwc_dir, uid, gid)
            except OSError:
                pass
            try:
                os.chown(labwc_env, uid, gid)
            except OSError:
                pass
            info("labwc cursor environment configured")
        except (ImportError, KeyError):
            pass

    # Configure labwc rc.xml for cursor hiding (higher authority than env vars)
    if mode in ("both", "player") and not lite and shutil.which("labwc"):
        try:
            import pwd
            desktop_user = detect_desktop_user()
            pw = pwd.getpwnam(desktop_user)
            _configure_labwc_rc_xml(pw.pw_dir, pw.pw_uid, pw.pw_gid)
            _configure_labwc_autostart(pw.pw_dir, pw.pw_uid, pw.pw_gid)
        except (ImportError, KeyError):
            pass

    # --- [6] Boot config (GPU memory + hardware watchdog) ---
    step(6, total, "Configuring boot settings...")
    config_file = find_boot_config()
    if config_file:
        with open(config_file) as f:
            boot = f.read()
        additions = ""
        if mode in ("both", "player") and "gpu_mem=128" not in boot:
            additions += "gpu_mem=128\n"
            info("GPU memory set to 128MB (reboot required)")
        if "dtparam=watchdog=on" not in boot:
            additions += "dtparam=watchdog=on\n"
            info("Hardware watchdog enabled (reboot required)")
        if additions:
            with open(config_file, "a") as f:
                f.write("\n" + additions)

    # systemd watchdog integration
    system_conf = "/etc/systemd/system.conf"
    if os.path.isfile(system_conf):
        with open(system_conf) as f:
            conf = f.read()
        if not re.search(r"^RuntimeWatchdogSec=", conf, re.MULTILINE):
            new_conf = re.sub(
                r"^#RuntimeWatchdogSec=.*$",
                "RuntimeWatchdogSec=14",
                conf,
                flags=re.MULTILINE,
            )
            if new_conf != conf:
                with open(system_conf, "w") as f:
                    f.write(new_conf)
                info("systemd hardware watchdog integration enabled (14s timeout)")

    # Set ownership of entire install directory
    run_cmd(["chown", "-R", f"{SERVICE_USER}:{SERVICE_USER}", install_dir])

    # On Pi OS Desktop the player runs as the desktop user (not tinysignage),
    # so its writable browser profile dir must be owned by that user. Also
    # make sure the install dir is traversable/readable for them.
    if mode in ("both", "player") and not lite:
        desktop_user = detect_desktop_user()
        data_dir = os.path.join(install_dir, "data")
        bp_dir = os.path.join(data_dir, "browser-profile")
        os.makedirs(bp_dir, exist_ok=True)
        run_cmd(["chown", "-R", f"{desktop_user}:{desktop_user}", data_dir])
        # Make every directory world-traversable so the desktop user can
        # reach config.yaml, the venv, and launcher.py. Use +X (capital) so
        # this only touches directories and already-executable files —
        # importantly, config.env stays 0600.
        run_cmd(["chmod", "-R", "a+X", install_dir])


# =========================================================================
# App setup — all platforms
# =========================================================================

def setup_venv(install_dir):
    """Create Python venv if it doesn't exist."""
    venv_dir = os.path.join(install_dir, "venv")
    if os.path.isdir(venv_dir):
        info("venv already exists")
        return
    run_cmd([find_python(), "-m", "venv", venv_dir])


def install_deps(install_dir):
    """pip install -r requirements.txt into the venv."""
    run_cmd([
        get_venv_pip(install_dir), "install", "--quiet",
        "-r", os.path.join(install_dir, "requirements.txt"),
    ])


def create_directories(install_dir):
    """Create media/, db/, logs/, certs/ directories."""
    for d in ["media", "media/thumbs", "db", "logs", "certs"]:
        os.makedirs(os.path.join(install_dir, d), exist_ok=True)


def generate_config_env(install_dir):
    """Generate config.env with a random SECRET_KEY (if absent)."""
    path = os.path.join(install_dir, "config.env")
    if os.path.isfile(path):
        info("config.env already exists")
        return
    content = (
        "# TinySignage environment config (auto-generated)\n"
        f"SECRET_KEY={secrets.token_hex(32)}\n"
    )
    if sys.platform != "win32":
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(content)
    else:
        with open(path, "w") as f:
            f.write(content)
    info("Generated config.env with SECRET_KEY")


# Tracked files the installer/user modifies on deployed systems.
# Stashed before git pull and restored after.
_GIT_MANAGED_CONFIGS = {
    "config.yaml",
    "tinysignage-bridge/config.yaml",
}

# Minimum keys that MUST survive even a failed stash pop (fallback).
_CONFIG_YAML_CRITICAL_KEYS = ("device_id", "server_url", "display_name")


def _yaml_quote(value):
    """Quote a value for safe YAML serialization (stdlib only)."""
    s = str(value)
    return "'" + s.replace("'", "''") + "'"


def _indent_of(line):
    return len(line) - len(line.lstrip(" "))


def _read_yaml_values(config_path, keys):
    """Read top-level scalar values from a YAML file (stdlib only).

    Returns {key: value} for only the keys present in *keys* that exist
    in the file.  Handles bare, single-quoted, and double-quoted values.
    """
    result = {}
    try:
        with open(config_path) as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                # Only top-level keys (no leading whitespace).
                if line[0] in (" ", "\t"):
                    continue
                colon = stripped.find(":")
                if colon < 0:
                    continue
                key = stripped[:colon].strip()
                if key not in keys:
                    continue
                raw = stripped[colon + 1:].strip()
                # Strip inline comments (outside quotes).
                if raw.startswith("'"):
                    end = raw.find("'", 1)
                    if end > 0:
                        raw = raw[1:end].replace("''", "'")
                elif raw.startswith('"'):
                    end = raw.find('"', 1)
                    if end > 0:
                        raw = raw[1:end]
                else:
                    # Bare value — strip inline comment.
                    if " #" in raw:
                        raw = raw[:raw.index(" #")].rstrip()
                if raw:
                    result[key] = raw
    except FileNotFoundError:
        pass
    return result


def _update_yaml_file(config_path, **updates):
    """Update YAML keys in a file (stdlib only).

    Top-level scalar keys are passed as ``key=value``. Nested keys use
    dot notation, e.g. ``server__https__enabled=True`` is written as::

        server:
          https:
            enabled: 'True'

    (Python keyword args can't contain dots, so we use ``__`` as the
    separator.) Existing keys are replaced in place; missing keys are
    appended to the appropriate parent block, creating parent blocks
    if needed.
    """
    lines = []
    if os.path.isfile(config_path):
        with open(config_path) as f:
            lines = f.readlines()

    # Split updates into top-level (no "__") and nested (one or more "__")
    top_level = {}
    nested = []  # list of (path_parts, value)
    for key, value in updates.items():
        if "__" in key:
            nested.append((key.split("__"), value))
        else:
            top_level[key] = value

    # --- pass 1: top-level scalar replace-in-place ----------------------
    remaining_top = dict(top_level)
    new_lines = []
    for line in lines:
        replaced = False
        if not line.lstrip().startswith("#") and _indent_of(line) == 0:
            for key in list(remaining_top):
                if re.match(rf"^{re.escape(key)}\s*:", line):
                    new_lines.append(f"{key}: {_yaml_quote(remaining_top.pop(key))}\n")
                    replaced = True
                    break
        if not replaced:
            new_lines.append(line)

    # Append any top-level keys not already in the file
    for key, value in remaining_top.items():
        new_lines.append(f"{key}: {_yaml_quote(value)}\n")

    # --- pass 2: nested keys --------------------------------------------
    # For each nested path, walk the file, locate (or create) each
    # parent block, and replace or append the leaf scalar.
    for path_parts, value in nested:
        new_lines = _apply_nested_update(new_lines, path_parts, value)

    with open(config_path, "w") as f:
        f.writelines(new_lines)


def _apply_nested_update(lines, path_parts, value):
    """Apply a single nested-key update to a list of YAML lines.

    Walks down the indentation tree looking for each path component.
    If a component doesn't exist, it's appended to its parent block.
    """
    leaf_key = path_parts[-1]
    parents = path_parts[:-1]

    # Locate the insertion region for the parent chain.
    # start, end: line range [start, end) that is "inside" the parent
    # (end points to the first line at parent_indent or less, or len(lines))
    start = 0
    end = len(lines)
    parent_indent = -2  # pretend virtual root
    for idx, parent in enumerate(parents):
        child_indent = parent_indent + 2
        found = -1
        i = start
        while i < end:
            line = lines[i]
            if (
                not line.lstrip().startswith("#")
                and line.strip()
                and _indent_of(line) == child_indent
                and re.match(rf"^{' ' * child_indent}{re.escape(parent)}\s*:", line)
            ):
                found = i
                break
            i += 1
        if found == -1:
            # Parent doesn't exist — append the whole remaining chain
            # at the end of the current region.
            insert_at = end
            new_chunks = []
            chain = parents[idx:] + [leaf_key]
            for depth, comp in enumerate(chain):
                indent = " " * (child_indent + depth * 2)
                if comp == leaf_key:
                    new_chunks.append(f"{indent}{comp}: {_yaml_quote(value)}\n")
                else:
                    new_chunks.append(f"{indent}{comp}:\n")
            return lines[:insert_at] + new_chunks + lines[insert_at:]

        # Parent exists — descend into its block
        start = found + 1
        # Find end of this parent's block: first line whose indent is
        # <= child_indent (and is non-blank non-comment)
        new_end = end
        j = start
        while j < end:
            line = lines[j]
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and _indent_of(line) <= child_indent:
                new_end = j
                break
            j += 1
        end = new_end
        parent_indent = child_indent

    # Now look for the leaf key within [start, end)
    leaf_indent = parent_indent + 2
    for i in range(start, end):
        line = lines[i]
        if (
            not line.lstrip().startswith("#")
            and _indent_of(line) == leaf_indent
            and re.match(rf"^{' ' * leaf_indent}{re.escape(leaf_key)}\s*:", line)
        ):
            lines = lines[:i] + [f"{' ' * leaf_indent}{leaf_key}: {_yaml_quote(value)}\n"] + lines[i + 1:]
            return lines

    # Leaf not found — append at the end of the parent block
    insert_at = end
    new_line = f"{' ' * leaf_indent}{leaf_key}: {_yaml_quote(value)}\n"
    return lines[:insert_at] + [new_line] + lines[insert_at:]


def update_config_yaml(install_dir, display_name=None, server_url=None):
    """Update config.yaml fields (stdlib only — no PyYAML dependency)."""
    if not display_name and not server_url:
        return
    config_path = os.path.join(install_dir, "config.yaml")
    updates = {}
    if server_url:
        updates["server_url"] = server_url
    if display_name:
        updates["display_name"] = display_name
    _update_yaml_file(config_path, **updates)
    if display_name:
        info(f"Set display_name to: {display_name}")
    if server_url:
        info(f"Set server_url to: {server_url}")


def init_database(install_dir):
    """Run Alembic migrations + seed data."""
    run_cmd([get_venv_python(install_dir), "-c", DB_INIT_SCRIPT], cwd=install_dir)


# =========================================================================
# Dependency checks (desktop platforms)
# =========================================================================

def check_macos_deps(mode="both"):
    if mode != "player" and not shutil.which("ffmpeg"):
        warn("FFmpeg not found. Video thumbnails won't be generated.")
        info("Fix: brew install ffmpeg")


def check_windows_deps(mode="both"):
    if mode != "player" and not shutil.which("ffmpeg"):
        warn("FFmpeg not found. Video thumbnails won't be generated.")
        info("Fix: winget install Gyan.FFmpeg")


def check_linux_deps(mode="both"):
    missing = []
    if mode in ("both", "player"):
        if (not shutil.which("cog")
                and not shutil.which("chromium")
                and not shutil.which("chromium-browser")):
            missing.append("chromium or cog")
    if mode != "player" and not shutil.which("ffmpeg"):
        missing.append("ffmpeg")
    if mode != "player":
        try:
            subprocess.run(
                [sys.executable, "-c", "import venv"],
                capture_output=True, check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append("python3-venv")
    if missing:
        warn(f"Missing optional packages: {', '.join(missing)}")
        info(f"Fix: sudo apt install {' '.join(missing)}")


# =========================================================================
# Post-install — platform-specific
# =========================================================================

def macos_post_install(install_dir, non_interactive, port=DEFAULT_PORT):
    plist_dir = os.path.expanduser("~/Library/LaunchAgents")
    plist_path = os.path.join(plist_dir, "com.tinysignage.app.plist")

    if non_interactive or prompt_yn("Generate launchd plist to run on startup?"):
        os.makedirs(plist_dir, exist_ok=True)
        with open(plist_path, "w") as f:
            f.write(LAUNCHD_PLIST.format(install_dir=install_dir, port=port))
        info(f"Created {plist_path}")

        if not non_interactive and prompt_yn("Load it now (start TinySignage)?"):
            run_cmd(["launchctl", "load", plist_path])
            info("TinySignage started via launchd")
    else:
        info("Skipped launchd setup")


def windows_post_install(install_dir, non_interactive, port=DEFAULT_PORT):
    bat_path = os.path.join(install_dir, "start-tinysignage.bat")

    if non_interactive or prompt_yn("Generate start-tinysignage.bat?"):
        with open(bat_path, "w") as f:
            f.write(WINDOWS_BAT.format(install_dir=install_dir, port=port))
        info(f"Created {bat_path}")

        if not non_interactive and prompt_yn(
            "Create shortcut in Startup folder (run on login)?"
        ):
            startup = os.path.join(
                os.environ.get("APPDATA", ""),
                r"Microsoft\Windows\Start Menu\Programs\Startup",
            )
            if os.path.isdir(startup):
                shortcut = os.path.join(startup, "tinysignage.vbs")
                safe_path = bat_path.replace('"', '')
                with open(shortcut, "w") as f:
                    f.write(
                        'CreateObject("WScript.Shell").Run '
                        f'Chr(34) & "{safe_path}" & Chr(34), 0, False\n'
                    )
                info(f"Created startup shortcut: {shortcut}")
            else:
                warn(f"Startup folder not found: {startup}")
    else:
        info("Skipped bat file generation")


def linux_post_install(install_dir, non_interactive, port=DEFAULT_PORT):
    service_dir = os.path.expanduser("~/.config/systemd/user")
    service_path = os.path.join(service_dir, "tinysignage.service")

    if non_interactive or prompt_yn("Generate systemd user service?"):
        os.makedirs(service_dir, exist_ok=True)
        with open(service_path, "w") as f:
            f.write(SYSTEMD_USER.format(install_dir=install_dir, port=port))
        info(f"Created {service_path}")
        info("To start: systemctl --user start tinysignage")
        info("To enable on login: systemctl --user enable tinysignage")
    else:
        info("Skipped systemd user service setup")
        info("To run manually:")
        info(f"  {get_venv_python(install_dir)} -m app.server")


# =========================================================================
# Update mode
# =========================================================================

def _detect_installed_mode(install_dir, plat):
    """Detect what was originally installed by checking for artifacts."""
    has_venv = os.path.isdir(os.path.join(install_dir, "venv"))
    if plat == "pi":
        has_app = os.path.isfile("/etc/systemd/system/signage-app.service")
        has_player = os.path.isfile("/etc/systemd/system/signage-player.service")
        if not has_player:
            # Pi OS Desktop installs the player via XDG autostart (current)
            # or as a systemd user unit (legacy, broken — kept here so
            # `--update` can detect and self-heal those installs).
            try:
                import pwd
                du = detect_desktop_user()
                home = pwd.getpwnam(du).pw_dir
                autostart = os.path.join(
                    home, ".config/autostart/signage-player.desktop")
                legacy_unit = os.path.join(
                    home, ".config/systemd/user/signage-player.service")
                has_player = (
                    os.path.isfile(autostart)
                    or os.path.isfile(legacy_unit)
                )
            except (ImportError, KeyError):
                pass
    else:
        has_app = has_venv  # desktop CMS always has a venv
        has_player = False  # desktop player has no detectable service
    if has_app and has_player:
        return "both"
    if has_app:
        return "cms"
    return "player"


def git_pull_install_dir(install_dir, runner):
    """Run 'git pull --ff-only' in install_dir. Returns True on success.

    Never calls error_exit — caller must continue on failure so that
    deps/migrations/restart still run (they're useful self-heals even
    when the code itself can't be updated, e.g. offline or SSH auth).

    `runner` is a callable matching run_cmd's signature so we can route
    git through `runuser -u tinysignage` on Pi and plain subprocess on
    desktop/macOS without branching inside this helper.

    Handles user-modified config files via git stash push/pop so that
    upstream changes are merged cleanly with local values preserved.
    """
    git_marker = os.path.join(install_dir, ".git")
    if not os.path.exists(git_marker):  # may be a file (worktree), not a dir
        warn("Not a git working tree — skipping code update.")
        return False

    if not shutil.which("git"):
        warn("git not found in PATH — skipping code update.")
        return False

    # Detect remote URL first so we can tailor the failure hint if pull fails.
    r = runner(["git", "remote", "get-url", "origin"],
               cwd=install_dir, capture=True, check=False)
    remote_url = (r.stdout.strip() if r and r.returncode == 0 else "")
    is_ssh = remote_url.startswith("git@") or remote_url.startswith("ssh://")

    # --- Classify porcelain output ----------------------------------------
    config_path = os.path.join(install_dir, "config.yaml")
    did_stash = False
    saved_values = {}

    r = runner(["git", "status", "--porcelain"],
               cwd=install_dir, capture=True, check=False)
    if r and r.returncode == 0 and r.stdout.strip():
        tracked_modified = set()
        for line in r.stdout.strip().splitlines():
            status = line[:2]
            fname = line[2:].strip()
            if status == "??":
                # Untracked files — git pull won't touch them, safe to ignore.
                continue
            tracked_modified.add(fname)

        managed = tracked_modified & _GIT_MANAGED_CONFIGS
        unexpected = tracked_modified - _GIT_MANAGED_CONFIGS
        if unexpected:
            # Try to auto-reset unexpected modifications so they don't
            # block the update (e.g. media/.gitkeep touched by media ops,
            # or phantom index entries from SD card filesystem corruption).
            for fname in sorted(unexpected):
                info(f"Auto-resetting unexpected modification: {fname}")
                rc = runner(["git", "checkout", "HEAD", "--", fname],
                            cwd=install_dir, capture=True, check=False)
                if not rc or rc.returncode != 0:
                    # File not in HEAD (corrupt index entry) — clear it.
                    runner(["git", "reset", "HEAD", "--", fname],
                           cwd=install_dir, capture=True, check=False)

            # Re-check status after cleanup.
            r = runner(["git", "status", "--porcelain"],
                       cwd=install_dir, capture=True, check=False)
            tracked_modified = set()
            if r and r.returncode == 0 and r.stdout.strip():
                for line in r.stdout.strip().splitlines():
                    status = line[:2]
                    fname = line[2:].strip()
                    if status == "??":
                        continue
                    tracked_modified.add(fname)
            managed = tracked_modified & _GIT_MANAGED_CONFIGS
            unexpected = tracked_modified - _GIT_MANAGED_CONFIGS

            if unexpected:
                flist = ", ".join(sorted(unexpected))
                warn(f"Unexpected local modifications — skipping git pull: {flist}\n"
                     "Commit or stash these changes, then re-run the update.")
                return False

        # Stash managed config files so git pull sees a clean tree.
        if managed:
            # Save critical keys as last-resort fallback before any git ops.
            saved_values = _read_yaml_values(
                config_path, _CONFIG_YAML_CRITICAL_KEYS)

            r = runner(
                ["git", "stash", "push", "-m", "tinysignage-update"] +
                ["--", *sorted(managed)],
                cwd=install_dir, capture=True, check=False)
            if r and r.returncode == 0:
                did_stash = True
            else:
                warn("Could not stash config files — skipping git pull.")
                return False

    # --- Capture HEAD before ----------------------------------------------
    r = runner(["git", "rev-parse", "--short", "HEAD"],
               cwd=install_dir, capture=True, check=False)
    head_before = r.stdout.strip() if r and r.returncode == 0 else ""

    # --- The pull itself --------------------------------------------------
    r = runner(["git", "pull", "--ff-only"],
               cwd=install_dir, capture=True, check=False)
    pull_ok = r and r.returncode == 0

    if not pull_ok:
        err = (r.stderr.strip() if r and r.stderr else "") or "(no output)"
        warn(f"git pull failed — continuing without code update:\n{err}")
        if is_ssh:
            warn(
                "This clone uses SSH (git@github.com:...). The service user "
                "has no SSH keys. Switch the remote to HTTPS:\n"
                f"  sudo -u {SERVICE_USER} git -C {install_dir} remote set-url origin \\\n"
                "    https://github.com/<owner>/<repo>.git\n"
                "Then re-run the update."
            )

    # --- Restore stashed config -------------------------------------------
    if did_stash:
        r = runner(["git", "stash", "pop"],
                   cwd=install_dir, capture=True, check=False)
        if not r or r.returncode != 0:
            # Conflict — accept upstream version and overlay critical keys.
            warn("Stash pop had conflicts — accepting upstream config "
                 "and restoring critical values.")
            runner(["git", "checkout", "--theirs", "."],
                   cwd=install_dir, capture=True, check=False)
            runner(["git", "reset", "HEAD"],
                   cwd=install_dir, capture=True, check=False)
            if saved_values:
                _update_yaml_file(config_path, **saved_values)
    elif not pull_ok and saved_values:
        # Stash wasn't attempted but we saved values — restore them.
        _update_yaml_file(config_path, **saved_values)

    if not pull_ok:
        return False

    # --- Capture HEAD after -----------------------------------------------
    r = runner(["git", "rev-parse", "--short", "HEAD"],
               cwd=install_dir, capture=True, check=False)
    head_after = r.stdout.strip() if r and r.returncode == 0 else ""

    if head_before and head_after and head_before == head_after:
        info("Already up to date.")
    elif head_before and head_after:
        r = runner(["git", "rev-list", "--count", f"{head_before}..{head_after}"],
                   cwd=install_dir, capture=True, check=False)
        n = r.stdout.strip() if r and r.returncode == 0 else "?"
        plural = "commit" if n == "1" else "commits"
        info(f"Updated {head_before} → {head_after} ({n} new {plural})")
    else:
        info("git pull completed.")
    return True


def _no_venv_error(plat, install_dir):
    """Exit with an actionable hint when --update can't find a venv."""
    msg = f"No venv found at {os.path.join(install_dir, 'venv')}."
    if plat == "pi" and os.path.isdir(os.path.join(TARGET_DIR, "venv")) \
            and os.path.realpath(install_dir) != os.path.realpath(TARGET_DIR):
        msg += (
            f"\n\nYour TinySignage is installed at {TARGET_DIR}, but you're "
            f"running --update from {install_dir}.\n\n"
            f"To update, run:\n"
            f"  cd {TARGET_DIR}\n"
            f"  sudo python3 install.py --update"
        )
    else:
        msg += (
            "\n\nRun --update from the directory where TinySignage was "
            "originally installed (the one containing 'venv/').\n\n"
            "For a fresh install instead, run install.py without --update."
        )
    error_exit(msg)


def do_update(plat, install_dir, skip_pull=False):
    """Update an existing installation: pull, deps, migrations, restart."""
    print("=== TinySignage Update ===\n")

    mode = _detect_installed_mode(install_dir, plat)
    info(f"Detected install mode: {mode}")
    info(f"Install directory: {install_dir}")
    print()

    has_venv = os.path.isdir(os.path.join(install_dir, "venv"))

    if not has_venv and mode != "player":
        _no_venv_error(plat, install_dir)

    # Pick a runner so git (and anything else) goes through the right
    # user context on Pi without branching inside helpers.
    if plat == "pi":
        if os.geteuid() != 0:
            error_exit("Pi update requires root. Run: sudo python3 install.py --update")
        runner = lambda cmd, **kw: run_as_user(SERVICE_USER, cmd, **kw)
    else:
        runner = run_cmd

    # total_steps: pull + (deps + migrations) + restart for CMS installs;
    #              pull + reboot-hint for player-only Pi installs.
    total_steps = 4 if has_venv else 2
    step_num = 1

    # --- Step 1: git pull ------------------------------------------------
    if skip_pull:
        step(step_num, total_steps, "Skipping git pull (--no-pull)")
    else:
        step(step_num, total_steps, "Pulling latest code...")
        git_pull_install_dir(install_dir, runner)
    step_num += 1

    if plat == "pi":
        if has_venv:
            step(step_num, total_steps, "Updating Python dependencies...")
            pip = get_venv_pip(install_dir)
            run_as_user(SERVICE_USER, [
                pip, "install", "--quiet",
                "-r", os.path.join(install_dir, "requirements.txt"),
            ], cwd=install_dir)
            step_num += 1

            step(step_num, total_steps, "Running database migrations...")
            run_as_user(SERVICE_USER, [
                get_venv_python(install_dir), "-c", DB_INIT_SCRIPT,
            ], cwd=install_dir)
            step_num += 1

            # Self-heal installs that pre-date HTTPS support: the systemd
            # unit lists certs/ in ReadWritePaths, but older installs never
            # created the directory, so enabling HTTPS via the setup wizard
            # fails with EROFS under ProtectSystem=strict.
            certs_dir = os.path.join(install_dir, "certs")
            if not os.path.isdir(certs_dir):
                run_as_user(SERVICE_USER, ["mkdir", "-p", certs_dir])
                info("Created missing certs/ directory for HTTPS support")

        step(step_num, total_steps, "Restarting services...")
        for svc in ["signage-app", "signage-player"]:
            if os.path.isfile(f"/etc/systemd/system/{svc}.service"):
                run_cmd(["systemctl", "restart", svc])
                info(f"Restarted {svc}")
            else:
                info(f"Skipped {svc} (not installed)")
        # Self-heal legacy broken installs: if the old user unit exists
        # but the new autostart file does not, install the autostart now.
        try:
            import pwd
            du = detect_desktop_user()
            pw = pwd.getpwnam(du)
            legacy_unit = os.path.join(
                pw.pw_dir, ".config/systemd/user/signage-player.service")
            new_autostart = os.path.join(
                pw.pw_dir, ".config/autostart/signage-player.desktop")
            if os.path.isfile(legacy_unit) and not os.path.isfile(new_autostart):
                info("Repairing legacy broken player install (user unit → autostart)")
                standalone = not os.path.isdir(os.path.join(install_dir, "venv"))
                _install_player_autostart(install_dir, du, standalone)
        except (ImportError, KeyError):
            pass

        # Self-heal: apply labwc rc.xml cursor config to existing installs
        if shutil.which("labwc"):
            try:
                import pwd
                du = detect_desktop_user()
                pw = pwd.getpwnam(du)
                _configure_labwc_rc_xml(pw.pw_dir, pw.pw_uid, pw.pw_gid)
                _configure_labwc_autostart(pw.pw_dir, pw.pw_uid, pw.pw_gid)
            except (ImportError, KeyError):
                pass

        # Pi OS Desktop player is launched via XDG autostart, so there is
        # no "service" to restart — killing chromium mid-session would
        # briefly flash the desktop. Tell the user to reboot instead.
        try:
            import pwd
            du = detect_desktop_user()
            desktop_path = os.path.join(
                pwd.getpwnam(du).pw_dir,
                ".config/autostart/signage-player.desktop",
            )
            if os.path.isfile(desktop_path):
                info("Player will pick up new code on next reboot.")
                info("To apply changes now: sudo reboot")
        except (ImportError, KeyError):
            pass

    else:
        step(step_num, total_steps, "Updating Python dependencies...")
        install_deps(install_dir)
        step_num += 1

        step(step_num, total_steps, "Running database migrations...")
        init_database(install_dir)
        step_num += 1

        step(step_num, total_steps, "Restarting services...")
        if plat == "macos":
            plist = os.path.expanduser(
                "~/Library/LaunchAgents/com.tinysignage.app.plist"
            )
            if os.path.isfile(plist):
                run_cmd(["launchctl", "unload", plist], check=False)
                run_cmd(["launchctl", "load", plist])
                info("launchd service restarted")
            else:
                info("No launchd plist found — restart manually")
        else:
            service_path = os.path.expanduser(
                "~/.config/systemd/user/tinysignage.service"
            )
            if os.path.isfile(service_path):
                run_cmd(["systemctl", "--user", "restart", "tinysignage"], check=False)
                info("systemd user service restarted")
            else:
                info("Restart the application manually")

    print("\nUpdate complete!")


# =========================================================================
# Uninstall mode
# =========================================================================

def _remove_path(path, label=None):
    """Remove a file, symlink, or directory if it exists. Tolerate missing."""
    label = label or path
    try:
        if os.path.islink(path) or os.path.isfile(path):
            os.remove(path)
            info(f"Removed {label}")
            return True
        if os.path.isdir(path):
            shutil.rmtree(path)
            info(f"Removed {label}")
            return True
    except OSError as e:
        warn(f"Could not remove {label}: {e}")
    return False


def _stop_and_remove_system_unit(name):
    """Stop, disable, and remove /etc/systemd/system/<name>.service.

    Returns True if the unit existed and was removed, False otherwise.
    """
    unit_file = f"/etc/systemd/system/{name}.service"
    if not os.path.isfile(unit_file):
        return False
    run_cmd(["systemctl", "stop", name], check=False)
    run_cmd(["systemctl", "disable", name], check=False)
    _remove_path(unit_file, label=f"{name}.service")
    return True


def _strip_labwc_autostart_cursor(home_dir):
    """Remove the cursor-hiding lines we added to labwc autostart."""
    autostart_path = os.path.join(home_dir, ".config", "labwc", "autostart")
    if not os.path.isfile(autostart_path):
        return
    try:
        with open(autostart_path) as f:
            lines = f.readlines()
    except OSError:
        return
    kept = [
        ln for ln in lines
        if _LABWC_AUTOSTART_MARKER not in ln
        and "wtype -M alt -M logo -P h" not in ln
    ]
    if kept == lines:
        return
    try:
        if any(ln.strip() for ln in kept):
            with open(autostart_path, "w") as f:
                f.writelines(kept)
            info(f"Cleaned cursor lines from {autostart_path}")
        else:
            os.remove(autostart_path)
            info(f"Removed empty {autostart_path}")
    except OSError as e:
        warn(f"Could not update {autostart_path}: {e}")


def _strip_labwc_cursor_from_rc_xml(home_dir):
    """Remove the <cursor> element and HideCursor keybind we added to rc.xml.

    Deletes the file if it becomes effectively empty (root with no children).
    """
    import xml.etree.ElementTree as ET

    rc_path = os.path.join(home_dir, ".config", "labwc", "rc.xml")
    if not os.path.isfile(rc_path):
        return
    try:
        tree = ET.parse(rc_path)
        root = tree.getroot()
        changed = False

        cursor_el = root.find("cursor")
        if cursor_el is not None:
            root.remove(cursor_el)
            changed = True

        # Remove the HideCursor keybind we added
        keyboard_el = root.find("keyboard")
        if keyboard_el is not None:
            for kb in keyboard_el.findall("keybind"):
                if kb.get("key") == "A-W-h":
                    for action in kb.findall("action"):
                        if action.get("name") == "HideCursor":
                            keyboard_el.remove(kb)
                            changed = True
                            break
            # Remove empty <keyboard> element
            if len(keyboard_el) == 0:
                root.remove(keyboard_el)

        if not changed:
            return
        if len(root) == 0:
            os.remove(rc_path)
            info(f"Removed empty {rc_path}")
        else:
            ET.indent(tree, space="  ")
            tree.write(rc_path, xml_declaration=True, encoding="UTF-8")
            info(f"Removed cursor config from {rc_path}")
    except Exception as e:
        warn(f"Could not clean labwc rc.xml: {e}")


def _strip_labwc_cursor_lines(home_dir):
    """Remove the XCURSOR_THEME=hidden / XCURSOR_SIZE=1 lines we wrote
    into a labwc environment file. Leaves any other lines intact, and
    deletes the file if it becomes empty.
    """
    env_path = os.path.join(home_dir, ".config", "labwc", "environment")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path) as f:
            lines = f.readlines()
    except OSError:
        return
    kept = [
        ln for ln in lines
        if ln.strip() not in ("XCURSOR_THEME=hidden", "XCURSOR_SIZE=1")
    ]
    if kept == lines:
        return
    try:
        if any(ln.strip() for ln in kept):
            with open(env_path, "w") as f:
                f.writelines(kept)
            info(f"Cleaned cursor lines from {env_path}")
        else:
            os.remove(env_path)
            info(f"Removed empty {env_path}")
    except OSError as e:
        warn(f"Could not update {env_path}: {e}")


def _backup_pi_data(install_dir):
    """Move user data out of install_dir to a timestamped backup directory.

    Returns the backup path, or None if there was nothing to back up.
    Backup goes into the invoking sudo user's home dir if available,
    otherwise /root.
    """
    import time
    items = [
        name for name in ("db", "media", "config.yaml", "config.env")
        if os.path.exists(os.path.join(install_dir, name))
    ]
    if not items:
        return None
    sudo_user = os.environ.get("SUDO_USER")
    backup_parent = "/root"
    owner_uid = owner_gid = None
    if sudo_user:
        try:
            import pwd
            pw = pwd.getpwnam(sudo_user)
            backup_parent = pw.pw_dir
            owner_uid, owner_gid = pw.pw_uid, pw.pw_gid
        except (ImportError, KeyError):
            pass
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = os.path.join(backup_parent, f"tinysignage-backup-{timestamp}")
    try:
        os.makedirs(backup_dir)
    except OSError as e:
        warn(f"Could not create backup directory {backup_dir}: {e}")
        return None
    for name in items:
        try:
            shutil.move(
                os.path.join(install_dir, name),
                os.path.join(backup_dir, name),
            )
        except OSError as e:
            warn(f"Could not back up {name}: {e}")
    if owner_uid is not None:
        for root, dirs, files in os.walk(backup_dir):
            try:
                os.chown(root, owner_uid, owner_gid)
            except OSError:
                pass
            for f in files:
                try:
                    os.chown(os.path.join(root, f), owner_uid, owner_gid)
                except OSError:
                    pass
    info(f"Backed up data to: {backup_dir}")
    return backup_dir


def do_uninstall(plat, install_dir, non_interactive=False, purge=False):
    """Remove TinySignage from this device."""
    print("=== TinySignage Uninstall ===\n")
    print("This will remove TinySignage services, files, and the service user.")
    print("Hostname, autologin, and boot config tweaks are left alone.")
    print()

    if not non_interactive:
        if not prompt_yn("Are you sure you want to uninstall?", default=False):
            print("Cancelled.")
            return
        keep_data = prompt_yn(
            "Keep your media files and database? (saves a backup)",
            default=True,
        )
    else:
        keep_data = not purge
    print()

    if plat == "pi":
        _uninstall_pi(install_dir, keep_data)
    else:
        _uninstall_desktop(plat, install_dir, keep_data)

    print()
    print("=" * 50)
    print("  Uninstall complete.")
    print("=" * 50)


def _uninstall_pi(install_dir, keep_data):
    """Remove all TinySignage state from a Raspberry Pi."""
    if os.geteuid() != 0:
        error_exit(
            "Pi uninstall requires root. "
            "Run: sudo python3 install.py --uninstall"
        )

    total = 6

    # --- [1] Stop and remove system services ---
    step(1, total, "Stopping and removing system services...")
    _stop_and_remove_system_unit("signage-app")
    lite_player_removed = _stop_and_remove_system_unit("signage-player")
    run_cmd(["systemctl", "daemon-reload"], check=False)

    # --- [2] Remove desktop player artifacts ---
    step(2, total, "Removing player desktop entries...")
    desktop_user = None
    try:
        desktop_user = detect_desktop_user()
    except Exception:
        pass
    if desktop_user:
        try:
            import pwd
            home = pwd.getpwnam(desktop_user).pw_dir
            _remove_path(
                os.path.join(home, ".config/autostart/signage-player.desktop"),
                label="player autostart entry",
            )
            _remove_legacy_player_user_unit(desktop_user)
            _strip_labwc_cursor_lines(home)
            _strip_labwc_cursor_from_rc_xml(home)
            _strip_labwc_autostart_cursor(home)
        except (ImportError, KeyError):
            pass
    # The pre-fix installer wrote the labwc env file under the SERVICE_USER
    # home by mistake — clean that up too if present.
    try:
        import pwd
        su_home = pwd.getpwnam(SERVICE_USER).pw_dir
        _strip_labwc_cursor_lines(su_home)
        _strip_labwc_cursor_from_rc_xml(su_home)
        _strip_labwc_autostart_cursor(su_home)
    except (ImportError, KeyError):
        pass

    # --- [3] Remove transparent cursor theme ---
    step(3, total, "Removing transparent cursor theme...")
    _remove_path("/usr/share/icons/hidden", label="cursor theme")

    # --- [4] Restore tty1 if Lite cage masked it ---
    if lite_player_removed:
        step(4, total, "Restoring tty1 console...")
        run_cmd(["systemctl", "unmask", "getty@tty1.service"], check=False)
        run_cmd(["systemctl", "enable", "getty@tty1.service"], check=False)
    else:
        step(4, total, "Restoring tty1 console... (skipped — not Lite)")

    # --- [5] Back up data and remove install directory ---
    step(5, total, "Removing install directory...")
    if os.path.isdir(TARGET_DIR):
        # Make sure we're not running from inside the dir we're deleting.
        try:
            os.chdir("/")
        except OSError:
            pass
        if keep_data:
            _backup_pi_data(TARGET_DIR)
        try:
            shutil.rmtree(TARGET_DIR)
            info(f"Removed {TARGET_DIR}")
        except OSError as e:
            warn(f"Could not remove {TARGET_DIR}: {e}")
    else:
        info(f"{TARGET_DIR} not found")

    # --- [6] Remove service user ---
    step(6, total, "Removing service user...")
    r = run_cmd(["id", SERVICE_USER], capture=True, check=False)
    if r and r.returncode == 0:
        run_cmd(["userdel", "-r", SERVICE_USER], check=False)
        info(f"Removed user '{SERVICE_USER}'")
    else:
        info(f"User '{SERVICE_USER}' not present")


def _uninstall_desktop(plat, install_dir, keep_data):
    """Remove TinySignage launcher state from macOS, Windows, or desktop Linux.

    The repository directory itself is left in place — on these
    platforms users typically run from a clone, so deleting it would be
    surprising. Only the launcher hook (plist / user unit / .bat) is
    removed, plus optionally the runtime data inside the repo.
    """
    info(f"On {plat}, the repository directory itself will be left alone.")
    info("Only the launcher service and (optionally) runtime data will be removed.")
    print()

    if plat == "macos":
        plist = os.path.expanduser(
            "~/Library/LaunchAgents/com.tinysignage.app.plist"
        )
        if os.path.isfile(plist):
            run_cmd(["launchctl", "unload", plist], check=False)
            _remove_path(plist, label="launchd plist")
        else:
            info("No launchd plist found")
    elif plat == "linux":
        service = os.path.expanduser(
            "~/.config/systemd/user/tinysignage.service"
        )
        if os.path.isfile(service):
            run_cmd(["systemctl", "--user", "stop", "tinysignage"], check=False)
            run_cmd(["systemctl", "--user", "disable", "tinysignage"], check=False)
            _remove_path(service, label="systemd user unit")
        else:
            info("No systemd user unit found")
    elif plat == "windows":
        bat = os.path.join(install_dir, "start-tinysignage.bat")
        if os.path.isfile(bat):
            _remove_path(bat, label="start batch file")
        else:
            info("No start batch file found")

    # Runtime data inside the repo
    if not keep_data:
        info("Removing runtime data (db, media, venv, config.env)...")
        for name in ("db", "media", "venv", "config.env"):
            path = os.path.join(install_dir, name)
            if os.path.exists(path):
                _remove_path(path, label=name)
    else:
        info("Runtime data left in place (db, media, venv, config.env).")


# =========================================================================
# Main install flows
# =========================================================================

def install_pi(install_dir, display_name, non_interactive, mode="both", server_url=None, port=DEFAULT_PORT):
    """Full Raspberry Pi install."""
    if os.geteuid() != 0:
        error_exit("Pi install requires root. Run: sudo python3 install.py")

    mode_labels = {"both": "CMS + Player", "cms": "CMS Only", "player": "Player Only"}
    print(f"=== TinySignage Pi Installer ({mode_labels[mode]}) ===\n")

    # Sanity check
    if not os.path.isfile(os.path.join(install_dir, "config.yaml")):
        error_exit(f"config.yaml not found in {install_dir} — is this the repo root?")

    # Prompt for display name
    if not display_name:
        if non_interactive:
            display_name = "TinySignage"
        else:
            print('Give this display a name (e.g. "Lobby TV", "Menu Board").')
            print("This also sets the hostname so you can reach the CMS")
            print("from other devices (e.g. lobby-tv.local:8080/cms).\n")
            display_name = prompt_input("Display Name", "TinySignage")

    hostname = sanitize_hostname(display_name)
    print(f"  Hostname: {hostname}.local\n")

    lite = is_pi_lite()

    # Move to /opt/tinysignage
    install_dir = pi_move_to_opt(install_dir, non_interactive)
    print()

    # ---- System setup (as root) ----
    pi_system_setup(install_dir, display_name, hostname, lite, mode, port)
    print()

    # ---- App setup ----
    if mode == "player" and not server_url:
        error_exit("Player mode requires a server URL (--server-url)")

    if mode == "player":
        # Player-only: minimal setup, no backend needed
        print("=== Player Setup ===\n")
        total = 2

        step(1, total, "Creating directories...")
        run_as_user(SERVICE_USER, [
            "mkdir", "-p", os.path.join(install_dir, "data", "browser-profile"),
        ])

        step(2, total, "Configuring CMS server connection...")
        update_config_yaml(install_dir, display_name=display_name, server_url=server_url)
        run_cmd(["chown", f"{SERVICE_USER}:{SERVICE_USER}",
                 os.path.join(install_dir, "config.yaml")])

    else:
        # CMS or Both: full app setup
        print("=== App Setup ===\n")
        total = 6
        python_cmd = find_python()
        venv_dir = os.path.join(install_dir, "venv")
        venv_python = get_venv_python(install_dir)
        pip_cmd = get_venv_pip(install_dir)

        step(1, total, "Creating virtual environment...")
        if os.path.isdir(venv_dir):
            info("venv already exists")
        else:
            run_as_user(SERVICE_USER, [python_cmd, "-m", "venv", venv_dir],
                         cwd=install_dir)

        step(2, total, "Installing Python dependencies...")
        run_as_user(SERVICE_USER, [
            pip_cmd, "install", "--quiet",
            "-r", os.path.join(install_dir, "requirements.txt"),
        ], cwd=install_dir)

        step(3, total, "Creating directories...")
        # certs/ must exist before signage-app.service starts so systemd's
        # ReadWritePaths bind-mount lands on a real directory — otherwise
        # ProtectSystem=strict leaves /opt/tinysignage read-only and the
        # setup wizard's ensure_cert() fails with EROFS when the user
        # enables HTTPS.
        for d in ["media", "media/thumbs", "db", "logs", "certs"]:
            run_as_user(SERVICE_USER, [
                "mkdir", "-p", os.path.join(install_dir, d),
            ])

        step(4, total, "Generating config.env...")
        config_env = os.path.join(install_dir, "config.env")
        if os.path.isfile(config_env):
            info("config.env already exists")
        else:
            secret_key = secrets.token_hex(32)
            fd = os.open(config_env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write("# TinySignage environment config (auto-generated)\n")
                f.write(f"SECRET_KEY={secret_key}\n")
            run_cmd(["chown", f"{SERVICE_USER}:{SERVICE_USER}", config_env])
            info("Generated config.env with SECRET_KEY")

        step(5, total, "Updating config.yaml...")
        local_url = server_url or f"https://localhost:{port}"
        update_config_yaml(install_dir, display_name=display_name, server_url=local_url)
        run_cmd(["chown", f"{SERVICE_USER}:{SERVICE_USER}",
                 os.path.join(install_dir, "config.yaml")])

        step(6, total, "Initializing database...")
        run_as_user(SERVICE_USER, [venv_python, "-c", DB_INIT_SCRIPT], cwd=install_dir)

    # Success
    print()
    print("=" * 50)
    if mode == "player":
        print("  Player installation complete! Reboot to start:")
        print()
        print("    sudo reboot")
        print()
        print("  After reboot:")
        print(f"    Player connects to: {server_url}")
        print(f"    Manage content at:  {server_url}/cms")
    elif mode == "cms":
        print("  CMS installation complete! Reboot to start:")
        print()
        print("    sudo reboot")
        print()
        print("  After reboot, open the CMS at either:")
        print(f"    https://{hostname}.local:{port}/cms")
        ip = _get_primary_ip()
        if ip:
            print(f"    https://{ip}:{port}/cms   (use this if .local doesn't resolve)")
        print()
        print("  Your browser will warn about the self-signed cert on first visit — click Advanced → Proceed.")
        print()
        print("  Point your player devices at this server during their install.")
    else:
        print("  Installation complete! Reboot to start:")
        print()
        print("    sudo reboot")
        print()
        print("  After reboot, open the CMS at either:")
        print(f"    https://{hostname}.local:{port}/cms")
        ip = _get_primary_ip()
        if ip:
            print(f"    https://{ip}:{port}/cms   (use this if .local doesn't resolve)")
        print()
        print("  Your browser will warn about the self-signed cert on first visit — click Advanced → Proceed.")
        print("  The player launches automatically on the display.")
    print("=" * 50)


def install_desktop(plat, install_dir, non_interactive, mode="both", server_url=None, port=DEFAULT_PORT):
    """Install for macOS, Windows, or desktop Linux."""
    names = {"macos": "macOS", "windows": "Windows", "linux": "Linux"}
    mode_suffix = {"both": "", "cms": " (CMS Only)", "player": " (Player Only)"}
    print(f"=== TinySignage {names[plat]} Installer{mode_suffix[mode]} ===\n")

    # Sanity check
    if not os.path.isfile(os.path.join(install_dir, "config.yaml")):
        error_exit(f"config.yaml not found in {install_dir} — is this the repo root?")

    if mode == "player":
        # Player-only: just save server_url and print instructions
        # No venv exists for player-only — use the current interpreter
        print("Configuring player to connect to remote CMS...\n")
        update_config_yaml(install_dir, server_url=server_url)

        print()
        print("=" * 50)
        print("  Player setup complete!")
        print()
        print("  Open this URL in any browser:")
        print(f"    {server_url}/player")
        print()
        print("  Or run the kiosk launcher:")
        if plat == "windows":
            print(r"    python launcher.py")
        else:
            print("    python3 launcher.py")
        print("=" * 50)
        return

    # CMS or Both: full setup
    # Dependency checks
    {"macos": check_macos_deps, "windows": check_windows_deps,
     "linux": check_linux_deps}[plat](mode)
    print()

    # App setup
    total = 5

    step(1, total, "Creating virtual environment...")
    setup_venv(install_dir)

    step(2, total, "Installing Python dependencies...")
    install_deps(install_dir)

    step(3, total, "Creating directories...")
    create_directories(install_dir)

    step(4, total, "Generating config.env...")
    generate_config_env(install_dir)

    step(5, total, "Initializing database...")
    init_database(install_dir)

    # Set server_url so the player knows where to connect
    if mode == "both":
        update_config_yaml(install_dir, server_url=f"https://localhost:{port}")

    print()

    # Platform-specific post-install
    {"macos": macos_post_install, "windows": windows_post_install,
     "linux": linux_post_install}[plat](install_dir, non_interactive, port)

    # Success message
    print()
    print("=" * 50)
    print("  Installation complete!")
    print()
    if plat == "windows":
        bat = os.path.join(install_dir, "start-tinysignage.bat")
        if os.path.isfile(bat):
            print("  Start: double-click start-tinysignage.bat")
        else:
            print(r"  Start: venv\Scripts\activate && python -m app.server")
    else:
        print("  Start: source venv/bin/activate && python -m app.server")
    print()
    print(f"  Setup wizard: http://localhost:{port}/setup  (first run)")
    print(f"  CMS:          http://localhost:{port}/cms")
    if mode == "both":
        print(f"  Player:       http://localhost:{port}/player")
    elif mode == "cms":
        print()
        print("  Point your player devices at this machine's address during their install.")
    print("=" * 50)


# =========================================================================
# CLI entry point
# =========================================================================

def main():
    check_python_version()

    parser = argparse.ArgumentParser(
        description="TinySignage cross-platform installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              python3 install.py                                         Interactive install
              python3 install.py --mode cms                              CMS server only
              python3 install.py --mode player --server-url http://cms.local:8080   Player only
              python3 install.py --update                                Update existing install
              sudo python3 install.py --uninstall                        Remove TinySignage
              sudo python3 install.py --non-interactive --display-name "Lobby TV"   Scripted Pi
        """),
    )
    parser.add_argument(
        "--update", action="store_true",
        help="update existing install (git pull + pip deps + db migrations + restart)",
    )
    parser.add_argument(
        "--no-pull", action="store_true",
        help="with --update, skip the automatic 'git pull' step",
    )
    parser.add_argument(
        "--uninstall", action="store_true",
        help="remove TinySignage services, files, and service user",
    )
    parser.add_argument(
        "--purge", action="store_true",
        help="with --uninstall --non-interactive, also delete media and database",
    )
    parser.add_argument(
        "--mode", choices=["both", "cms", "player"],
        help="install mode: both (CMS + Player), cms (server only), player (display only)",
    )
    parser.add_argument(
        "--server-url",
        help="CMS server URL for player-only installs (e.g. http://192.168.1.50:8080)",
    )
    parser.add_argument(
        "--display-name",
        help="display name (Pi only; also sets hostname)",
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"server port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--non-interactive", action="store_true",
        help="skip all prompts, use defaults",
    )
    args = parser.parse_args()

    if args.update and args.uninstall:
        error_exit("--update and --uninstall are mutually exclusive")

    install_dir = os.path.dirname(os.path.abspath(__file__))
    plat = detect_platform()
    print(f"Detected platform: {plat}\n")

    if args.uninstall:
        do_uninstall(plat, install_dir, args.non_interactive, args.purge)
        return

    if args.update:
        do_update(plat, install_dir, skip_pull=args.no_pull)
        return

    # Determine install mode
    mode = args.mode
    if not mode and not args.non_interactive:
        mode = prompt_mode()
    elif not mode:
        mode = "both"

    # Get server URL for player-only mode
    server_url = args.server_url
    if mode == "player" and not server_url:
        if args.non_interactive:
            error_exit("Player-only mode requires --server-url")
        server_url = prompt_server_url()

    # Validate server URL reachability (warning only — doesn't block install)
    if mode == "player" and server_url:
        validate_server_url(server_url)

    print()

    port = args.port

    if plat == "pi":
        install_pi(install_dir, args.display_name, args.non_interactive, mode, server_url, port)
    else:
        install_desktop(plat, install_dir, args.non_interactive, mode, server_url, port)


if __name__ == "__main__":
    main()
