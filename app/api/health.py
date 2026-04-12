import json
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import generate_token, hash_token, require_admin, require_device, require_viewer
from app.database import get_session
from app.models import ApiToken, Device, Settings

router = APIRouter()

_config_path = Path("config.yaml")


@router.get("/health")
async def health_check():
    """Public health check — no auth required."""
    return {"status": "ok"}


@router.post("/player/bootstrap")
async def player_bootstrap(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Local-only endpoint: auto-pair the local player with the seeded default device.

    Only works for requests from localhost (127.0.0.1 / ::1).  Reads the
    device_id written to config.yaml during install, finds or creates a
    device token for it, and returns credentials the player can store.
    This eliminates the need for manual registration on headless Pi displays.
    """
    client_ip = request.client.host if request.client else ""
    if client_ip not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="Bootstrap only available from localhost")

    try:
        config = yaml.safe_load(_config_path.read_text())
    except Exception:
        raise HTTPException(status_code=500, detail="Cannot read config.yaml")

    device_id = config.get("device_id")
    if not device_id:
        raise HTTPException(status_code=404, detail="No device_id in config.yaml")

    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Default device not found in database")

    # Check for an existing bootstrap token (don't touch tokens from setup wizard)
    result = await session.execute(
        select(ApiToken).where(
            ApiToken.device_id == device_id,
            ApiToken.role == "device",
            ApiToken.is_active == True,
            ApiToken.created_by == "local_bootstrap",
        )
    )
    bootstrap_token = result.scalars().first()

    if bootstrap_token:
        # Re-key the existing bootstrap token
        plaintext = generate_token()
        bootstrap_token.token_hash = hash_token(plaintext)
    else:
        # Create a new bootstrap token (leaves setup wizard tokens intact)
        plaintext = generate_token()
        new_token = ApiToken(
            token_hash=hash_token(plaintext),
            name=f"Device: {device.name} (bootstrap)",
            role="device",
            device_id=device_id,
            created_by="local_bootstrap",
        )
        session.add(new_token)

    await session.commit()

    return {
        "device_id": device_id,
        "token": plaintext,
        "device_name": device.name,
        "status": device.status,
    }


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
        raise HTTPException(status_code=400, detail="device_id required")

    if device_id != token.device_id:
        raise HTTPException(status_code=403, detail="Token not authorized for this device")

    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    device.last_heartbeat = now
    device.last_seen = now
    device.ip_address = request.client.host if request.client else None

    # Pending devices: update last_seen but don't promote to online
    if device.status == "pending":
        await session.commit()
        return {"status": "pending", "server_time": now.isoformat()}

    device.status = "online"

    if "player_version" in body:
        device.player_version = body["player_version"]
    if "player_type" in body:
        device.player_type = body["player_type"]
    if "player_timezone" in body:
        device.player_timezone = body["player_timezone"]
    if "storage_free_mb" in body:
        device.storage_free_mb = body["storage_free_mb"]
    if "uptime_seconds" in body:
        device.uptime_seconds = body["uptime_seconds"]
    if "js_heap_used_mb" in body:
        device.js_heap_used_mb = body["js_heap_used_mb"]
    if "js_heap_total_mb" in body:
        device.js_heap_total_mb = body["js_heap_total_mb"]
    if "dom_responsive" in body:
        device.dom_responsive = body["dom_responsive"]

    # Compute clock drift
    player_time_str = body.get("player_time")
    if player_time_str:
        try:
            player_time = datetime.fromisoformat(
                player_time_str.replace("Z", "+00:00")
            ).replace(tzinfo=None)
            drift = (now - player_time).total_seconds()
            device.clock_drift_seconds = round(drift, 1)
        except (ValueError, TypeError):
            pass

    # Build response with restart flag and health settings
    resp = {"status": "ok", "server_time": now.isoformat()}

    if device.restart_requested:
        resp["restart"] = True
        device.restart_requested = False
    else:
        resp["restart"] = False

    # Attach server-side cog RSS reading (Pi only)
    from app.cog_monitor import cog_monitor
    if cog_monitor.last_rss_mb is not None:
        device.cog_rss_mb = cog_monitor.last_rss_mb

    # Include player health settings from global Settings
    settings = await session.get(Settings, 1)
    if settings:
        resp["restart_hour"] = settings.player_restart_hour
        resp["memory_limit_mb"] = settings.player_memory_limit_mb if settings.player_memory_limit_mb is not None else 200
    else:
        resp["restart_hour"] = None
        resp["memory_limit_mb"] = 200

    await session.commit()
    return resp


@router.post("/devices/{device_id}/player-log")
async def upload_player_log(
    device_id: str,
    body: dict,
    token: ApiToken = Depends(require_device),
    session: AsyncSession = Depends(get_session),
):
    """Receive player log entries from a device (sent with heartbeat)."""
    if device_id != token.device_id:
        raise HTTPException(status_code=403, detail="Token not authorized for this device")

    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")

    entries = body.get("entries", [])
    if not isinstance(entries, list):
        raise HTTPException(status_code=422, detail="entries must be an array")

    # Store as JSON text (ring buffer — player already trims to 200)
    device.player_log = json.dumps(entries[-200:])
    device.player_log_updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.commit()
    return {"status": "ok", "stored": len(entries)}


@router.get("/devices/{device_id}/player-log")
async def get_player_log(
    device_id: str,
    level: str | None = None,
    search: str | None = None,
    _token: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    """Retrieve player log for a device. Viewer+ access."""
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")

    entries = []
    if device.player_log:
        try:
            entries = json.loads(device.player_log)
        except (json.JSONDecodeError, TypeError):
            entries = []

    # Filter by level
    if level:
        level_lower = level.lower()
        entries = [e for e in entries if e.get("l", "").lower() == level_lower]

    # Filter by search term
    if search:
        search_lower = search.lower()
        entries = [e for e in entries if search_lower in e.get("m", "").lower()]

    return {
        "device_id": device_id,
        "device_name": device.name,
        "entries": entries,
        "total": len(entries),
        "updated_at": device.player_log_updated_at.isoformat() if device.player_log_updated_at else None,
    }


@router.post("/devices/{device_id}/capabilities")
async def report_capabilities(
    device_id: str,
    body: dict,
    request: Request,
    token: ApiToken = Depends(require_device),
    session: AsyncSession = Depends(get_session),
):
    """Receive capability report from a player device."""
    if device_id != token.device_id:
        raise HTTPException(status_code=403, detail="Token not authorized for this device")

    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Extract promoted fields from nested payload
    software = body.get("software", {})
    if software.get("player_version"):
        device.player_version = software["player_version"]
    if software.get("player_type"):
        device.player_type = software["player_type"]

    hardware = body.get("hardware", {})
    if hardware.get("ram_mb") is not None:
        device.ram_mb = hardware["ram_mb"]
    if hardware.get("storage_total_mb") is not None:
        device.storage_total_mb = hardware["storage_total_mb"]
    if hardware.get("storage_free_mb") is not None:
        device.storage_free_mb = hardware["storage_free_mb"]
    if hardware.get("gpio_supported") is not None:
        device.gpio_supported = hardware["gpio_supported"]
    if hardware.get("cpu_cores") is not None:
        pass  # Not promoted to a column; stored in JSON blob

    display = body.get("display", {})
    if display.get("resolution_detected"):
        device.resolution_detected = display["resolution_detected"]

    # Store full blob
    device.capabilities = json.dumps(body)
    device.capabilities_updated_at = now
    device.last_seen = now
    if device.status != "pending":
        device.status = "online"

    await session.commit()
    return {"status": "ok"}


@router.get("/player/hardware")
async def player_hardware(
    _token: ApiToken = Depends(require_device),
):
    """Return server-side hardware stats (RAM, disk) for WPE/non-Chromium players."""
    ram_total_mb = None
    if platform.system() == "Linux":
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        ram_total_mb = round(kb / 1024)
                        break
        except (OSError, ValueError):
            pass

    disk_total_mb = None
    disk_free_mb = None
    media_dir = Path("media")
    if media_dir.is_dir():
        try:
            usage = shutil.disk_usage(media_dir.resolve())
            disk_total_mb = round(usage.total / (1024 * 1024))
            disk_free_mb = round(usage.free / (1024 * 1024))
        except OSError:
            pass

    return {
        "ram_total_mb": ram_total_mb,
        "disk_total_mb": disk_total_mb,
        "disk_free_mb": disk_free_mb,
        "source": "server",
    }


@router.get("/health/dashboard")
async def health_dashboard(
    _admin: ApiToken = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
):
    """Return per-device health summary."""
    result = await session.execute(select(Device))
    devices = result.scalars().all()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    summary = []
    for d in devices:
        signals = _compute_signals(d, now)
        # Overall status = worst signal
        signal_levels = [s["level"] for s in signals.values()]
        if "red" in signal_levels:
            overall = "red"
        elif "yellow" in signal_levels:
            overall = "yellow"
        else:
            overall = "green"

        warnings = []
        for sig_name, sig in signals.items():
            if sig["level"] != "green" and sig.get("message"):
                warnings.append(sig["message"])

        # Check clock drift (kept as warning, not a signal)
        if d.clock_drift_seconds is not None and abs(d.clock_drift_seconds) > 30:
            warnings.append(f"Clock drift: {d.clock_drift_seconds:+.1f}s")

        health = {
            "id": d.id,
            "name": d.name,
            "status": d.status,
            "overall": overall,
            "signals": signals,
            "last_heartbeat": d.last_heartbeat.isoformat() if d.last_heartbeat else None,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            "player_version": d.player_version,
            "player_type": d.player_type,
            "player_timezone": d.player_timezone,
            "clock_drift_seconds": d.clock_drift_seconds,
            "resolution_detected": d.resolution_detected,
            "ram_mb": d.ram_mb,
            "storage_total_mb": d.storage_total_mb,
            "storage_free_mb": d.storage_free_mb,
            "js_heap_used_mb": d.js_heap_used_mb,
            "js_heap_total_mb": d.js_heap_total_mb,
            "dom_responsive": d.dom_responsive,
            "uptime_seconds": d.uptime_seconds,
            "capabilities_updated_at": d.capabilities_updated_at.isoformat() if d.capabilities_updated_at else None,
            "warnings": warnings,
        }
        summary.append(health)

    return {"devices": summary, "server_time": now.isoformat()}


def _compute_signals(device: Device, now: datetime) -> dict:
    """Compute per-signal health status for a device."""
    signals = {}

    # Heartbeat signal
    if device.last_heartbeat:
        minutes_since = (now - device.last_heartbeat).total_seconds() / 60
        if minutes_since < 15:
            signals["heartbeat"] = {"level": "green", "message": ""}
        elif minutes_since < 60:
            signals["heartbeat"] = {"level": "yellow", "message": f"No heartbeat for {int(minutes_since)} min"}
        else:
            signals["heartbeat"] = {"level": "red", "message": f"No heartbeat for {int(minutes_since)} min"}
    else:
        signals["heartbeat"] = {"level": "red", "message": "Never sent a heartbeat"}

    # Storage signal
    if device.storage_free_mb is not None and device.storage_total_mb is not None and device.storage_total_mb > 0:
        pct_free = device.storage_free_mb / device.storage_total_mb
        if pct_free > 0.2 and device.storage_free_mb > 1024:
            signals["storage"] = {"level": "green", "message": ""}
        elif pct_free < 0.1 or device.storage_free_mb < 500:
            signals["storage"] = {"level": "red", "message": f"Storage critically low: {device.storage_free_mb} MB free ({pct_free:.0%})"}
        else:
            signals["storage"] = {"level": "yellow", "message": f"Storage low: {device.storage_free_mb} MB free ({pct_free:.0%})"}
    elif device.storage_free_mb is not None:
        # Have free but not total — can only check absolute
        if device.storage_free_mb > 1024:
            signals["storage"] = {"level": "green", "message": ""}
        elif device.storage_free_mb < 500:
            signals["storage"] = {"level": "red", "message": f"Storage critically low: {device.storage_free_mb} MB free"}
        else:
            signals["storage"] = {"level": "yellow", "message": f"Storage low: {device.storage_free_mb} MB free"}
    else:
        signals["storage"] = {"level": "yellow", "message": "Storage unknown"}

    # Resolution signal
    if device.resolution_detected:
        try:
            w, h = device.resolution_detected.split("x")
            w, h = int(w), int(h)
            if w >= 1280 and h >= 720:
                signals["resolution"] = {"level": "green", "message": ""}
            else:
                signals["resolution"] = {"level": "yellow", "message": f"Low resolution: {device.resolution_detected}"}
        except (ValueError, AttributeError):
            signals["resolution"] = {"level": "yellow", "message": "Resolution not detected"}
    else:
        signals["resolution"] = {"level": "yellow", "message": "Resolution not detected"}

    # RAM signal
    if device.ram_mb is not None:
        if device.ram_mb >= 2048:
            signals["ram"] = {"level": "green", "message": ""}
        else:
            signals["ram"] = {"level": "yellow", "message": f"Low RAM: {device.ram_mb} MB"}
    else:
        signals["ram"] = {"level": "yellow", "message": "RAM unknown"}

    # JS Heap signal (memory_limit_mb defaults to 200 if not set)
    memory_limit = 200
    if device.js_heap_used_mb is not None:
        pct = device.js_heap_used_mb / memory_limit if memory_limit > 0 else 0
        if pct > 1.0:
            signals["js_heap"] = {"level": "red", "message": f"JS heap {device.js_heap_used_mb} MB exceeds {memory_limit} MB limit"}
        elif pct > 0.7:
            signals["js_heap"] = {"level": "yellow", "message": f"JS heap {device.js_heap_used_mb} MB ({pct:.0%} of limit)"}
        else:
            signals["js_heap"] = {"level": "green", "message": ""}
    elif device.last_heartbeat is not None:
        # Device is checking in but browser doesn't expose performance.memory
        signals["js_heap"] = {"level": "green", "message": "N/A (unsupported by browser)"}
    else:
        signals["js_heap"] = {"level": "grey", "message": "Waiting for first heartbeat"}

    # DOM responsiveness signal
    if device.dom_responsive is not None:
        if device.dom_responsive:
            signals["responsiveness"] = {"level": "green", "message": ""}
        else:
            signals["responsiveness"] = {"level": "red", "message": "Player DOM unresponsive"}
    else:
        signals["responsiveness"] = {"level": "yellow", "message": "Responsiveness unknown"}

    return signals
