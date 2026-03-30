import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SchemaVersion(Base):
    __tablename__ = "schema_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(10), nullable=False)
    uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, default=10)
    play_order: Mapped[int] = mapped_column(Integer, default=0)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mimetype: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transition_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    transition_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    playlist_items: Mapped[list["PlaylistItem"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    asset_tags: Mapped[list["AssetTag"]] = relationship(cascade="all, delete-orphan")


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    transition_duration: Mapped[float] = mapped_column(Float, default=1.0)
    transition_type: Mapped[str] = mapped_column(String(20), default="fade")
    default_duration: Mapped[int] = mapped_column(Integer, default=10)
    shuffle: Mapped[bool] = mapped_column(Boolean, default=False)


class Layout(Base):
    __tablename__ = "layouts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    zones: Mapped[list["LayoutZone"]] = relationship(
        back_populates="layout", cascade="all, delete-orphan"
    )
    devices: Mapped[list["Device"]] = relationship(back_populates="layout")


class LayoutZone(Base):
    __tablename__ = "layout_zones"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    layout_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("layouts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    zone_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="main"
    )  # "main", "ticker", "sidebar", "pip"
    x_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    y_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    width_percent: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    height_percent: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    z_index: Mapped[int] = mapped_column(Integer, default=0)
    playlist_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("playlists.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    layout: Mapped["Layout"] = relationship(back_populates="zones")
    playlist: Mapped["Playlist | None"] = relationship()


class Device(Base):
    __tablename__ = "devices"
    # tenant_id: deferred until SaaS work begins

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Default Player")
    playlist_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("playlists.id", ondelete="SET NULL"), nullable=True
    )
    layout_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("layouts.id", ondelete="SET NULL"), nullable=True
    )
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="offline")
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    player_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    player_timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    clock_drift_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    player_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    gpio_supported: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    resolution_detected: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ram_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_total_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_free_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capabilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    capabilities_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    registration_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    registration_expires: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    playlist: Mapped["Playlist | None"] = relationship(back_populates="devices")
    layout: Mapped["Layout | None"] = relationship(back_populates="devices")


class Playlist(Base):
    __tablename__ = "playlists"
    # tenant_id: deferred until SaaS work begins

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    transition_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    transition_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    default_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shuffle: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    mode: Mapped[str] = mapped_column(
        String(10), nullable=False, default="simple", server_default="simple"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    items: Mapped[list["PlaylistItem"]] = relationship(
        back_populates="playlist", cascade="all, delete-orphan",
        order_by="PlaylistItem.order"
    )
    devices: Mapped[list["Device"]] = relationship(back_populates="playlist")


class DeviceGroup(Base):
    __tablename__ = "device_groups"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    memberships: Mapped[list["DeviceGroupMembership"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class DeviceGroupMembership(Base):
    __tablename__ = "device_group_memberships"

    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("device_groups.id", ondelete="CASCADE"), primary_key=True
    )

    device: Mapped["Device"] = relationship()
    group: Mapped["DeviceGroup"] = relationship(back_populates="memberships")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="viewer"
    )  # "admin", "editor", "viewer"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    theme_preference: Mapped[str] = mapped_column(
        String(20), nullable=False, default="dark", server_default="dark"
    )


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "admin", "editor", "viewer", "device"
    device_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    device: Mapped["Device | None"] = relationship()
    user: Mapped["User | None"] = relationship()


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    playlist_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(
        String(20), nullable=False  # "device", "group", or "all"
    )
    target_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True  # device or group id; null when target_type="all"
    )
    start_time: Mapped[str | None] = mapped_column(
        String(5), nullable=True  # "HH:MM" (24h) — null means all day
    )
    end_time: Mapped[str | None] = mapped_column(
        String(5), nullable=True  # "HH:MM" (24h) — null means all day
    )
    days_of_week: Mapped[str | None] = mapped_column(
        String(20), nullable=True  # comma-separated: "0,1,2,3,4,5,6" (Mon=0..Sun=6); null means every day
    )
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    recurrence_rule: Mapped[str | None] = mapped_column(String(500), nullable=True)
    priority_weight: Mapped[float] = mapped_column(Float, default=1.0)
    transition_playlist_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("playlists.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    playlist: Mapped["Playlist"] = relationship(foreign_keys=[playlist_id])
    transition_playlist: Mapped["Playlist | None"] = relationship(foreign_keys=[transition_playlist_id])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        index=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    user: Mapped["User | None"] = relationship()


class Override(Base):
    __tablename__ = "overrides"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(20), nullable=False  # "message" or "playlist"
    )
    content: Mapped[str] = mapped_column(
        String(4096), nullable=False  # text message or playlist_id
    )
    target_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="all"  # "all", "group", "device"
    )
    target_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True  # device or group id; null when target_type="all"
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    creator: Mapped["User | None"] = relationship()


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#7c83ff")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    asset_tags: Mapped[list["AssetTag"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )


class AssetTag(Base):
    __tablename__ = "asset_tags"

    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    asset: Mapped["Asset"] = relationship(overlaps="asset_tags")
    tag: Mapped["Tag"] = relationship(back_populates="asset_tags")


class PlaylistItem(Base):
    __tablename__ = "playlist_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    playlist_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    playlist: Mapped["Playlist"] = relationship(back_populates="items")
    asset: Mapped["Asset"] = relationship(back_populates="playlist_items")
