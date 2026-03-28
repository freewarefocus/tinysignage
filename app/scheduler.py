import asyncio
import logging
import random
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models import Asset, Playlist, PlaylistItem, Settings

log = logging.getLogger("tinysignage.scheduler")


class Scheduler:
    """Tracks current playlist position for admin status display.

    Players now self-advance via polling; the scheduler no longer broadcasts
    over WebSocket. It still cycles through the playlist to maintain
    current_asset_id/name for the /api/status endpoint.
    """

    def __init__(self):
        self.current_asset_id: str | None = None
        self.current_asset_name: str | None = None
        self.running = False
        self._task: asyncio.Task | None = None
        self._skip_event = asyncio.Event()
        self._skip_direction = 0  # 0=next, -1=prev
        self._jump_target: str | None = None

    async def get_active_playlist(self) -> list[Asset]:
        """Get enabled assets from the default playlist, filtered by schedule window."""
        async with async_session() as session:
            # SQLite returns naive datetimes; strip tzinfo for comparison
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            result = await session.execute(
                select(Playlist)
                .where(Playlist.is_default == True)
                .options(
                    selectinload(Playlist.items).selectinload(PlaylistItem.asset)
                )
            )
            playlist = result.scalars().first()
            if not playlist:
                return []

            assets = []
            for item in playlist.items:
                asset = item.asset
                if not asset or not asset.is_enabled:
                    continue
                if asset.start_date and asset.start_date > now:
                    continue
                if asset.end_date and asset.end_date < now:
                    continue
                assets.append(asset)
            return assets

    async def get_settings(self) -> Settings:
        async with async_session() as session:
            return await session.get(Settings, 1)

    def skip_to_next(self):
        self._skip_direction = 0
        self._skip_event.set()

    def skip_to_previous(self):
        self._skip_direction = -1
        self._skip_event.set()

    def jump_to(self, asset_id: str):
        self._jump_target = asset_id
        self._skip_event.set()

    async def _wait_duration(self, duration: float):
        """Sleep for duration, but wake up early if skip requested."""
        self._skip_event.clear()
        try:
            await asyncio.wait_for(self._skip_event.wait(), timeout=duration)
        except asyncio.TimeoutError:
            pass  # Normal expiry

    async def run(self):
        self.running = True
        log.info("Scheduler started")
        while self.running:
            try:
                playlist = await self.get_active_playlist()
            except Exception:
                log.exception("Failed to fetch playlist, retrying in 5s")
                await asyncio.sleep(5)
                continue

            if not playlist:
                self.current_asset_id = None
                self.current_asset_name = None
                await asyncio.sleep(5)
                continue

            try:
                settings = await self.get_settings()
            except Exception:
                log.exception("Failed to fetch settings, retrying in 5s")
                await asyncio.sleep(5)
                continue

            if settings.shuffle:
                playlist = list(playlist)
                random.shuffle(playlist)

            index = 0

            # Handle jump target from previous cycle
            if self._jump_target:
                for i, asset in enumerate(playlist):
                    if asset.id == self._jump_target:
                        index = i
                        break
                self._jump_target = None

            while index < len(playlist) and self.running:
                asset = playlist[index]

                try:
                    refreshed = await self._refresh_asset(asset.id)
                except Exception:
                    log.exception("Failed to refresh asset %s", asset.id)
                    index += 1
                    continue

                if refreshed is None or not refreshed.is_enabled:
                    index += 1
                    continue

                self.current_asset_id = asset.id
                self.current_asset_name = asset.name

                if asset.duration == 0 and asset.asset_type == "video":
                    duration = 300
                else:
                    duration = asset.duration or settings.default_duration

                await self._wait_duration(duration)

                # Handle jump — break to re-fetch playlist
                if self._jump_target:
                    break

                # Handle previous
                if self._skip_direction == -1:
                    index = max(0, index - 1)
                    self._skip_direction = 0
                else:
                    index += 1

        log.info("Scheduler stopped")

    async def _refresh_asset(self, asset_id: str) -> Asset | None:
        async with async_session() as session:
            return await session.get(Asset, asset_id)

    def start(self):
        self._task = asyncio.create_task(self._run_safe())

    async def _run_safe(self):
        """Wrapper that catches CancelledError and unexpected crashes."""
        try:
            await self.run()
        except asyncio.CancelledError:
            log.info("Scheduler cancelled")
        except Exception:
            log.exception("Scheduler crashed unexpectedly")

    async def stop(self):
        self.running = False
        self._skip_event.set()  # Wake up any sleeping wait
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


scheduler = Scheduler()
