"""Tests for Watchdog._check_devices() logic from app/watchdog.py.

Feature tree refs: [FT-19.9]-[FT-19.10]

Strategy: Create devices with known last_heartbeat values, run
_check_devices(), verify status updates. We monkeypatch
app.watchdog.async_session to use the test session maker.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.watchdog import Watchdog
from tests.factories import create_device


async def test_online_device_within_threshold(engine, session):
    """last_heartbeat 60s ago, status='online' -> stays 'online'."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    device = await create_device(
        session, status="online",
        last_heartbeat=now - timedelta(seconds=60),
    )
    await session.commit()

    test_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    with patch("app.watchdog.async_session", test_session_maker):
        watchdog = Watchdog()
        await watchdog._check_devices()

    await session.refresh(device)
    assert device.status == "online"


async def test_online_device_beyond_threshold(engine, session):
    """last_heartbeat 180s ago, status='online' -> becomes 'offline'."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    device = await create_device(
        session, status="online",
        last_heartbeat=now - timedelta(seconds=180),
    )
    await session.commit()

    test_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    with patch("app.watchdog.async_session", test_session_maker):
        watchdog = Watchdog()
        await watchdog._check_devices()

    await session.refresh(device)
    assert device.status == "offline"


async def test_offline_device_stays_offline(engine, session):
    """Already offline, old heartbeat -> stays 'offline'."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    device = await create_device(
        session, status="offline",
        last_heartbeat=now - timedelta(seconds=300),
    )
    await session.commit()

    test_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    with patch("app.watchdog.async_session", test_session_maker):
        watchdog = Watchdog()
        await watchdog._check_devices()

    await session.refresh(device)
    assert device.status == "offline"


async def test_device_with_no_heartbeat(engine, session):
    """last_heartbeat=None, last_seen=None -> no crash, status unchanged."""
    device = await create_device(session, status="offline")
    # Ensure both are None
    device.last_heartbeat = None
    device.last_seen = None
    await session.commit()

    test_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    with patch("app.watchdog.async_session", test_session_maker):
        watchdog = Watchdog()
        await watchdog._check_devices()

    await session.refresh(device)
    assert device.status == "offline"


async def test_falls_back_to_last_seen(engine, session):
    """last_heartbeat=None, last_seen=180s ago, status='online' -> becomes 'offline'."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    device = await create_device(
        session, status="online",
        last_seen=now - timedelta(seconds=180),
    )
    device.last_heartbeat = None
    await session.commit()

    test_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    with patch("app.watchdog.async_session", test_session_maker):
        watchdog = Watchdog()
        await watchdog._check_devices()

    await session.refresh(device)
    assert device.status == "offline"
