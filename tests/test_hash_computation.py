"""Tests for playlist/zone/trigger hash computation.

Feature tree refs: [FT-20.12]

Tests _playlist_hash() from app/api/playlists.py. Hash changes are used
by the player to detect when it needs to re-fetch content.
"""

from types import SimpleNamespace

from app.api.playlists import _playlist_hash


def _make_asset(asset_id="a1", content_hash="hash1", duration=10,
                is_enabled=True, transition_type=None, transition_duration=None):
    return SimpleNamespace(
        id=asset_id, content_hash=content_hash, duration=duration,
        is_enabled=is_enabled, transition_type=transition_type,
        transition_duration=transition_duration,
    )


def _make_item(order, asset, transition_type=None, transition_duration=None,
               duration=None, object_fit=None, effect=None):
    return SimpleNamespace(order=order, asset=asset,
                           transition_type=transition_type,
                           transition_duration=transition_duration,
                           duration=duration,
                           object_fit=object_fit,
                           effect=effect)


def test_playlist_hash_deterministic():
    """Same items -> same hash."""
    asset = _make_asset()
    items = [_make_item(0, asset)]
    assert _playlist_hash(items) == _playlist_hash(items)


def test_playlist_hash_changes_on_add():
    """Add item -> hash changes."""
    asset1 = _make_asset(asset_id="a1", content_hash="h1")
    asset2 = _make_asset(asset_id="a2", content_hash="h2")

    items_before = [_make_item(0, asset1)]
    items_after = [_make_item(0, asset1), _make_item(1, asset2)]

    assert _playlist_hash(items_before) != _playlist_hash(items_after)


def test_playlist_hash_changes_on_remove():
    """Remove item -> hash changes."""
    asset1 = _make_asset(asset_id="a1", content_hash="h1")
    asset2 = _make_asset(asset_id="a2", content_hash="h2")

    items_before = [_make_item(0, asset1), _make_item(1, asset2)]
    items_after = [_make_item(0, asset1)]

    assert _playlist_hash(items_before) != _playlist_hash(items_after)


def test_playlist_hash_empty():
    """No items -> consistent empty hash."""
    h1 = _playlist_hash([])
    h2 = _playlist_hash([])
    assert h1 == h2
    assert len(h1) == 16  # truncated SHA-256


def test_zones_hash_deterministic():
    """Same zones data -> same hash (via playlist hash on zone playlists)."""
    asset = _make_asset()
    items = [_make_item(0, asset)]
    h1 = _playlist_hash(items)
    h2 = _playlist_hash(items)
    assert h1 == h2


def test_zones_hash_changes_on_zone_add():
    """Adding a zone playlist changes the combined hash."""
    asset1 = _make_asset(asset_id="a1", content_hash="h1")
    asset2 = _make_asset(asset_id="a2", content_hash="h2")

    zone1_items = [_make_item(0, asset1)]
    zone2_items = [_make_item(0, asset2)]

    hash_one_zone = _playlist_hash(zone1_items)
    hash_two_zones = _playlist_hash(zone1_items + zone2_items)

    assert hash_one_zone != hash_two_zones


def test_trigger_flow_hash_deterministic():
    """Same branches/items -> same hash."""
    asset = _make_asset(asset_id="branch-a", content_hash="bh1")
    items = [_make_item(0, asset)]
    assert _playlist_hash(items) == _playlist_hash(items)


def test_trigger_flow_hash_changes_on_webhook_fire():
    """Changing content_hash (simulating webhook fire timestamp) -> hash changes."""
    asset_before = _make_asset(asset_id="a1", content_hash="before-fire")
    asset_after = _make_asset(asset_id="a1", content_hash="after-fire")

    items_before = [_make_item(0, asset_before)]
    items_after = [_make_item(0, asset_after)]

    assert _playlist_hash(items_before) != _playlist_hash(items_after)
