# API Reference

All TinySignage API endpoints. The API is served at `/api/*` and requires Bearer token authentication unless marked as public.

Authentication: include `Authorization: Bearer YOUR_TOKEN` in the request header. See [Users and Permissions](users-and-permissions.md) for token details.

---

## Assets

Manage media assets (images, videos, URLs, HTML snippets).

### List assets

```
GET /api/assets
Auth: viewer
```

Returns all assets. Filterable by tag.

Query parameters:
- `tag_id` (string, optional) -- filter by tag ID

Response: array of asset objects with `id`, `name`, `asset_type`, `uri`, `duration`, `play_order`, `is_enabled`, `mimetype`, `file_size`, `thumbnail_path`, `content_hash`, `transition_type`, `transition_duration`, `created_at`, `updated_at`.

### Create asset

```
POST /api/assets
Auth: editor
Content-Type: multipart/form-data (file upload) or application/json (URL/HTML)
```

Upload a file, add a URL, or create an HTML snippet (up to 64KB). New assets are auto-added to the default playlist.

Body (file upload): form field `file` with the media file, plus optional `name`, `duration`.

Body (URL): `{"name": "Dashboard", "asset_type": "url", "uri": "https://example.com"}`.

Body (HTML): `{"name": "Welcome", "asset_type": "html", "uri": "<h1>Welcome</h1>"}`.

### Get asset

```
GET /api/assets/{id}
Auth: viewer
```

### Get asset thumbnail

```
GET /api/assets/{id}/thumbnail
Auth: viewer
```

Returns the thumbnail image file.

### Get HTML content

```
GET /api/assets/{id}/content
Auth: viewer
```

Returns raw HTML content for HTML-type assets.

### Update asset

```
PATCH /api/assets/{id}
Auth: editor
```

Update asset fields including per-asset `transition_type` and `transition_duration`.

Body: `{"name": "New Name", "duration": 15, "transition_type": "cut", "transition_duration": 0.5}`.

### Replace asset file

```
PUT /api/assets/{id}/replace
Auth: editor
Content-Type: multipart/form-data
```

Replace the media file while keeping the asset's metadata and playlist positions.

### Duplicate asset

```
POST /api/assets/{id}/duplicate
Auth: editor
```

Creates a copy with "(copy)" appended to the name.

### Delete asset

```
DELETE /api/assets/{id}
Auth: editor
```

Deletes the asset, its media file, and its thumbnail.

### Reorder assets

```
POST /api/assets/reorder
Auth: editor
```

Bulk update asset play order.

Body: `{"order": [{"id": "asset-1", "play_order": 0}, {"id": "asset-2", "play_order": 1}]}`.

---

## Playlists

Manage playlists and their items.

### List playlists

```
GET /api/playlists
Auth: viewer
```

Returns all playlists with `item_count` and content `hash`.

### Create playlist

```
POST /api/playlists
Auth: editor
```

Body: `{"name": "Morning Rotation"}`.

### Get playlist

```
GET /api/playlists/{id}
Auth: viewer
```

Returns the playlist with nested items and their associated assets.

### Update playlist

```
PATCH /api/playlists/{id}
Auth: editor
```

Body: `{"name": "Renamed", "transition_type": "fade", "transition_duration": 1.5, "default_duration": 15, "shuffle": true}`.

### Delete playlist

```
DELETE /api/playlists/{id}
Auth: editor
```

Cannot delete the default playlist. Checks for references from devices, schedules, overrides, and zones.

### Get playlist hash

```
GET /api/playlists/{id}/hash
Auth: token
```

Returns the SHA-256 content hash. Used by the player for change detection.

### Add item to playlist

```
POST /api/playlists/{id}/items
Auth: editor
```

Body: `{"asset_id": "asset-uuid"}`.

### Remove item from playlist

```
DELETE /api/playlists/{id}/items/{item_id}
Auth: editor
```

### Reorder playlist items

```
POST /api/playlists/{id}/reorder
Auth: editor
```

Body: `{"order": [{"id": "item-1", "order": 0}, {"id": "item-2", "order": 1}]}`.

### Bulk pre-flight check

```
POST /api/playlists/{id}/preflight
Auth: viewer
```

Check playlist compatibility against multiple devices.

Body: `{"device_ids": ["device-1", "device-2"]}`.

---

## Devices

Manage devices, pairing, and polling.

### List devices

```
GET /api/devices
Auth: viewer
```

### Create device

```
POST /api/devices
Auth: admin
```

Creates a new device with an auto-generated pairing code (6-char, expires in 10 minutes).

Body: `{"name": "Lobby TV"}`.

### Get device

```
GET /api/devices/{id}
Auth: admin
```

### Update device

```
PATCH /api/devices/{id}
Auth: admin
```

Body: `{"name": "New Name", "playlist_id": "playlist-uuid", "layout_id": "layout-uuid"}`.

### Delete device

```
DELETE /api/devices/{id}
Auth: admin
```

Cascades to tokens and group memberships.

### Register device (public)

```
POST /api/devices/register
Auth: public
```

Exchange a pairing code for a device token. Called by the player during the pairing flow.

Body: `{"code": "ABC123"}`.

Response: `{"token": "ts_...", "device_id": "uuid"}`.

### Generate pairing code

```
POST /api/devices/{id}/pairing-code
Auth: admin
```

Generates a new 6-character pairing code (expires in 10 minutes).

### Get device playlist (polling endpoint)

```
GET /api/devices/{id}/playlist
Auth: device
```

Primary player endpoint. Returns playlist hash, items, display settings, active overrides, and multi-zone layout payload.

The player calls this every 30 seconds.

### Pre-flight check

```
GET /api/devices/{id}/preflight
Auth: viewer
```

Advisory compatibility check before playlist assignment.

---

## Device Groups

Manage device groups and membership.

### List groups

```
GET /api/groups
Auth: viewer
```

### Create group

```
POST /api/groups
Auth: admin
```

Body: `{"name": "Lobby Screens", "description": "All screens in the main lobby"}`.

### Get group

```
GET /api/groups/{id}
Auth: viewer
```

Returns group with member devices.

### Update group

```
PATCH /api/groups/{id}
Auth: admin
```

Body: `{"name": "Updated Name", "description": "Updated description"}`.

### Delete group

```
DELETE /api/groups/{id}
Auth: admin
```

Deletes the group and all memberships. Does not delete devices.

### Add device to group

```
POST /api/groups/{id}/members
Auth: admin
```

Body: `{"device_id": "device-uuid"}`.

### Remove device from group

```
DELETE /api/groups/{id}/members/{device_id}
Auth: admin
```

### Bulk assign playlist to group

```
POST /api/groups/{id}/assign-playlist
Auth: admin
```

Assigns a playlist to all devices in the group.

Body: `{"playlist_id": "playlist-uuid"}`.

---

## Schedules

Time-based playlist switching.

### List schedules

```
GET /api/schedules
Auth: viewer
```

### Create schedule

```
POST /api/schedules
Auth: editor
```

Body:
```json
{
  "name": "Weekday Business Hours",
  "playlist_id": "playlist-uuid",
  "target_type": "all",
  "start_time": "09:00",
  "end_time": "17:00",
  "days_of_week": "0,1,2,3,4",
  "priority": 1,
  "recurrence_rule": "FREQ=WEEKLY",
  "transition_playlist_id": "bumper-playlist-uuid"
}
```

Fields: `name`, `playlist_id`, `target_type` (`device`/`group`/`all`), `target_id` (if device or group), `start_time`, `end_time`, `days_of_week`, `start_date`, `end_date`, `priority`, `recurrence_rule`, `priority_weight`, `transition_playlist_id`, `is_active`.

### Get schedule

```
GET /api/schedules/{id}
Auth: viewer
```

### Update schedule

```
PATCH /api/schedules/{id}
Auth: editor
```

### Delete schedule

```
DELETE /api/schedules/{id}
Auth: editor
```

### Timeline preview

```
GET /api/schedules/preview/timeline
Auth: viewer
```

Returns 48 half-hour time slots showing which playlist plays on a given device for a given date.

Query parameters:
- `device_id` (string, required)
- `date` (string, optional, YYYY-MM-DD format, defaults to today)

---

## Layouts and Zones

Multi-zone screen layouts.

### List layouts

```
GET /api/layouts
Auth: viewer
```

Returns all layouts with zone counts.

### Create layout

```
POST /api/layouts
Auth: editor
```

Body: `{"name": "Lobby Layout", "description": "Main content with bottom ticker"}`.

### Get layout

```
GET /api/layouts/{id}
Auth: viewer
```

Returns layout with all zones.

### Update layout

```
PATCH /api/layouts/{id}
Auth: editor
```

Body: `{"name": "Updated Name", "description": "Updated description"}`.

### Delete layout

```
DELETE /api/layouts/{id}
Auth: editor
```

### List zones

```
GET /api/layouts/{id}/zones
Auth: viewer
```

### Create zone

```
POST /api/layouts/{id}/zones
Auth: editor
```

Body:
```json
{
  "name": "Main Content",
  "zone_type": "main",
  "x_percent": 0.0,
  "y_percent": 0.0,
  "width_percent": 75.0,
  "height_percent": 100.0,
  "z_index": 0,
  "playlist_id": "playlist-uuid"
}
```

### Update zone

```
PATCH /api/layouts/{id}/zones/{zone_id}
Auth: editor
```

### Delete zone

```
DELETE /api/layouts/{id}/zones/{zone_id}
Auth: editor
```

---

## Widgets

Built-in widget templates.

### List widget templates

```
GET /api/widgets
Auth: viewer
```

Returns available widget templates (clock, date, weather) with parameterized HTML defaults. Use the returned HTML to create HTML-type assets.

---

## Emergency Overrides

Admin-only emergency content push.

### List overrides

```
GET /api/overrides
Auth: admin
```

### Create override

```
POST /api/overrides
Auth: admin
```

Body:
```json
{
  "name": "Fire Drill Notice",
  "content_type": "message",
  "content": "Fire drill in progress. Please proceed to exits.",
  "target_type": "all",
  "expires_at": "2026-03-29T15:00:00"
}
```

For playlist overrides, set `content_type` to `"playlist"` and `content` to the playlist ID.

Target options: `target_type` (`all`/`group`/`device`), `target_id` (required if group or device).

### Get override

```
GET /api/overrides/{id}
Auth: admin
```

### Update override

```
PATCH /api/overrides/{id}
Auth: admin
```

Body: `{"name": "Updated", "is_active": false, "expires_at": "2026-03-30T12:00:00"}`.

### Delete override

```
DELETE /api/overrides/{id}
Auth: admin
```

---

## Tags

Media organization tags.

### List tags

```
GET /api/tags
Auth: viewer
```

Returns all tags with asset counts.

### Create tag

```
POST /api/tags
Auth: editor
```

Body: `{"name": "Holiday", "color": "#ff5733"}`.

### Update tag

```
PATCH /api/tags/{id}
Auth: editor
```

Body: `{"name": "Renamed", "color": "#33ff57"}`.

### Delete tag

```
DELETE /api/tags/{id}
Auth: editor
```

### Add tag to asset

```
POST /api/assets/{id}/tags
Auth: editor
```

Body: `{"tag_id": "tag-uuid"}`.

### Remove tag from asset

```
DELETE /api/assets/{id}/tags/{tag_id}
Auth: editor
```

### Get asset tags

```
GET /api/assets/{id}/tags
Auth: viewer
```

---

## Users and Auth

User management and authentication.

### Login

```
POST /api/auth/login
Auth: public
```

Body: `{"username": "admin", "password": "yourpassword"}`.

Response: `{"token": "ts_...", "user": {"id": "...", "username": "admin", "role": "admin"}}`.

The token expires after 30 days.

### Logout

```
POST /api/auth/logout
Auth: token
```

Invalidates the current session token.

### Get current user

```
GET /api/auth/me
Auth: token
```

Returns the authenticated user's profile.

### List users

```
GET /api/users
Auth: admin
```

### Create user

```
POST /api/users
Auth: admin
```

Body: `{"username": "editor1", "display_name": "Content Editor", "password": "securepass", "role": "editor"}`.

### Update user

```
PUT /api/users/{id}
Auth: admin
```

Body: `{"display_name": "New Name", "role": "admin", "is_active": true, "password": "newpass"}`.

### Delete user

```
DELETE /api/users/{id}
Auth: admin
```

Protected against deleting the last admin account.

### Get preferences

```
GET /api/users/me/preferences
Auth: token
```

Returns theme preference (`dark` or `light`).

### Update preferences

```
PATCH /api/users/me/preferences
Auth: token
```

Body: `{"theme_preference": "light"}`.

---

## Audit Log

Admin-only audit trail.

### Query audit log

```
GET /api/audit
Auth: admin
```

Query parameters:
- `action` (string, optional) -- filter by action type
- `entity_type` (string, optional) -- filter by entity type
- `user_id` (string, optional) -- filter by user
- `limit` (integer, optional) -- page size
- `offset` (integer, optional) -- pagination offset

### List distinct actions

```
GET /api/audit/actions
Auth: admin
```

Returns distinct `action` and `entity_type` values for filter dropdowns.

---

## API Tokens

Admin-only token management.

### Create token

```
POST /api/tokens
Auth: admin
```

Body: `{"name": "CI Pipeline", "role": "editor", "expires_at": "2027-01-01T00:00:00"}`.

Response includes the plaintext token (shown only once).

### List tokens

```
GET /api/tokens
Auth: admin
```

Returns all tokens with masked values (the plaintext is never stored or returned after creation).

### Revoke token

```
DELETE /api/tokens/{id}
Auth: admin
```

Immediately deactivates the token.

---

## Backup

Admin-only backup and restore.

### Export backup

```
GET /api/backup/export
Auth: admin
```

Returns a ZIP file containing the database and all media files.

### Import backup

```
POST /api/backup/import
Auth: admin
Content-Type: multipart/form-data
```

Upload a backup ZIP to restore. Replaces the current database and media.

---

## Health and Monitoring

### Health check (public)

```
GET /api/health
Auth: public
```

Response: `{"status": "ok"}`.

### Player heartbeat

```
POST /api/player/heartbeat
Auth: device
```

Body: `{"player_time": "2026-03-29T12:00:00Z", "timezone": "America/New_York", "version": "1.0", "storage_free_mb": 2048}`.

### Report capabilities

```
POST /api/devices/{id}/capabilities
Auth: device
```

Body: hardware and software profile (screen resolution, RAM, CPU cores, touch, audio, storage quota). Supported fields are promoted to device columns; the full report is stored as a JSON blob.

### Health dashboard

```
GET /api/health/dashboard
Auth: viewer
```

Returns per-device health signals: heartbeat status, storage, resolution, RAM. Signals are color-coded (green/yellow/red).

---

## Settings and Control

### Get settings

```
GET /api/settings
Auth: viewer
```

Returns global display settings (transition type, duration, default duration, shuffle).

### Update settings

```
PATCH /api/settings
Auth: admin
```

Body: `{"transition_type": "slide", "transition_duration": 2.0, "default_duration": 15, "shuffle": true}`.

### Get playback status

```
GET /api/status
Auth: viewer
```

### Skip to next

```
POST /api/control/next
Auth: admin
```

### Skip to previous

```
POST /api/control/previous
Auth: admin
```

### Jump to asset

```
POST /api/control/asset/{id}
Auth: admin
```

---

## Storage

### Storage dashboard

```
GET /api/storage
Auth: viewer
```

Returns disk usage summary and per-asset file size breakdown.

---

## System Logs

### Read error log

```
GET /api/logs/errors
Auth: admin
```

Returns error log entries with pagination and filtering.

### Clear error log

```
DELETE /api/logs/errors
Auth: admin
```

---

## Setup

### Setup wizard page

```
GET /setup
Auth: public
```

Serves the first-boot setup HTML form. Redirects to `/cms` if setup is already complete.

### Complete setup

```
POST /api/setup
Auth: public
```

Creates the admin user, default device, and setup marker. Only works if setup has not been completed.

Body: `{"device_name": "My Display", "username": "admin", "password": "yourpassword"}`.

---

## Static pages

These are not API endpoints but are served by the application:

| Path | Description |
|------|-------------|
| `/` | Redirects to `/setup` (first boot) or `/cms` |
| `/player` | Player HTML page (server_url meta tag injected) |
| `/admin` | Redirects to `/cms` |
| `/cms` | Vue CMS app |
| `/media/{filename}` | Media files (Cache-Control: public, max-age=86400, immutable) |
| `/static/{path}` | Static frontend assets |

---

## See also

- [Users and Permissions](users-and-permissions.md) -- Roles and token management
- [Architecture](architecture.md) -- System design overview
- [Player Behavior](player-behavior.md) -- How the player uses the API
- [Contributing](../CONTRIBUTING.md) -- Adding new endpoints
