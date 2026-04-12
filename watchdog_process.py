#!/usr/bin/env python3
"""TinySignage independent process watchdog.

Monitors the CMS backend and browser player as an external process.
Zero imports from app/ — uses only stdlib + pyyaml.

Usage:
    python watchdog_process.py              # Run with config.yaml defaults
    python watchdog_process.py --once       # Single check cycle, then exit
"""

import argparse
import logging
import logging.handlers
import os
import platform
import signal
import ssl
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # Degrade gracefully — use defaults

SCRIPT_DIR = Path(__file__).resolve().parent

# =========================================================================
# Defaults (used when config.yaml is missing or has no watchdog section)
# =========================================================================

DEFAULTS = {
    "enabled": True,
    "check_interval": 30,
    "startup_grace": 60,
    "mode": "auto",
    "cms_fail_threshold": 3,
    "browser_memory_limit_mb": 1024,
    "browser_fail_threshold": 2,
    "log_file": "./logs/watchdog.log",
}

# Browser process names to scan for, per engine type
BROWSER_NAMES_LINUX = ("cog", "chromium", "chromium-browser", "chrome", "google-chrome")
BROWSER_NAMES_MACOS = ("Google Chrome", "Chromium", "cog")
BROWSER_NAMES_WINDOWS = ("chrome.exe", "chromium.exe")

# =========================================================================
# Logging setup
# =========================================================================

log = logging.getLogger("tinysignage.watchdog")


def setup_logging(log_file: str, level: str = "INFO"):
    """Configure rotating file + stderr logging."""
    log.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler (5 MB x 3 backups)
    log_path = Path(log_file)
    if not log_path.is_absolute():
        log_path = SCRIPT_DIR / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(
        str(log_path), maxBytes=5 * 1024 * 1024, backupCount=3,
    )
    fh.setFormatter(fmt)
    log.addHandler(fh)

    # Stderr for systemd journal / console visibility
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    log.addHandler(sh)


# =========================================================================
# Config loading
# =========================================================================

def load_config() -> dict:
    """Load watchdog config from config.yaml, falling back to defaults."""
    cfg = dict(DEFAULTS)
    config_path = SCRIPT_DIR / "config.yaml"
    if yaml and config_path.exists():
        try:
            full = yaml.safe_load(config_path.read_text())
            if full and isinstance(full, dict):
                wd = full.get("watchdog", {})
                if isinstance(wd, dict):
                    for k, v in wd.items():
                        if k in cfg:
                            cfg[k] = v
                # Also grab server port/https for health check URL
                server = full.get("server", {}) or {}
                cfg["_port"] = server.get("port", 8080)
                cfg["_https"] = bool(
                    (server.get("https") or {}).get("enabled", False)
                )
        except Exception as e:
            log.warning("Could not read config.yaml: %s — using defaults", e)
    return cfg


# =========================================================================
# Platform detection
# =========================================================================

def detect_platform() -> str:
    """Return 'docker', 'pi', 'linux', 'macos', or 'windows'."""
    # Docker detection — exit early
    if (os.environ.get("container") == "docker"
            or Path("/.dockerenv").exists()):
        return "docker"

    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    if system == "linux":
        for path in ("/proc/device-tree/model", "/proc/cpuinfo"):
            try:
                content = Path(path).read_text().lower()
                if "raspberry pi" in content or "bcm" in content:
                    return "pi"
            except (OSError, PermissionError):
                pass
        return "linux"
    return "linux"  # fallback


def detect_mode(cfg: dict, plat: str) -> str:
    """Determine what to monitor: 'cms', 'player', or 'both'.

    In 'auto' mode, inspects what services/files exist on this machine.
    """
    mode = cfg.get("mode", "auto")
    if mode in ("cms", "player", "both"):
        return mode

    # Auto-detect based on platform artifacts
    has_cms = False
    has_player = False

    if plat == "pi":
        has_cms = Path("/etc/systemd/system/signage-app.service").exists()
        has_player = (
            Path("/etc/systemd/system/signage-player.service").exists()
            or _has_pi_desktop_player()
        )
    elif plat == "linux":
        has_cms = Path("~/.config/systemd/user/tinysignage.service").expanduser().exists()
        # Desktop Linux doesn't manage a player process
    elif plat == "macos":
        has_cms = Path("~/Library/LaunchAgents/com.tinysignage.app.plist").expanduser().exists()
    elif plat == "windows":
        has_cms = (SCRIPT_DIR / "start-tinysignage.bat").exists()
        # On Windows, check if launcher.py exists for player
        has_player = (SCRIPT_DIR / "launcher.py").exists()

    if has_cms and has_player:
        return "both"
    if has_player:
        return "player"
    # Default to CMS if we can't tell — it's the most common case
    return "cms"


def _has_pi_desktop_player() -> bool:
    """Check if the Pi Desktop XDG autostart player entry exists."""
    try:
        import pwd
        for pw in pwd.getpwall():
            if 1000 <= pw.pw_uid < 65000:
                autostart = Path(pw.pw_dir) / ".config/autostart/signage-player.desktop"
                if autostart.exists():
                    return True
    except (ImportError, OSError):
        pass
    return False


# =========================================================================
# CMS health check
# =========================================================================

def _insecure_ssl_context() -> ssl.SSLContext:
    """SSL context that accepts self-signed certs (local health checks only)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def check_cms_health(port: int, use_https: bool) -> bool:
    """HTTP GET /health with 5s timeout. Returns True if healthy."""
    scheme = "https" if use_https else "http"
    url = f"{scheme}://127.0.0.1:{port}/health"
    ctx = _insecure_ssl_context() if use_https else None
    try:
        req = urllib.request.Request(url, method="GET")
        kwargs = {"timeout": 5}
        if ctx is not None:
            kwargs["context"] = ctx
        with urllib.request.urlopen(req, **kwargs) as resp:
            return resp.status == 200
    except Exception:
        return False


# =========================================================================
# Process discovery (cross-platform, no psutil)
# =========================================================================

def find_cms_pid() -> int | None:
    """Find the PID of the CMS (uvicorn/python) process."""
    system = platform.system()
    if system == "Linux":
        return _find_pid_linux("uvicorn", fallback_comm="python")
    elif system == "Darwin":
        return _find_pid_macos("uvicorn")
    elif system == "Windows":
        return _find_pid_windows("python.exe")
    return None


def find_browser_pid() -> int | None:
    """Find the PID of the browser process."""
    system = platform.system()
    if system == "Linux":
        return _find_browser_pid_linux()
    elif system == "Darwin":
        return _find_browser_pid_macos()
    elif system == "Windows":
        return _find_browser_pid_windows()
    return None


def _find_pid_linux(cmdline_match: str, fallback_comm: str | None = None) -> int | None:
    """Scan /proc for a process whose cmdline contains the match string."""
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            if pid == os.getpid():
                continue
            try:
                cmdline = (entry / "cmdline").read_text().replace("\0", " ")
                if cmdline_match in cmdline and "app.server" in cmdline:
                    return pid
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return None


def _find_browser_pid_linux() -> int | None:
    """Scan /proc/*/comm for known browser process names."""
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                comm = (entry / "comm").read_text().strip()
                if comm in BROWSER_NAMES_LINUX:
                    return int(entry.name)
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return None


def _find_pid_macos(match: str) -> int | None:
    """Use ps to find a process matching a string."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", match],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                pid = int(line.strip())
                if pid != os.getpid():
                    return pid
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass
    return None


def _find_browser_pid_macos() -> int | None:
    """Use pgrep to find Chrome/Chromium/cog on macOS."""
    for name in BROWSER_NAMES_MACOS:
        try:
            result = subprocess.run(
                ["pgrep", "-f", name],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    pid = int(line.strip())
                    if pid != os.getpid():
                        return pid
        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
            continue
    return None


def _find_pid_windows(image_name: str) -> int | None:
    """Use tasklist to find a process by image name, then filter by cmdline."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line or "No tasks" in line or "INFO:" in line:
                    continue
                parts = line.split('","')
                if len(parts) >= 2:
                    pid_str = parts[1].strip('"')
                    try:
                        return int(pid_str)
                    except ValueError:
                        continue
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _find_browser_pid_windows() -> int | None:
    """Find browser process on Windows via tasklist."""
    for name in BROWSER_NAMES_WINDOWS:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if not line or "No tasks" in line or "INFO:" in line:
                        continue
                    parts = line.split('","')
                    if len(parts) >= 2:
                        pid_str = parts[1].strip('"')
                        try:
                            return int(pid_str)
                        except ValueError:
                            continue
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return None


# =========================================================================
# Memory reading (cross-platform, no psutil)
# =========================================================================

def read_rss_mb(pid: int) -> int | None:
    """Read RSS in MB for a process. Returns None if unable to read."""
    system = platform.system()
    if system == "Linux":
        return _read_rss_linux(pid)
    elif system == "Darwin":
        return _read_rss_macos(pid)
    elif system == "Windows":
        return _read_rss_windows(pid)
    return None


def _read_rss_linux(pid: int) -> int | None:
    """Read RSS from /proc/<pid>/statm (field 1 = resident pages)."""
    try:
        fields = Path(f"/proc/{pid}/statm").read_text().split()
        resident_pages = int(fields[1])
        return (resident_pages * 4096) // (1024 * 1024)
    except (OSError, IndexError, ValueError):
        return None


def _read_rss_macos(pid: int) -> int | None:
    """Read RSS via ps -o rss= (output in KB)."""
    try:
        result = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            kb = int(result.stdout.strip())
            return kb // 1024
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass
    return None


def _read_rss_windows(pid: int) -> int | None:
    """Read RSS via tasklist /FI (parse CSV, 'Mem Usage' column in KB)."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line or "No tasks" in line or "INFO:" in line:
                    continue
                # CSV: "name","pid","session","session#","mem"
                parts = line.split('","')
                if len(parts) >= 5:
                    mem_str = parts[4].strip('"').replace(",", "").replace(" K", "")
                    try:
                        kb = int(mem_str)
                        return kb // 1024
                    except ValueError:
                        pass
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


# =========================================================================
# Restart commands (platform-dispatched)
# =========================================================================

def restart_cms(plat: str):
    """Restart the CMS process. OS supervisor handles re-launch."""
    log.warning("Restarting CMS...")

    if plat == "windows":
        _restart_cms_windows()
    else:
        # Linux/macOS/Pi: SIGTERM the process, let systemd/launchd re-launch
        pid = find_cms_pid()
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                log.info("Sent SIGTERM to CMS (PID %d)", pid)
            except OSError as e:
                log.error("Failed to kill CMS PID %d: %s", pid, e)
        else:
            log.warning("CMS PID not found — cannot restart")


def restart_browser(plat: str):
    """Restart the browser process. OS supervisor / shell loop handles re-launch."""
    log.warning("Restarting browser...")

    if plat == "windows":
        _restart_browser_windows()
    else:
        # Linux/macOS/Pi: SIGTERM the process
        pid = find_browser_pid()
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                log.info("Sent SIGTERM to browser (PID %d)", pid)
            except OSError as e:
                log.error("Failed to kill browser PID %d: %s", pid, e)
        else:
            log.warning("Browser PID not found — cannot restart")


def _restart_cms_windows():
    """Kill uvicorn/python and re-launch via batch file."""
    # Kill existing python processes running app.server
    try:
        # Use WMIC to find python processes with app.server in command line
        result = subprocess.run(
            ["wmic", "process", "where",
             "Name='python.exe' and CommandLine like '%app.server%'",
             "get", "ProcessId", "/format:csv"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                parts = line.strip().split(",")
                if len(parts) >= 2:
                    try:
                        pid = int(parts[-1])
                        subprocess.run(
                            ["taskkill", "/PID", str(pid), "/F"],
                            capture_output=True, timeout=10,
                        )
                        log.info("Killed CMS process PID %d", pid)
                    except (ValueError, subprocess.TimeoutExpired):
                        continue
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Re-launch via batch file
    bat = SCRIPT_DIR / "start-tinysignage.bat"
    if bat.exists():
        try:
            subprocess.Popen(
                ["cmd", "/c", str(bat)],
                cwd=str(SCRIPT_DIR),
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            log.info("Re-launched CMS via %s", bat)
        except OSError as e:
            log.error("Failed to re-launch CMS: %s", e)
    else:
        log.warning("start-tinysignage.bat not found — cannot re-launch CMS")


def _restart_browser_windows():
    """Kill Chrome and re-launch via launcher.py."""
    for name in BROWSER_NAMES_WINDOWS:
        try:
            subprocess.run(
                ["taskkill", "/IM", name, "/F"],
                capture_output=True, timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    launcher = SCRIPT_DIR / "launcher.py"
    if launcher.exists():
        python = sys.executable or "python"
        try:
            subprocess.Popen(
                [python, str(launcher)],
                cwd=str(SCRIPT_DIR),
                creationflags=subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            log.info("Re-launched browser via launcher.py")
        except OSError as e:
            log.error("Failed to re-launch browser: %s", e)
    else:
        log.warning("launcher.py not found — cannot re-launch browser")


# =========================================================================
# Process existence check
# =========================================================================

def pid_exists(pid: int) -> bool:
    """Check if a process with the given PID exists."""
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0 and str(pid) in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    else:
        try:
            os.kill(pid, 0)  # Signal 0 = existence check
            return True
        except OSError:
            return False


# =========================================================================
# Main watchdog loop
# =========================================================================

def watchdog_loop(cfg: dict, plat: str, mode: str, *, once: bool = False):
    """Core monitoring loop."""
    interval = cfg.get("check_interval", 30)
    grace = cfg.get("startup_grace", 60)
    cms_threshold = cfg.get("cms_fail_threshold", 3)
    browser_threshold = cfg.get("browser_fail_threshold", 2)
    mem_limit = cfg.get("browser_memory_limit_mb", 400)
    port = cfg.get("_port", 8080)
    use_https = cfg.get("_https", False)

    cms_fails = 0
    browser_fails = 0
    start_time = time.monotonic()
    last_browser_pid = None

    log.info(
        "Watchdog started: platform=%s, mode=%s, interval=%ds, grace=%ds",
        plat, mode, interval, grace,
    )

    while True:
        try:
            elapsed = time.monotonic() - start_time
            monitor_cms = mode in ("cms", "both")
            monitor_browser = mode in ("player", "both")

            # --- CMS health check ---
            if monitor_cms:
                if elapsed < grace:
                    log.debug("Startup grace period — skipping CMS check (%.0fs remaining)",
                              grace - elapsed)
                else:
                    healthy = check_cms_health(port, use_https)
                    if healthy:
                        if cms_fails > 0:
                            log.info("CMS recovered after %d failure(s)", cms_fails)
                        cms_fails = 0
                    else:
                        cms_fails += 1
                        log.warning("CMS health check failed (%d/%d)",
                                    cms_fails, cms_threshold)
                        if cms_fails >= cms_threshold:
                            restart_cms(plat)
                            cms_fails = 0
                            if not once:
                                log.info("Cooldown 15s after CMS restart")
                                time.sleep(15)
                                continue

            # --- Browser process check ---
            if monitor_browser:
                browser_pid = find_browser_pid()
                if browser_pid:
                    browser_fails = 0
                    last_browser_pid = browser_pid

                    # Memory check
                    if mem_limit > 0:
                        rss = read_rss_mb(browser_pid)
                        if rss is not None:
                            log.debug("Browser PID %d RSS: %d MB (limit: %d MB)",
                                      browser_pid, rss, mem_limit)
                            if rss > mem_limit:
                                log.warning(
                                    "Browser RSS %d MB exceeds limit %d MB — restarting",
                                    rss, mem_limit,
                                )
                                restart_browser(plat)
                                last_browser_pid = None
                                if not once:
                                    log.info("Cooldown 30s after browser restart")
                                    time.sleep(30)
                                    continue
                else:
                    # Browser not found — but only count as failure after grace
                    if elapsed > grace:
                        browser_fails += 1
                        log.warning("Browser process not found (%d/%d)",
                                    browser_fails, browser_threshold)
                        if browser_fails >= browser_threshold:
                            restart_browser(plat)
                            browser_fails = 0
                            last_browser_pid = None
                            if not once:
                                log.info("Cooldown 30s after browser restart")
                                time.sleep(30)
                                continue

            if once:
                log.info("Single check complete — exiting")
                break

            time.sleep(interval)

        except KeyboardInterrupt:
            log.info("Watchdog interrupted — shutting down")
            break
        except Exception:
            log.exception("Unexpected error in watchdog loop")
            if once:
                break
            time.sleep(interval)


# =========================================================================
# Entry point
# =========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="TinySignage independent process watchdog",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run a single check cycle and exit",
    )
    args = parser.parse_args()

    # Load config
    cfg = load_config()

    # Check master switch
    if not cfg.get("enabled", True):
        print("Watchdog disabled in config.yaml (watchdog.enabled: false)")
        sys.exit(0)

    # Platform detection
    plat = detect_platform()

    # Docker: exit immediately
    if plat == "docker":
        print("Docker detected — watchdog not needed (use Docker healthcheck + restart policy)")
        sys.exit(0)

    # Setup logging
    setup_logging(cfg.get("log_file", "./logs/watchdog.log"))

    # Detect mode
    mode = detect_mode(cfg, plat)
    log.info("Platform: %s, Mode: %s", plat, mode)

    # Run
    watchdog_loop(cfg, plat, mode, once=args.once)


if __name__ == "__main__":
    main()
