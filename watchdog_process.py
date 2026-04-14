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
    "memory_log_enabled": False,
    "memory_log_interval": 1800,
    # Scheduled weekly full system reboot (Linux/Pi only).
    # Every mature signage project recommends this as a safety net against
    # slow memory accumulation that per-process restarts can't catch.
    "scheduled_reboot_day": None,    # 0=Mon .. 6=Sun, None=disabled
    "scheduled_reboot_hour": 3,      # Hour (0-23) to reboot on the scheduled day
}

# Browser process names to scan for, per engine type
BROWSER_NAMES_LINUX = ("chromium", "chromium-browser", "chromium-browse", "chrome", "google-chrome")
BROWSER_NAMES_MACOS = ("Google Chrome", "Chromium")
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
            or (SCRIPT_DIR / "scripts" / "run-player.sh").exists()
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
        return _find_pid_linux("uvicorn")
    elif system == "Darwin":
        return _find_pid_macos("uvicorn")
    elif system == "Windows":
        return _find_pid_windows("python.exe", cmdline_filter="app.server")
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


def _find_pid_linux(cmdline_match: str) -> int | None:
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


def _find_all_browser_pids_linux() -> list[int]:
    """Return ALL PIDs matching known browser comm names. Linux only."""
    pids = []
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                comm = (entry / "comm").read_text().strip()
                if comm in BROWSER_NAMES_LINUX:
                    pids.append(int(entry.name))
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return pids



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
    """Use pgrep to find Chrome/Chromium on macOS."""
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


def _find_pid_windows(image_name: str, cmdline_filter: str | None = None) -> int | None:
    """Use tasklist to find a process by image name, optionally filtering by cmdline via PowerShell."""
    if cmdline_filter:
        # Use PowerShell Get-CimInstance for command-line filtering
        try:
            ps_cmd = (
                f"Get-CimInstance Win32_Process -Filter "
                f"\"Name='{image_name}' AND CommandLine LIKE '%{cmdline_filter}%'\" "
                f"| Select-Object -First 1 -ExpandProperty ProcessId"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                try:
                    return int(result.stdout.strip())
                except ValueError:
                    pass
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    # Simple tasklist lookup (no cmdline filter)
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
    """Read RSS from /proc — prefers smaps_rollup (more accurate), falls back to statm."""
    # smaps_rollup includes shared/private pages and is more accurate than
    # statm (which misses DRM/GBM buffers and GPU-mapped memory).
    try:
        text = Path(f"/proc/{pid}/smaps_rollup").read_text()
        for line in text.splitlines():
            if line.startswith("Rss:"):
                kb = int(line.split()[1])
                return kb // 1024
    except (OSError, IndexError, ValueError):
        pass
    # Fallback to statm
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
    """Read RSS via tasklist /FI (parse CSV, 'Mem Usage' column in KB).

    The memory column format varies by locale (e.g. "123,456 K", "123.456 Ko").
    We strip all non-digit characters to handle any locale.
    """
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
                    # Strip everything except digits to handle any locale
                    digits = "".join(c for c in parts[4] if c.isdigit())
                    if digits:
                        try:
                            kb = int(digits)
                            return kb // 1024
                        except ValueError:
                            pass
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _read_total_browser_rss_linux(browser_pid: int) -> tuple[int, int]:
    """Read RSS of the browser process tree.

    Returns (total_rss_mb, process_count).
    """
    all_pids = _find_all_browser_pids_linux()
    if browser_pid not in all_pids:
        all_pids.append(browser_pid)
    total = 0
    count = 0
    for pid in all_pids:
        rss = read_rss_mb(pid)
        if rss is not None:
            total += rss
            count += 1
    return total, count


# =========================================================================
# Memory snapshot (periodic diagnostics)
# =========================================================================

def _find_pids_by_comm_linux(comm_name: str) -> list[int]:
    """Scan /proc/*/comm for all PIDs matching *comm_name*. Linux only."""
    pids = []
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                comm = (entry / "comm").read_text().strip()
                if comm == comm_name:
                    pids.append(int(entry.name))
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return pids


def _find_pids_by_cmdline_linux(match: str) -> list[int]:
    """Scan /proc/*/cmdline for all PIDs whose cmdline contains *match*. Linux only."""
    pids = []
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            if pid == os.getpid():
                continue
            try:
                cmdline = (entry / "cmdline").read_text().replace("\0", " ")
                if match in cmdline:
                    pids.append(pid)
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return pids


def read_system_memory() -> dict | None:
    """Parse /proc/meminfo for total and available memory. Linux only.

    Returns {"total_mb": int, "available_mb": int, "used_pct": float} or None.
    """
    if platform.system() != "Linux":
        return None
    try:
        text = Path("/proc/meminfo").read_text()
        info = {}
        for line in text.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].rstrip(":")
                if key in ("MemTotal", "MemAvailable"):
                    info[key] = int(parts[1])  # value in kB
        if "MemTotal" in info and "MemAvailable" in info:
            total_mb = info["MemTotal"] // 1024
            avail_mb = info["MemAvailable"] // 1024
            used_pct = ((total_mb - avail_mb) / total_mb * 100) if total_mb else 0.0
            return {"total_mb": total_mb, "available_mb": avail_mb, "used_pct": used_pct}
    except (OSError, ValueError):
        pass
    return None


def collect_memory_snapshot(plat: str, mode: str) -> list[tuple[str, int | None, int | None]]:
    """Gather (label, pid, rss_mb) tuples for TinySignage-related processes."""
    entries: list[tuple[str, int | None, int | None]] = []

    # CMS (uvicorn)
    cms_pid = find_cms_pid()
    entries.append(("CMS (uvicorn)", cms_pid, read_rss_mb(cms_pid) if cms_pid else None))

    # Browser (chromium)
    browser_pid = find_browser_pid()
    entries.append(("Browser", browser_pid, read_rss_mb(browser_pid) if browser_pid else None))

    # Linux/Pi-only children
    if platform.system() == "Linux":
        # GPIO bridge — optional, omitted if not running
        bridge_pids = _find_pids_by_cmdline_linux("bridge.py")
        for pid in bridge_pids:
            entries.append(("GPIO bridge", pid, read_rss_mb(pid)))

    # Watchdog self
    self_pid = os.getpid()
    entries.append(("Watchdog (self)", self_pid, read_rss_mb(self_pid)))

    return entries


def log_memory_snapshot(plat: str, mode: str):
    """Format and log a memory snapshot as a single log.info() call."""
    entries = collect_memory_snapshot(plat, mode)
    sys_mem = read_system_memory()

    lines = ["--- Memory Snapshot ---"]

    if sys_mem:
        lines.append(
            "  System: %.1f%% used (%d / %d MB)"
            % (sys_mem["used_pct"], sys_mem["total_mb"] - sys_mem["available_mb"], sys_mem["total_mb"])
        )

    total_rss = 0
    for label, pid, rss in entries:
        if pid is None:
            lines.append("  %-24s  not running" % label)
        elif rss is None:
            lines.append("  %-24s  PID %-8d  RSS: ?" % (label, pid))
        else:
            lines.append("  %-24s  PID %-8d  RSS: %d MB" % (label, pid, rss))
            total_rss += rss

    lines.append("  %-24s                RSS: %d MB" % ("Total", total_rss))
    lines.append("--- End Snapshot ---")

    log.info("\n".join(lines))


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


def _kill_pids_with_fallback(pids: list[int], label: str, timeout: int = 5):
    """SIGTERM all PIDs, wait up to *timeout* seconds, SIGKILL survivors."""
    if not pids:
        return
    # Send SIGTERM to all
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    log.info("Sent SIGTERM to %d %s process(es): %s", len(pids), label, pids)

    # Wait for them to exit
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        survivors = [p for p in pids if pid_exists(p)]
        if not survivors:
            return
        time.sleep(0.5)

    # SIGKILL any still alive
    survivors = [p for p in pids if pid_exists(p)]
    for pid in survivors:
        try:
            os.kill(pid, signal.SIGKILL)
            log.warning("Sent SIGKILL to %s PID %d (did not exit after SIGTERM)", label, pid)
        except OSError:
            pass


def _restart_browser_via_systemd() -> bool:
    """Try to restart the browser via systemctl. Returns True on success."""
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "restart", "signage-player.service"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            log.info("Restarted browser via systemctl (cgroup cleanup)")
            return True
        log.debug("systemctl restart failed (rc=%d): %s",
                  result.returncode, result.stderr.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.debug("systemctl restart unavailable: %s", e)
    return False


def restart_browser(plat: str):
    """Restart the browser process. OS supervisor / shell loop handles re-launch."""
    log.warning("Restarting browser...")

    if plat == "windows":
        _restart_browser_windows()
        return

    # Linux/macOS/Pi: try systemd first (cgroup kill is atomic & complete)
    if plat in ("pi", "linux") and _restart_browser_via_systemd():
        # systemd's KillMode=control-group already killed all children
        return

    # Fallback: manual kill of ALL browser processes
    if platform.system() == "Linux":
        browser_pids = _find_all_browser_pids_linux()
        if browser_pids:
            log.info("Manual kill: %d browser processes", len(browser_pids))
            _kill_pids_with_fallback(browser_pids, "browser")
        else:
            log.warning("No browser processes found — cannot restart")
    else:
        # macOS fallback — single PID kill (unchanged behavior)
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
    # Kill existing python processes running app.server via PowerShell
    try:
        ps_cmd = (
            "Get-CimInstance Win32_Process -Filter "
            "\"Name='python.exe' AND CommandLine LIKE '%app.server%'\" "
            "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            log.info("Killed CMS python processes via PowerShell")
        elif result.stderr.strip():
            log.warning("PowerShell CMS kill output: %s", result.stderr.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log.warning("PowerShell not available for CMS kill: %s — trying taskkill fallback", e)
        # Fallback: use taskkill by image name (less precise)
        try:
            subprocess.run(
                ["taskkill", "/IM", "python.exe", "/F"],
                capture_output=True, timeout=10,
            )
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
    """Kill the signage Chrome instance and re-launch via launcher.py.

    Targets only Chrome processes whose command line contains 'browser-profile'
    (the custom --user-data-dir used by launcher.py), so the user's normal
    Chrome windows are left untouched.
    """
    killed = False
    # Try PowerShell first — can filter by command line to target only signage Chrome
    try:
        ps_cmd = (
            "Get-CimInstance Win32_Process -Filter "
            "\"(Name='chrome.exe' OR Name='chromium.exe') "
            "AND CommandLine LIKE '%browser-profile%'\" "
            "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            killed = True
            log.info("Killed signage browser processes via PowerShell")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    if not killed:
        # Fallback: find browser PID via tasklist + kill individually
        pid = find_browser_pid()
        if pid:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    capture_output=True, timeout=10,
                )
                log.info("Killed browser PID %d via taskkill", pid)
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


def scheduled_system_reboot(plat: str) -> None:
    """Perform a full system reboot (Linux/Pi only).

    Every mature signage project (PiSignage, Xibo, FullPageOS) recommends a
    weekly reboot as a safety net against slow memory accumulation that
    per-process restarts cannot catch — kernel slab caches, GPU driver
    allocations, and other resources only freed on reboot.
    """
    if plat not in ("pi", "linux"):
        log.warning("Scheduled reboot skipped — only supported on Linux/Pi (current: %s)", plat)
        return

    log.warning("Initiating scheduled system reboot...")
    try:
        subprocess.run(["sudo", "systemctl", "reboot"], timeout=30)
    except FileNotFoundError:
        # Fallback for systems without systemctl
        try:
            subprocess.run(["sudo", "reboot"], timeout=30)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            log.error("Failed to reboot: %s", e)
    except subprocess.TimeoutExpired:
        log.error("Reboot command timed out")


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
    mem_limit = cfg.get("browser_memory_limit_mb", 1024)
    memory_log_enabled = cfg.get("memory_log_enabled", False)
    memory_log_interval = cfg.get("memory_log_interval", 1800)
    reboot_day = cfg.get("scheduled_reboot_day")       # 0=Mon..6=Sun or None
    reboot_hour = cfg.get("scheduled_reboot_hour", 3)  # 0-23
    port = cfg.get("_port", 8080)
    use_https = cfg.get("_https", False)

    cms_fails = 0
    browser_fails = 0
    check_count = 0
    # Log a status heartbeat every STATUS_INTERVAL checks (~5 min at default 30s)
    STATUS_INTERVAL = 10
    start_time = time.monotonic()
    # First snapshot fires after startup_grace (settling delay), not after
    # the full memory_log_interval.  Subsequent snapshots follow the interval.
    last_memory_log = start_time + grace - memory_log_interval
    last_reboot_check_day = -1  # Track which weekday we last triggered a reboot

    if reboot_day is not None:
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_label = day_names[reboot_day] if 0 <= reboot_day <= 6 else f"day={reboot_day}"
        log.info(
            "Watchdog started: platform=%s, mode=%s, interval=%ds, grace=%ds, mem_log=%ds, "
            "reboot=%s@%02d:00",
            plat, mode, interval, grace, memory_log_interval, day_label, reboot_hour,
        )
    else:
        log.info(
            "Watchdog started: platform=%s, mode=%s, interval=%ds, grace=%ds, mem_log=%ds",
            plat, mode, interval, grace, memory_log_interval,
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

                    # Memory check — aggregate RSS of browser process tree
                    if mem_limit > 0:
                        if platform.system() == "Linux":
                            rss, proc_count = _read_total_browser_rss_linux(browser_pid)
                            log.debug("Browser total RSS: %d MB across %d processes (limit: %d MB)",
                                      rss, proc_count, mem_limit)
                        else:
                            rss = read_rss_mb(browser_pid)
                            log.debug("Browser PID %d RSS: %d MB (limit: %d MB)",
                                      browser_pid, rss or 0, mem_limit)
                        if rss is not None and rss > mem_limit:
                            log.warning(
                                "Browser total RSS %d MB exceeds limit %d MB — restarting",
                                rss, mem_limit,
                            )
                            restart_browser(plat)
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
                            if not once:
                                log.info("Cooldown 30s after browser restart")
                                time.sleep(30)
                                continue

            # --- Periodic status heartbeat ---
            check_count += 1
            if check_count % STATUS_INTERVAL == 0:
                parts = []
                if monitor_cms:
                    parts.append("CMS=ok" if cms_fails == 0 else f"CMS=failing({cms_fails}/{cms_threshold})")
                if monitor_browser:
                    bp = find_browser_pid()
                    if bp:
                        if platform.system() == "Linux":
                            rss_total, pc = _read_total_browser_rss_linux(bp)
                            parts.append(f"browser=ok(RSS {rss_total}MB/{mem_limit}MB, {pc} procs)")
                        else:
                            rss_val = read_rss_mb(bp)
                            parts.append(f"browser=ok(RSS {rss_val or '?'}MB/{mem_limit}MB)")
                    else:
                        parts.append(f"browser=not_found({browser_fails}/{browser_threshold})")
                log.info("Status: %s", ", ".join(parts))

            # --- Memory snapshot ---
            # Always snapshot in --once mode (diagnostic tool).
            # In normal mode, only if memory_log_enabled.
            should_snapshot = False
            if once:
                should_snapshot = True
            elif memory_log_enabled and memory_log_interval > 0:
                now = time.monotonic()
                if now - last_memory_log >= memory_log_interval:
                    should_snapshot = True

            if should_snapshot:
                try:
                    log_memory_snapshot(plat, mode)
                except Exception:
                    log.exception("Failed to collect memory snapshot")
                last_memory_log = time.monotonic()

            # --- Scheduled weekly system reboot (Linux/Pi only) ---
            if reboot_day is not None and not once:
                import datetime as _dt
                now_dt = _dt.datetime.now()
                if (now_dt.weekday() == reboot_day
                        and now_dt.hour == reboot_hour
                        and last_reboot_check_day != now_dt.weekday()):
                    last_reboot_check_day = now_dt.weekday()
                    log.warning(
                        "Scheduled weekly reboot (day=%d, hour=%d)",
                        reboot_day, reboot_hour,
                    )
                    scheduled_system_reboot(plat)
                    # If we're still running (non-Pi or reboot failed),
                    # continue the loop rather than firing again this hour.
                    time.sleep(3600)
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
