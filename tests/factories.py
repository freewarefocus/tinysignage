import uuid
from datetime import datetime, timezone, timedelta
from app.auth import generate_token, hash_token, hash_password
from app.models import (
    Asset, ApiToken, Device, DeviceGroup, DeviceGroupMembership,
    Layout, LayoutZone, Override, Playlist, PlaylistItem,
    Schedule, Settings, Tag, AssetTag, TriggerFlow, TriggerBranch, User,
)


async def create_settings(session, **overrides) -> Settings:
    """Create Settings singleton. Merges overrides with defaults."""
    defaults = {"id": 1, "transition_duration": 1.0, "transition_type": "fade",
                "default_duration": 10, "shuffle": False}
    defaults.update(overrides)
    settings = Settings(**defaults)
    session.add(settings)
    await session.flush()
    return settings


async def create_user(session, username="testadmin", role="admin",
                      password="testpass123", **overrides) -> tuple[User, str]:
    """Create a User. Returns (user, plaintext_password)."""
    user = User(
        username=username,
        display_name=overrides.pop("display_name", username),
        password_hash=hash_password(password),
        role=role,
        **overrides,
    )
    session.add(user)
    await session.flush()
    return user, password


async def create_token(session, role="admin", device_id=None,
                       user_id=None, **overrides) -> tuple[ApiToken, str]:
    """Create an ApiToken. Returns (token_record, plaintext_token).
    The plaintext token is what you pass in the Authorization: Bearer header.
    """
    plaintext = generate_token()
    token = ApiToken(
        token_hash=hash_token(plaintext),
        name=overrides.pop("name", f"Test {role} token"),
        role=role,
        device_id=device_id,
        user_id=user_id,
        **overrides,
    )
    session.add(token)
    await session.flush()
    return token, plaintext


async def create_playlist(session, name="Test Playlist",
                          is_default=False, **overrides) -> Playlist:
    """Create a Playlist."""
    playlist = Playlist(name=name, is_default=is_default, **overrides)
    session.add(playlist)
    await session.flush()
    return playlist


async def create_asset(session, name="test.png", asset_type="image",
                       uri="test.png", duration=10, **overrides) -> Asset:
    """Create an Asset."""
    asset = Asset(
        name=name, asset_type=asset_type, uri=uri,
        duration=duration, **overrides,
    )
    session.add(asset)
    await session.flush()
    return asset


async def create_playlist_item(session, playlist_id, asset_id,
                                order=0) -> PlaylistItem:
    """Add an asset to a playlist."""
    item = PlaylistItem(
        playlist_id=playlist_id, asset_id=asset_id, order=order,
    )
    session.add(item)
    await session.flush()
    return item


async def create_device(session, name="Test Player",
                        playlist_id=None, **overrides) -> Device:
    """Create a Device."""
    device = Device(name=name, playlist_id=playlist_id, **overrides)
    session.add(device)
    await session.flush()
    return device


async def create_device_group(session, name="Test Group",
                               **overrides) -> DeviceGroup:
    """Create a DeviceGroup."""
    group = DeviceGroup(name=name, **overrides)
    session.add(group)
    await session.flush()
    return group


async def add_device_to_group(session, device_id, group_id) -> DeviceGroupMembership:
    """Add a device to a group."""
    membership = DeviceGroupMembership(device_id=device_id, group_id=group_id)
    session.add(membership)
    await session.flush()
    return membership


async def create_layout(session, name="Test Layout", **overrides) -> Layout:
    """Create a Layout."""
    layout = Layout(name=name, **overrides)
    session.add(layout)
    await session.flush()
    return layout


async def create_zone(session, layout_id, name="Main Zone",
                      zone_type="main", **overrides) -> LayoutZone:
    """Create a LayoutZone."""
    defaults = {
        "x_percent": 0.0, "y_percent": 0.0,
        "width_percent": 100.0, "height_percent": 100.0,
        "z_index": 0,
    }
    defaults.update(overrides)
    zone = LayoutZone(layout_id=layout_id, name=name, zone_type=zone_type, **defaults)
    session.add(zone)
    await session.flush()
    return zone


async def create_schedule(session, name="Test Schedule", playlist_id=None,
                           target_type="all", **overrides) -> Schedule:
    """Create a Schedule."""
    schedule = Schedule(
        name=name, playlist_id=playlist_id,
        target_type=target_type, **overrides,
    )
    session.add(schedule)
    await session.flush()
    return schedule


async def create_override(session, name="Test Override",
                           content_type="message", content="Emergency!",
                           target_type="all", **overrides) -> Override:
    """Create an Override."""
    override = Override(
        name=name, content_type=content_type, content=content,
        target_type=target_type, **overrides,
    )
    session.add(override)
    await session.flush()
    return override


async def create_tag(session, name="test-tag", color="#7c83ff") -> Tag:
    """Create a Tag."""
    tag = Tag(name=name, color=color)
    session.add(tag)
    await session.flush()
    return tag


async def create_trigger_flow(session, name="Test Flow",
                                **overrides) -> TriggerFlow:
    """Create a TriggerFlow."""
    flow = TriggerFlow(name=name, **overrides)
    session.add(flow)
    await session.flush()
    return flow


async def create_trigger_branch(session, flow_id, source_playlist_id,
                                 target_playlist_id, trigger_type="keyboard",
                                 trigger_config="{}", **overrides) -> TriggerBranch:
    """Create a TriggerBranch."""
    branch = TriggerBranch(
        flow_id=flow_id,
        source_playlist_id=source_playlist_id,
        target_playlist_id=target_playlist_id,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        **overrides,
    )
    session.add(branch)
    await session.flush()
    return branch
