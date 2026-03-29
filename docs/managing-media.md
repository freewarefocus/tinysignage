# Managing Media

Media assets are the content that displays on your screens. TinySignage supports images, videos, web URLs, and HTML snippets.

---

## Supported types

| Type | Formats | Notes |
|------|---------|-------|
| **Image** | JPG, PNG, WebP, GIF | Auto-generated thumbnails |
| **Video** | MP4, WebM | Thumbnails require FFmpeg |
| **Web URL** | Any URL | Embedded as an iframe |
| **HTML snippet** | Raw HTML | Up to 64KB, rendered inline |

## Uploading media

Open the CMS and click **Media** in the sidebar. Drag files onto the upload zone or click to browse. Multiple files can be uploaded at once -- each shows a progress bar.

Uploaded files are stored in the `media/` directory. Thumbnails are auto-generated in `media/thumbs/`.

New uploads are automatically added to the default playlist. You can remove them from the default playlist or add them to other playlists later.

### Web URLs

Click **Add URL** and enter a web address. The URL is embedded as an iframe in the player. This works for any publicly accessible web page, dashboard, or web app.

### HTML snippets

Click **Add HTML** and paste or type HTML content (up to 64KB). The HTML is rendered directly in the player. Use this for custom messages, styled announcements, or any content you want to build by hand.

---

## Media library

The media library shows all assets as a thumbnail grid. Each card displays the asset name, type, and duration.

### Filtering by tags

Use the tag filter above the grid to show only assets with specific tags. Tags are color-coded for quick visual identification.

### Sorting

Assets display in their play order by default. The play order can be changed by dragging assets or using the reorder endpoint.

---

## Tags

Tags let you organize and filter media assets. Each tag has a name and a color.

### Creating tags

In the media library, click the tag management area to create a new tag. Enter a name and pick a hex color (e.g., `#7c83ff`).

### Tagging assets

Select an asset and add tags from the tag picker. An asset can have multiple tags. Tags are purely organizational -- they do not affect playback.

### Filtering

Click a tag in the filter bar to show only assets with that tag. This is useful when you have many assets and want to find content for a specific purpose (e.g., "holiday", "menu", "promotions").

---

## Widget templates

TinySignage includes built-in widget templates that generate HTML assets:

| Widget | Description |
|--------|-------------|
| **Clock** | Digital clock display with configurable format |
| **Date** | Date display with configurable format |
| **Weather** | Weather display (requires configuration) |

Widgets are created through the API (`GET /api/widgets` lists available templates with default HTML). Each widget is an HTML asset that you can customize after creation.

---

## Per-asset transition overrides

Each asset can have its own transition type and duration that override the playlist and global settings.

Edit an asset and set:
- **Transition type** -- `fade`, `slide`, or `cut`
- **Transition duration** -- seconds (e.g., `0.5` for a quick cut, `2.0` for a slow fade)

When the player reaches this asset, it uses the asset-level transition instead of the playlist or global default.

---

## Replace and duplicate

### Replace

To update an asset without changing its position in playlists, use **Replace**. Upload a new file and it replaces the existing one while keeping the same asset ID, name, and playlist slots.

### Duplicate

**Duplicate** creates a copy of an asset with "(copy)" appended to the name. The new asset gets its own ID and can be edited independently. Useful when you want a variation of an existing asset.

---

## Storage monitoring

The storage dashboard (`/storage` in the CMS, or `GET /api/storage`) shows:

- Total disk usage for all media files
- Per-asset file size breakdown
- Storage warning threshold (configurable in `config.yaml` as `storage.warning_threshold_mb`, default 500MB)

---

## See also

- [Playlists](playlists.md) -- Organizing media into playlists
- [Multi-Zone Layouts](multi-zone-layouts.md) -- Displaying different content in screen regions
- [Configuration](configuration.md) -- Storage settings
- [API Reference](api-reference.md) -- Asset and tag endpoints
