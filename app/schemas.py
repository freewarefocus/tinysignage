"""Pydantic request/response schemas for all models."""

from datetime import datetime

from pydantic import BaseModel


# --- Asset ---

class AssetOut(BaseModel):
    id: str
    name: str
    asset_type: str
    uri: str
    duration: int
    play_order: int
    is_enabled: bool
    start_date: datetime | None = None
    end_date: datetime | None = None
    mimetype: str | None = None
    file_size: int | None = None
    thumbnail_path: str | None = None
    content_hash: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AssetUpdate(BaseModel):
    name: str | None = None
    duration: int | None = None
    is_enabled: bool | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    play_order: int | None = None


# --- Playlist ---

class PlaylistItemOut(BaseModel):
    id: str
    playlist_id: str
    asset_id: str
    order: int
    asset: AssetOut | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PlaylistOut(BaseModel):
    id: str
    name: str
    is_default: bool
    items: list[PlaylistItemOut] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PlaylistCreate(BaseModel):
    name: str


class PlaylistUpdate(BaseModel):
    name: str | None = None


class PlaylistItemAdd(BaseModel):
    asset_id: str
    order: int | None = None


class PlaylistReorder(BaseModel):
    item_ids: list[str]


# --- Device ---

class DeviceOut(BaseModel):
    id: str
    name: str
    playlist_id: str | None = None
    last_seen: datetime | None = None
    ip_address: str | None = None
    status: str
    player_type: str | None = None
    resolution_detected: str | None = None
    ram_mb: int | None = None
    storage_total_mb: int | None = None
    storage_free_mb: int | None = None
    capabilities_updated_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class DeviceUpdate(BaseModel):
    name: str | None = None
    playlist_id: str | None = None


# --- Settings ---

class SettingsOut(BaseModel):
    transition_duration: float
    transition_type: str
    default_duration: int
    shuffle: bool

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    transition_duration: float | None = None
    transition_type: str | None = None
    default_duration: int | None = None
    shuffle: bool | None = None
