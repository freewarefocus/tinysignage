"""Cross-platform kiosk browser launcher for TinySignage."""
import argparse
import os
import subprocess
import platform
import shutil
import sys
from pathlib import Path
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
BROWSER_PROFILE_DIR = SCRIPT_DIR / "data" / "browser-profile"


def find_browser() -> str | None:
    """Find an installed Chromium-based browser."""
    candidates = {
        "linux": ["chromium-browser", "chromium", "google-chrome", "google-chrome-stable"],
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
        flags.extend([
            "--ozone-platform=wayland",
            "--disable-background-timer-throttling",
            "--disk-cache-dir=/dev/null",
        ])

    return flags


def launch(config_path: str = "config.yaml"):
    config = yaml.safe_load(Path(config_path).read_text())
    host = config["server"]["host"]
    port = config["server"]["port"]
    browser_config = config.get("player", {}).get("browser", "auto")
    kiosk = config.get("player", {}).get("kiosk", True)

    if browser_config != "auto":
        browser = browser_config
    else:
        browser = find_browser()

    if not browser:
        print("ERROR: No Chromium-based browser found.")
        return

    url = f"http://localhost:{port}/player"
    is_pi = Path("/proc/device-tree/model").exists()  # Rough Pi detection

    args = [browser]
    if kiosk:
        args.extend(get_kiosk_flags(is_pi))
    args.append(f"--user-data-dir={BROWSER_PROFILE_DIR}")
    args.append(url)

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
