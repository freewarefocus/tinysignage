#!/usr/bin/env python3
"""TinySignage cross-platform installer.

Usage:
    python3 install.py              # Interactive install
    python3 install.py --update     # Update existing install
    python3 install.py --non-interactive --display-name "Lobby TV"  # Scripted Pi

Requires Python 3.9+. Uses only the standard library (runs before venv exists).
"""

import argparse
import os
import platform
import re
import secrets
import shutil
import struct
import subprocess
import sys
import textwrap

# =========================================================================
# Constants & templates
# =========================================================================

MIN_PYTHON = (3, 9)
SERVICE_USER = "tinysignage"
TARGET_DIR = "/opt/tinysignage"
DEFAULT_PORT = 8080

# --- Systemd unit templates (Pi) ----------------------------------------

SYSTEMD_APP = """\
[Unit]
Description=TinySignage Backend
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={install_dir}
ExecStart={install_dir}/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths={install_dir}/media {install_dir}/db {install_dir}/logs {install_dir}/config.yaml {install_dir}/config.env
MemoryMax=512M

[Install]
WantedBy=multi-user.target
"""

SYSTEMD_PLAYER = """\
[Unit]
Description=TinySignage Player (Kiosk Browser)
After=signage-app.service graphical.target
Wants=signage-app.service
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User={user}
Environment=DISPLAY=:0
Environment=XCURSOR_THEME=hidden
Environment=XCURSOR_SIZE=1
ExecStartPre=/bin/sleep 5
ExecStart={install_dir}/venv/bin/python {install_dir}/launcher.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=graphical.target
"""

SYSTEMD_PLAYER_LITE = """\
[Unit]
Description=TinySignage Player (Kiosk Browser — Lite)
After=signage-app.service multi-user.target
Wants=signage-app.service
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User={user}

# cage creates its own Wayland session on this TTY
TTYPath=/dev/tty1
StandardInput=tty-force
StandardOutput=journal
StandardError=journal

RuntimeDirectory=tinysignage
Environment=XDG_RUNTIME_DIR=/run/tinysignage

ExecStartPre=/bin/sleep 5
ExecStart=/usr/bin/cage -d -s -- {install_dir}/venv/bin/python {install_dir}/launcher.py
WatchdogSec=120
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

# --- Standalone player systemd units (player-only, no local backend) ------

SYSTEMD_PLAYER_STANDALONE = """\
[Unit]
Description=TinySignage Player (Kiosk Browser)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User={user}
Environment=DISPLAY=:0
Environment=XCURSOR_THEME=hidden
Environment=XCURSOR_SIZE=1
ExecStartPre=/bin/sleep 5
ExecStart=/usr/bin/python3 {install_dir}/launcher.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=graphical.target
"""

SYSTEMD_PLAYER_LITE_STANDALONE = """\
[Unit]
Description=TinySignage Player (Kiosk Browser — Lite)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User={user}

# cage creates its own Wayland session on this TTY
TTYPath=/dev/tty1
StandardInput=tty-force
StandardOutput=journal
StandardError=journal

RuntimeDirectory=tinysignage
Environment=XDG_RUNTIME_DIR=/run/tinysignage

ExecStartPre=/bin/sleep 5
ExecStart=/usr/bin/cage -d -s -- /usr/bin/python3 {install_dir}/launcher.py
WatchdogSec=120
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

# --- Systemd user service (desktop Linux) --------------------------------

SYSTEMD_USER = """\
[Unit]
Description=TinySignage Backend
After=network.target

[Service]
Type=simple
WorkingDirectory={install_dir}
ExecStart={install_dir}/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
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
        <string>{install_dir}/venv/bin/uvicorn</string>
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
call venv\\Scripts\\activate
uvicorn app.main:app --host 0.0.0.0 --port 8080
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


def run_as_user(user, cmd, cwd=None):
    """Run a command as a different user via runuser (Linux only)."""
    return run_cmd(["runuser", "-u", user, "--"] + list(cmd), cwd=cwd)


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
    if mode is None:
        print("  Please enter 1, 2, or 3.\n")
        return prompt_mode()
    return mode


def prompt_server_url():
    """Prompt for the CMS server URL (player-only mode)."""
    print("\nEnter the address of your CMS server.")
    print("This is the device where you installed the TinySignage CMS.\n")
    print("  Examples:  http://192.168.1.50:8080")
    print("             http://lobby-tv.local:8080\n")
    url = prompt_input("CMS server address")
    if not url:
        print("  A server address is required for player-only installs.")
        return prompt_server_url()
    url = url.rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url


def step(number, total, message):
    print(f"[{number}/{total}] {message}")


def info(message):
    print(f"  {message}")


def warn(message):
    print(f"  WARNING: {message}")


def error_exit(message):
    print(f"\nERROR: {message}", file=sys.stderr)
    sys.exit(1)


def find_python():
    """Find the best available Python 3 interpreter (full path)."""
    for name in ["python3.13", "python3.12", "python3.11", "python3"]:
        path = shutil.which(name)
        if path:
            return path
    if sys.platform == "win32":
        path = shutil.which("python")
        if path:
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

def pi_move_to_opt(source_dir):
    """Move install directory to /opt/tinysignage if not already there."""
    if os.path.realpath(source_dir) == os.path.realpath(TARGET_DIR):
        return TARGET_DIR
    print(f"Moving install from {source_dir} to {TARGET_DIR}...")
    if os.path.isdir(TARGET_DIR):
        info(f"{TARGET_DIR} already exists — removing old copy")
        shutil.rmtree(TARGET_DIR)
    shutil.move(source_dir, TARGET_DIR)
    info(f"Install directory is now {TARGET_DIR}")
    return TARGET_DIR


def pi_system_setup(install_dir, display_name, hostname, lite, mode="both"):
    """All Pi system-level steps (requires root)."""
    total = 6

    # --- [1] apt packages ---
    step(1, total, "Installing system packages...")
    packages = ["python3", "avahi-daemon", "curl"]
    if mode in ("both", "cms"):
        packages.extend(["python3-venv", "python3-pip", "ffmpeg"])
    if mode in ("both", "player"):
        packages.append("chromium")
        if mode == "player":
            packages.append("python3-yaml")  # launcher.py needs PyYAML
        if lite:
            info("Detected Pi OS Lite — will install kiosk compositor (cage)")
            packages.extend(["cage", "xwayland"])
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
    tv = {"install_dir": install_dir, "user": SERVICE_USER}
    services = []

    if mode in ("both", "cms"):
        with open("/etc/systemd/system/signage-app.service", "w") as f:
            f.write(SYSTEMD_APP.format(**tv))
        services.append("signage-app")

    if mode in ("both", "player"):
        if mode == "player":
            # Standalone player — uses system Python, no local backend
            template = SYSTEMD_PLAYER_LITE_STANDALONE if lite else SYSTEMD_PLAYER_STANDALONE
        else:
            template = SYSTEMD_PLAYER_LITE if lite else SYSTEMD_PLAYER
        if lite:
            info("Using Lite kiosk service (cage + Chromium)")
        with open("/etc/systemd/system/signage-player.service", "w") as f:
            f.write(template.format(**tv))
        services.append("signage-player")

    run_cmd(["systemctl", "daemon-reload"])
    if services:
        run_cmd(["systemctl", "enable"] + services)

    # --- [5] Transparent cursor theme ---
    step(5, total, "Installing transparent cursor theme...")
    if mode in ("both", "player"):
        install_cursor_theme()
    else:
        info("Skipped (no player on this device)")

    # Set cursor theme in labwc environment (Pi OS Desktop with Wayland)
    if mode in ("both", "player") and shutil.which("labwc"):
        try:
            import pwd
            pw = pwd.getpwnam(SERVICE_USER)
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
            run_cmd(["chown", "-R", f"{SERVICE_USER}:{SERVICE_USER}", labwc_dir])
            info("labwc cursor environment configured")
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
    """Create media/, db/, logs/ directories."""
    for d in ["media", "media/thumbs", "db", "logs"]:
        os.makedirs(os.path.join(install_dir, d), exist_ok=True)


def generate_config_env(install_dir):
    """Generate config.env with a random SECRET_KEY (if absent)."""
    path = os.path.join(install_dir, "config.env")
    if os.path.isfile(path):
        info("config.env already exists")
        return
    with open(path, "w") as f:
        f.write("# TinySignage environment config (auto-generated)\n")
        f.write(f"SECRET_KEY={secrets.token_hex(32)}\n")
    info("Generated config.env with SECRET_KEY")


def update_config_yaml(install_dir, display_name=None, server_url=None):
    """Update config.yaml fields using venv's PyYAML."""
    if not display_name and not server_url:
        return
    parts = [
        "import yaml; from pathlib import Path",
        f"p = Path({os.path.join(install_dir, 'config.yaml')!r})",
        "c = yaml.safe_load(p.read_text())",
    ]
    if server_url:
        parts.append(f"c['server_url'] = {server_url!r}")
    if display_name:
        parts.append(f"c['display_name'] = {display_name!r}")
    parts.append(
        "p.write_text(yaml.dump(c, default_flow_style=False, sort_keys=False))"
    )
    run_cmd([get_venv_python(install_dir), "-c", "; ".join(parts)], cwd=install_dir)
    if display_name:
        info(f"Set display_name to: {display_name}")
    if server_url:
        info(f"Set server_url to: {server_url}")


def init_database(install_dir):
    """Run Alembic migrations + seed data."""
    script = textwrap.dedent("""\
        import asyncio
        from app.database import init_db, engine
        async def setup():
            await init_db()
            await engine.dispose()
        asyncio.run(setup())
    """)
    run_cmd([get_venv_python(install_dir), "-c", script], cwd=install_dir)


# =========================================================================
# Dependency checks (desktop platforms)
# =========================================================================

def check_macos_deps():
    if not shutil.which("ffmpeg"):
        warn("FFmpeg not found. Video thumbnails won't be generated.")
        info("Fix: brew install ffmpeg")


def check_windows_deps():
    if not shutil.which("ffmpeg"):
        warn("FFmpeg not found. Video thumbnails won't be generated.")
        info("Fix: winget install Gyan.FFmpeg")


def check_linux_deps():
    missing = []
    if not shutil.which("chromium") and not shutil.which("chromium-browser"):
        missing.append("chromium")
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg")
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

def macos_post_install(install_dir, non_interactive):
    plist_dir = os.path.expanduser("~/Library/LaunchAgents")
    plist_path = os.path.join(plist_dir, "com.tinysignage.app.plist")

    if non_interactive or prompt_yn("Generate launchd plist to run on startup?"):
        os.makedirs(plist_dir, exist_ok=True)
        with open(plist_path, "w") as f:
            f.write(LAUNCHD_PLIST.format(install_dir=install_dir))
        info(f"Created {plist_path}")

        if not non_interactive and prompt_yn("Load it now (start TinySignage)?"):
            run_cmd(["launchctl", "load", plist_path])
            info("TinySignage started via launchd")
    else:
        info("Skipped launchd setup")


def windows_post_install(install_dir, non_interactive):
    bat_path = os.path.join(install_dir, "start-tinysignage.bat")

    if non_interactive or prompt_yn("Generate start-tinysignage.bat?"):
        with open(bat_path, "w") as f:
            f.write(WINDOWS_BAT.format(install_dir=install_dir))
        info(f"Created {bat_path}")

        if not non_interactive and prompt_yn(
            "Create shortcut in Startup folder (run on login)?"
        ):
            startup = os.path.join(
                os.environ.get("APPDATA", ""),
                r"Microsoft\Windows\Start Menu\Programs\Startup",
            )
            if os.path.isdir(startup):
                shortcut = os.path.join(startup, "tinysignage.bat")
                with open(shortcut, "w") as f:
                    f.write(f'@start "" /min cmd /c "{bat_path}"\n')
                info(f"Created startup shortcut: {shortcut}")
            else:
                warn(f"Startup folder not found: {startup}")
    else:
        info("Skipped bat file generation")


def linux_post_install(install_dir, non_interactive):
    service_dir = os.path.expanduser("~/.config/systemd/user")
    service_path = os.path.join(service_dir, "tinysignage.service")

    if non_interactive or prompt_yn("Generate systemd user service?"):
        os.makedirs(service_dir, exist_ok=True)
        with open(service_path, "w") as f:
            f.write(SYSTEMD_USER.format(install_dir=install_dir))
        info(f"Created {service_path}")
        info("To start: systemctl --user start tinysignage")
        info("To enable on login: systemctl --user enable tinysignage")
    else:
        info("Skipped systemd user service setup")
        info("To run manually:")
        info(f"  {get_venv_python(install_dir)} -m uvicorn app.main:app --host 0.0.0.0 --port 8080")


# =========================================================================
# Update mode
# =========================================================================

def do_update(plat, install_dir):
    """Update an existing installation: deps, migrations, restart."""
    print("=== TinySignage Update ===\n")

    venv_dir = os.path.join(install_dir, "venv")
    if not os.path.isdir(venv_dir):
        error_exit(
            f"No venv found at {venv_dir}.\n"
            "Run install.py without --update for a fresh install."
        )

    if plat == "pi":
        if os.geteuid() != 0:
            error_exit("Pi update requires root. Run: sudo python3 install.py --update")

        step(1, 3, "Updating Python dependencies...")
        pip = get_venv_pip(install_dir)
        run_as_user(SERVICE_USER, [
            pip, "install", "--quiet",
            "-r", os.path.join(install_dir, "requirements.txt"),
        ], cwd=install_dir)

        step(2, 3, "Running database migrations...")
        script = textwrap.dedent("""\
            import asyncio
            from app.database import init_db, engine
            async def setup():
                await init_db()
                await engine.dispose()
            asyncio.run(setup())
        """)
        run_as_user(SERVICE_USER, [
            get_venv_python(install_dir), "-c", script,
        ], cwd=install_dir)

        step(3, 3, "Restarting services...")
        run_cmd(["systemctl", "restart", "signage-app"])
        run_cmd(["systemctl", "restart", "signage-player"])
        info("Services restarted")

    else:
        step(1, 3, "Updating Python dependencies...")
        install_deps(install_dir)

        step(2, 3, "Running database migrations...")
        init_database(install_dir)

        step(3, 3, "Restarting services...")
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
            info("Restart the application manually")

    print("\nUpdate complete!")


# =========================================================================
# Main install flows
# =========================================================================

def install_pi(install_dir, display_name, non_interactive, mode="both", server_url=None):
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
    install_dir = pi_move_to_opt(install_dir)
    print()

    # ---- System setup (as root) ----
    pi_system_setup(install_dir, display_name, hostname, lite, mode)
    print()

    # ---- App setup ----
    if mode == "player":
        # Player-only: minimal setup, no backend needed
        print("=== Player Setup ===\n")
        total = 2

        step(1, total, "Creating directories...")
        run_as_user(SERVICE_USER, [
            "mkdir", "-p", os.path.join(install_dir, "data", "browser-profile"),
        ])

        step(2, total, "Configuring CMS server connection...")
        # Player-only uses system python3 (python3-yaml installed via apt)
        yaml_script = (
            "import yaml; from pathlib import Path; "
            f"p = Path({os.path.join(install_dir, 'config.yaml')!r}); "
            "c = yaml.safe_load(p.read_text()); "
            f"c['server_url'] = {server_url!r}; "
            f"c['display_name'] = {display_name!r}; "
            "p.write_text(yaml.dump(c, default_flow_style=False, sort_keys=False))"
        )
        run_as_user(SERVICE_USER, ["python3", "-c", yaml_script], cwd=install_dir)
        info(f"Server URL: {server_url}")
        info(f"Display name: {display_name}")

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
        for d in ["media", "media/thumbs", "db", "logs"]:
            run_as_user(SERVICE_USER, [
                "mkdir", "-p", os.path.join(install_dir, d),
            ])

        step(4, total, "Generating config.env...")
        config_env = os.path.join(install_dir, "config.env")
        if os.path.isfile(config_env):
            info("config.env already exists")
        else:
            secret_key = secrets.token_hex(32)
            with open(config_env, "w") as f:
                f.write("# TinySignage environment config (auto-generated)\n")
                f.write(f"SECRET_KEY={secret_key}\n")
            run_cmd(["chown", f"{SERVICE_USER}:{SERVICE_USER}", config_env])
            info("Generated config.env with SECRET_KEY")

        step(5, total, "Updating config.yaml...")
        local_url = server_url or "http://localhost:8080"
        yaml_script = (
            "import yaml; from pathlib import Path; "
            f"p = Path({os.path.join(install_dir, 'config.yaml')!r}); "
            "c = yaml.safe_load(p.read_text()); "
            f"c['server_url'] = {local_url!r}; "
            f"c['display_name'] = {display_name!r}; "
            "p.write_text(yaml.dump(c, default_flow_style=False, sort_keys=False))"
        )
        run_as_user(SERVICE_USER, [venv_python, "-c", yaml_script], cwd=install_dir)
        info(f"Set display_name={display_name}, server_url={local_url}")

        step(6, total, "Initializing database...")
        db_script = textwrap.dedent("""\
            import asyncio
            from app.database import init_db, engine
            async def setup():
                await init_db()
                await engine.dispose()
            asyncio.run(setup())
        """)
        run_as_user(SERVICE_USER, [venv_python, "-c", db_script], cwd=install_dir)

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
        print("  After reboot:")
        print(f"    CMS: http://{hostname}.local:8080/cms")
        print()
        print("  Point your player devices at this server during their install.")
    else:
        print("  Installation complete! Reboot to start:")
        print()
        print("    sudo reboot")
        print()
        print("  After reboot:")
        print(f"    CMS:    http://{hostname}.local:8080/cms")
        print("    Player: launches automatically on the display")
    print("=" * 50)


def install_desktop(plat, install_dir, non_interactive, mode="both", server_url=None):
    """Install for macOS, Windows, or desktop Linux."""
    names = {"macos": "macOS", "windows": "Windows", "linux": "Linux"}
    mode_suffix = {"both": "", "cms": " (CMS Only)", "player": " (Player Only)"}
    print(f"=== TinySignage {names[plat]} Installer{mode_suffix[mode]} ===\n")

    # Sanity check
    if not os.path.isfile(os.path.join(install_dir, "config.yaml")):
        error_exit(f"config.yaml not found in {install_dir} — is this the repo root?")

    if mode == "player":
        # Player-only: just save server_url and print instructions
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
     "linux": check_linux_deps}[plat]()
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

    print()

    # Platform-specific post-install
    {"macos": macos_post_install, "windows": windows_post_install,
     "linux": linux_post_install}[plat](install_dir, non_interactive)

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
            print(r"  Start: venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8080")
    else:
        print("  Start: source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8080")
    print()
    print(f"  Setup wizard: http://localhost:{DEFAULT_PORT}/setup  (first run)")
    print(f"  CMS:          http://localhost:{DEFAULT_PORT}/cms")
    if mode == "both":
        print(f"  Player:       http://localhost:{DEFAULT_PORT}/player")
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
              sudo python3 install.py --non-interactive --display-name "Lobby TV"   Scripted Pi
        """),
    )
    parser.add_argument(
        "--update", action="store_true",
        help="update existing install (pip deps + db migrations + restart)",
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
        "--non-interactive", action="store_true",
        help="skip all prompts, use defaults",
    )
    args = parser.parse_args()

    install_dir = os.path.dirname(os.path.abspath(__file__))
    plat = detect_platform()
    print(f"Detected platform: {plat}\n")

    if args.update:
        do_update(plat, install_dir)
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

    print()

    if plat == "pi":
        install_pi(install_dir, args.display_name, args.non_interactive, mode, server_url)
    else:
        install_desktop(plat, install_dir, args.non_interactive, mode, server_url)


if __name__ == "__main__":
    main()
