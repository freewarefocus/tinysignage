from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin, require_device
from app.database import get_session
from app.models import ApiToken, Device

router = APIRouter()


@router.get("/health")
async def health_check():
    """Public health check — no auth required."""
    return {"status": "ok"}


@router.post("/player/heartbeat")
async def player_heartbeat(
    body: dict,
    request: Request,
    token: ApiToken = Depends(require_device),
    session: AsyncSession = Depends(get_session),
):
    """Receive heartbeat from a player device."""
    device_id = body.get("device_id")
    if not device_id:
        return {"error": "device_id required"}

    device = await session.get(Device, device_id)
    if not device:
        return {"error": "device not found"}

    now = datetime.now(timezone.utc)
    device.last_heartbeat = now
    device.last_seen = now
    device.status = "online"
    device.ip_address = request.client.host if request.client else None

    if "player_version" in body:
        device.player_version = body["player_version"]
    if "player_timezone" in body:
        device.player_timezone = body["player_timezone"]

    # Compute clock drift
    player_time_str = body.get("player_time")
    if player_time_str:
        try:
            player_time = datetime.fromisoformat(player_time_str.replace("Z", "+00:00"))
            drift = (now - player_time).total_seconds()
            device.clock_drift_seconds = round(drift, 1)
        except (ValueError, TypeError):
            pass

    await session.commit()
    return {"status": "ok", "server_time": now.isoformat()}


@router.get("/health/dashboard")
async def health_dashboard(
    _admin: ApiToken = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Return per-device health summary."""
    result = await session.execute(select(Device))
    devices = result.scalars().all()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    summary = []
    for d in devices:
        health = {
            "id": d.id,
            "name": d.name,
            "status": d.status,
            "last_heartbeat": d.last_heartbeat.isoformat() if d.last_heartbeat else None,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            "player_version": d.player_version,
            "player_timezone": d.player_timezone,
            "clock_drift_seconds": d.clock_drift_seconds,
            "warnings": [],
        }

        # Check staleness
        if d.last_heartbeat:
            seconds_since = (now - d.last_heartbeat).total_seconds()
            if seconds_since > 120:
                health["status"] = "offline"
                health["warnings"].append(
                    f"No heartbeat for {int(seconds_since)}s"
                )
        else:
            health["warnings"].append("Never sent a heartbeat")

        # Check clock drift
        if d.clock_drift_seconds is not None and abs(d.clock_drift_seconds) > 30:
            health["warnings"].append(
                f"Clock drift: {d.clock_drift_seconds:+.1f}s"
            )

        # Check timezone
        if d.player_timezone:
            # Just flag it for visibility; no server timezone to compare against yet
            pass

        summary.append(health)

    return {"devices": summary, "server_time": now.isoformat()}
