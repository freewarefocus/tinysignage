"""Cross-platform kiosk browser launcher for TinySignage."""
import argparse
import os
import subprocess
import platform
import shutil
import sys
import time
import urllib.request
from pathlib import Path
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
BROWSER_PROFILE_DIR = SCRIPT_DIR / "data" / "browser-profile"
# Real, writable tmpfs path for Chromium's disk cache on Pi.
# /tmp is tmpfs on Pi OS, so this still avoids SD-card wear, but unlike
# /dev/null it is an actual directory Chromium can mkdir into.
PI_DISK_CACHE_DIR = "/tmp/tinysignage-cache"


def find_browser() -> str | None:
    """Find an installed Chromium-based browser."""
    candidates = {
        # On Trixie only /usr/bin/chromium exists; put the canonical
        # Debian name first so shutil.which hits on the first try.
        "linux": ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable"],
        "darwin": [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ],
        "win32": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
    }

    system = platform.system().lower()
    if system == "windows":
        system = "win32"

    for candidate in candidates.get(system, []):
        if Path(candidate).exists() or shutil.which(candidate):
            return candidate
    return None


def get_kiosk_flags(is_pi: bool = False) -> list[str]:
    """Get Chromium flags for kiosk mode."""
    flags = [
        "--kiosk",
        "--noerrdialogs",
        "--disable-infobars",
        "--no-first-run",
        "--disable-translate",
        "--disable-features=TranslateUI",
        "--autoplay-policy=no-user-gesture-required",
    ]

    if is_pi:
        # Pick the ozone backend from the actual session type.
        # Hard-coding wayland breaks Pi OS Desktop X11 sessions; missing it
        # entirely makes Chromium guess (often wrong on labwc/wayfire).
        session = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if session == "wayland":
            flags.append("--ozone-platform=wayland")
        elif session == "x11":
            flags.append("--ozone-platform=x11")
        # else: leave it to Chromium's auto-detection

        flags.extend([
            "--disable-background-timer-throttling",
            # Real tmpfs path — /dev/null is a char device and Chromium's
            # mkdir of /dev/null/Default/Code Cache/* fails noisily and on
            # cold boots can delay/suppress the kiosk window.
            f"--disk-cache-dir={PI_DISK_CACHE_DIR}",
            "--disk-cache-size=1",
            # Clear inherited --js-flags from Pi OS's chromium.conf
            # (which injects --js-flags=--no-decommit-pooled-pages, an
            # unrecognized flag that spams stderr and hides real errors).
            "--js-flags=",
        ])

    return flags


def _ensure_pi_cache_dir() -> None:
    """Make sure the Chromium disk cache dir exists and is writable.

    /tmp is tmpfs on Pi OS so this directory disappears on every reboot;
    create it on each launch rather than relying on install.py.
    """
    try:
        os.makedirs(PI_DISK_CACHE_DIR, exist_ok=True)
    except OSError as e:
        print(f"WARN: could not create {PI_DISK_CACHE_DIR}: {e}")


def _wait_for_url(url: str, timeout: int = 60) -> None:
    """Block until `url` responds, or `timeout` seconds elapse.

    On cold boot signage-app.service may not be listening on :8080 yet
    when the desktop autostart fires. Without this poll Chromium hits
    its connection-error page and (depending on cache state) may fail
    to recover before the wrapper's restart loop tears it down.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except Exception:
            time.sleep(1)
    print(f"WARN: {url} did not become ready within {timeout}s; launching anyway")


def launch(config_path: str | None = None):
    # Resolve config.yaml relative to this script so the launcher works
    # regardless of the caller's cwd. XDG autostart fires with cwd=$HOME,
    # which used to crash the launcher with FileNotFoundError: 'config.yaml'.
    cfg = Path(config_path) if config_path else SCRIPT_DIR / "config.yaml"
    config = yaml.safe_load(cfg.read_text())
    browser_config = config.get("player", {}).get("browser", "auto")
    kiosk = config.get("player", {}).get("kiosk", True)

    if browser_config != "auto":
        browser = browser_config
    else:
        browser = find_browser()

    if not browser:
        print("ERROR: No Chromium-based browser found.")
        return

    # Use server_url if set, otherwise fall back to localhost
    port = config.get("server", {}).get("port", 8080)
    server_url = config.get("server_url", "").rstrip("/")
    if not server_url:
        server_url = f"http://localhost:{port}"
    url = f"{server_url}/player"
    is_pi = Path("/proc/device-tree/model").exists()  # Rough Pi detection

    if is_pi:
        _ensure_pi_cache_dir()

    args = [browser]
    if kiosk:
        args.extend(get_kiosk_flags(is_pi))
    args.append(f"--user-data-dir={BROWSER_PROFILE_DIR}")
    args.append(url)

    # Wait for the backend to be reachable before launching the kiosk.
    # Avoids the cold-boot race where chromium loads its connection-error
    # page because signage-app.service hasn't bound :8080 yet.
    print(f"Waiting for {url} to become ready...")
    _wait_for_url(url)

    print(f"Launching: {' '.join(args)}")

    if platform.system() == "Linux":
        # Replace this process with the browser — lets systemd (and cage)
        # track the browser directly for restart/lifecycle management
        os.execvp(args[0], args)
    else:
        subprocess.Popen(args)


def reset_browser_profile():
    """Delete the browser profile to force re-registration."""
    if BROWSER_PROFILE_DIR.exists():
        try:
            shutil.rmtree(BROWSER_PROFILE_DIR)
        except PermissionError:
            print(f"ERROR: Could not delete {BROWSER_PROFILE_DIR}")
            print("Close the browser first, then try again.")
            sys.exit(1)
        print(f"Player registration cleared: {BROWSER_PROFILE_DIR}")
        print("The player will show the registration screen on next launch.")
    else:
        print("No browser profile found. Nothing to reset.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TinySignage kiosk browser launcher")
    parser.add_argument("--reset", action="store_true",
                        help="Delete browser profile and exit (forces re-registration)")
    args = parser.parse_args()
    if args.reset:
        reset_browser_profile()
    else:
        launch()
