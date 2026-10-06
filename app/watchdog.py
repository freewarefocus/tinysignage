"""Background watchdog: checks device heartbeats and marks stale devices offline."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import async_session
from app.models import Device

log = logging.getLogger("tinysignage.watchdog")

CHECK_INTERVAL = 60  # seconds
STALE_THRESHOLD = 120  # seconds without heartbeat → offline


class Watchdog:
    def __init__(self):
        self.running = False
        self._task: asyncio.Task | None = None

    async def run(self):
        self.running = True
        log.info("Watchdog started")
        while self.running:
            try:
                await self._check_devices()
            except Exception:
                log.exception("Watchdog check failed")
            await asyncio.sleep(CHECK_INTERVAL)

    async def _check_devices(self):
        async with async_session() as session:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            result = await session.execute(select(Device))
            devices = result.scalars().all()

            for device in devices:
                # Use whichever timestamp is more recent
                # (polling updates last_seen; heartbeat updates both)
                timestamps = [t for t in (device.last_heartbeat, device.last_seen) if t]
                last_contact = max(timestamps) if timestamps else None
                if last_contact:
                    seconds_since = (now - last_contact).total_seconds()
                    if seconds_since > STALE_THRESHOLD and device.status == "online":
                        device.status = "offline"
                        log.info(
                            "Device %s (%s) marked offline — no contact for %ds",
                            device.name,
                            device.id[:8],
                            int(seconds_since),
                        )

            await session.commit()

    def start(self):
        self._task = asyncio.create_task(self._run_safe())

    async def _run_safe(self):
        try:
            await self.run()
        except asyncio.CancelledError:
            log.info("Watchdog cancelled")
        except Exception:
            log.exception("Watchdog crashed")

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


watchdog = Watchdog()
