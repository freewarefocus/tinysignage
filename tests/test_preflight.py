"""Tests for _run_preflight_checks() and _preflight_overall() from app/api/devices.py.

Feature tree refs: [FT-20.13]
"""

from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.devices import _run_preflight_checks, _preflight_overall


def _make_asset(file_size=1_000_000, duration=60, asset_type="image", is_enabled=True):
    """Create a mock asset with the fields preflight checks need."""
    return SimpleNamespace(
        file_size=file_size,
        duration=duration,
        asset_type=asset_type,
        is_enabled=is_enabled,
        content_hash="abc123",
        id="fake-id",
    )


def _make_item(asset):
    """Create a mock playlist item wrapping an asset."""
    return SimpleNamespace(asset=asset, order=0)


def _make_playlist(items):
    """Create a mock playlist with items."""
    return SimpleNamespace(items=items)


def _make_device(storage_free_mb=None, ram_mb=None, capabilities_updated_at=None):
    """Create a mock device with hardware info."""
    return SimpleNamespace(
        storage_free_mb=storage_free_mb,
        ram_mb=ram_mb,
        capabilities_updated_at=capabilities_updated_at,
    )


def _find_check(checks, check_name):
    """Find a check by its name in the results list."""
    return next(c for c in checks if c["check"] == check_name)


def test_preflight_pass_all():
    """Device with ample storage/RAM -> overall='pass'."""
    asset = _make_asset(file_size=1_000_000, duration=60, asset_type="image")
    device = _make_device(storage_free_mb=500, ram_mb=8192,
                          capabilities_updated_at=datetime.now(timezone.utc))
    playlist = _make_playlist([_make_item(asset)])

    checks = _run_preflight_checks(device, playlist)
    assert _preflight_overall(checks) == "pass"


def test_preflight_storage_fail():
    """Playlist total > device free storage -> storage check='fail'."""
    # 500 MB file, only 100 MB free
    asset = _make_asset(file_size=500 * 1024 * 1024)
    device = _make_device(storage_free_mb=100, ram_mb=8192)
    playlist = _make_playlist([_make_item(asset)])

    checks = _run_preflight_checks(device, playlist)
    assert _find_check(checks, "storage")["status"] == "fail"


def test_preflight_storage_warn():
    """Playlist total > 90% of free storage -> storage check='warn'."""
    # 95 MB file, 100 MB free (95% used)
    asset = _make_asset(file_size=95 * 1024 * 1024)
    device = _make_device(storage_free_mb=100, ram_mb=8192)
    playlist = _make_playlist([_make_item(asset)])

    checks = _run_preflight_checks(device, playlist)
    assert _find_check(checks, "storage")["status"] == "warn"


def test_preflight_storage_unknown():
    """Device storage_free_mb=None -> storage check='unknown'."""
    asset = _make_asset()
    device = _make_device(storage_free_mb=None, ram_mb=8192)
    playlist = _make_playlist([_make_item(asset)])

    checks = _run_preflight_checks(device, playlist)
    assert _find_check(checks, "storage")["status"] == "unknown"


def test_preflight_ram_warn_heavy_video():
    """>30 min video, <4096 MB RAM -> ram check='warn'."""
    # 35 minutes of video, 2048 MB RAM
    asset = _make_asset(duration=35 * 60, asset_type="video")
    device = _make_device(storage_free_mb=500, ram_mb=2048)
    playlist = _make_playlist([_make_item(asset)])

    checks = _run_preflight_checks(device, playlist)
    assert _find_check(checks, "ram")["status"] == "warn"


def test_preflight_ram_warn_moderate_video():
    """>10 min video, <2048 MB RAM -> ram check='warn'."""
    # 15 minutes of video, 1024 MB RAM
    asset = _make_asset(duration=15 * 60, asset_type="video")
    device = _make_device(storage_free_mb=500, ram_mb=1024)
    playlist = _make_playlist([_make_item(asset)])

    checks = _run_preflight_checks(device, playlist)
    assert _find_check(checks, "ram")["status"] == "warn"


def test_preflight_ram_pass():
    """Light video, adequate RAM -> ram check='pass'."""
    asset = _make_asset(duration=5 * 60, asset_type="video")
    device = _make_device(storage_free_mb=500, ram_mb=8192)
    playlist = _make_playlist([_make_item(asset)])

    checks = _run_preflight_checks(device, playlist)
    assert _find_check(checks, "ram")["status"] == "pass"


def test_preflight_ram_unknown():
    """Device ram_mb=None -> ram check='unknown'."""
    asset = _make_asset(duration=60, asset_type="video")
    device = _make_device(storage_free_mb=500, ram_mb=None)
    playlist = _make_playlist([_make_item(asset)])

    checks = _run_preflight_checks(device, playlist)
    assert _find_check(checks, "ram")["status"] == "unknown"


def test_preflight_overall_fail_if_any_fail():
    """One 'fail' + others 'pass' -> overall='fail'."""
    checks = [
        {"check": "storage", "status": "fail", "message": "", "details": {}},
        {"check": "ram", "status": "pass", "message": "", "details": {}},
        {"check": "gpio", "status": "not_applicable", "message": "", "details": {}},
    ]
    assert _preflight_overall(checks) == "fail"


def test_preflight_overall_warn_if_any_warn():
    """One 'warn' + others 'pass' -> overall='warn'."""
    checks = [
        {"check": "storage", "status": "pass", "message": "", "details": {}},
        {"check": "ram", "status": "warn", "message": "", "details": {}},
        {"check": "gpio", "status": "not_applicable", "message": "", "details": {}},
    ]
    assert _preflight_overall(checks) == "warn"
