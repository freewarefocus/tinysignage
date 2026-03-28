"""Cross-platform kiosk browser launcher for TinySignage."""
import subprocess
import platform
import shutil
from pathlib import Path
import yaml


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
            "--disable-gpu-compositing",
            "--enable-features=VaapiVideoDecoder",
            "--gpu-memory-buffer-video-frames",
            "--disable-background-timer-throttling",
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
    args.append(url)

    print(f"Launching: {' '.join(args)}")
    subprocess.Popen(args)


if __name__ == "__main__":
    launch()
