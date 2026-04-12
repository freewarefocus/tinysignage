"""Background monitor: logs Cog/WPE browser RSS on Linux (Pi) systems.

Runs hourly and reads /proc/<pid>/statm for the cog process.  Only activates
on Linux where the cog binary is present — a no-op on dev machines.
"""

import asyncio
import logging
import sys
from pathlib import Path

log = logging.getLogger("tinysignage.cog_monitor")

CHECK_INTERVAL = 3600  # 1 hour


def _find_cog_pid() -> int | None:
    """Return the PID of a running 'cog' process, or None."""
    if sys.platform != "linux":
        return None
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                comm = (entry / "comm").read_text().strip()
                if comm == "cog":
                    return int(entry.name)
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return None


def _read_rss_mb(pid: int) -> int | None:
    """Read RSS in MB from /proc/<pid>/statm (field 1 = resident pages)."""
    try:
        fields = Path(f"/proc/{pid}/statm").read_text().split()
        resident_pages = int(fields[1])
        # Page size is almost always 4096 on Linux/ARM
        return (resident_pages * 4096) // (1024 * 1024)
    except (OSError, IndexError, ValueError):
        return None


class CogMonitor:
    def __init__(self):
        self.running = False
        self._task: asyncio.Task | None = None
        self.last_rss_mb: int | None = None

    async def run(self):
        self.running = True
        # Quick check: if not Linux or no cog process, stay dormant
        if sys.platform != "linux":
            log.debug("CogMonitor: not Linux, staying dormant")
            return
        log.info("CogMonitor started (interval=%ds)", CHECK_INTERVAL)
        while self.running:
            try:
                self._check()
            except Exception:
                log.exception("CogMonitor check failed")
            await asyncio.sleep(CHECK_INTERVAL)

    def _check(self):
        pid = _find_cog_pid()
        if pid is None:
            self.last_rss_mb = None
            return
        rss = _read_rss_mb(pid)
        if rss is not None:
            self.last_rss_mb = rss
            log.info("cog[%d] RSS=%d MB", pid, rss)
        else:
            self.last_rss_mb = None
            log.warning("cog[%d] could not read RSS", pid)

    def start(self):
        self._task = asyncio.create_task(self._run_safe())

    async def _run_safe(self):
        try:
            await self.run()
        except asyncio.CancelledError:
            log.info("CogMonitor cancelled")
        except Exception:
            log.exception("CogMonitor crashed")

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


cog_monitor = CogMonitor()
