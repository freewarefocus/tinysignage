import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SchemaVersion(Base):
    __tablename__ = "schema_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    playlist_items: Mapped[list["PlaylistItem"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    transition_duration: Mapped[float] = mapped_column(Float, default=1.0)
    transition_type: Mapped[str] = mapped_column(String(20), default="fade")
    default_duration: Mapped[int] = mapped_column(Integer, default=10)
    shuffle: Mapped[bool] = mapped_column(Boolean, default=False)


class Device(Base):
    __tablename__ = "devices"
    # tenant_id: deferred until SaaS work begins

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Default Player")
    playlist_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("playlists.id"), nullable=True
    )
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="offline")
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    player_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    player_timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    clock_drift_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    registration_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    registration_expires: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    playlist: Mapped["Playlist | None"] = relationship(back_populates="devices")


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
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
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    memberships: Mapped[list["DeviceGroupMembership"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class DeviceGroupMembership(Base):
    __tablename__ = "device_group_memberships"

    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("devices.id"), primary_key=True
    )
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("device_groups.id"), primary_key=True
    )

    device: Mapped["Device"] = relationship()
    group: Mapped["DeviceGroup"] = relationship(back_populates="memberships")


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "admin" or "device"
    device_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("devices.id"), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    device: Mapped["Device | None"] = relationship()


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    playlist_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("playlists.id"), nullable=False
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
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    playlist: Mapped["Playlist"] = relationship()


class PlaylistItem(Base):
    __tablename__ = "playlist_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    playlist_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("playlists.id"), nullable=False
    )
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assets.id"), nullable=False
    )
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    playlist: Mapped["Playlist"] = relationship(back_populates="items")
    asset: Mapped["Asset"] = relationship(back_populates="playlist_items")
