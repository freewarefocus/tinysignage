# Managing Media

Media assets are the content that displays on your screens. TinySignage supports images, videos, web URLs, HTML snippets, and visually designed Custom Slides.

---

## Supported types

| Type | Formats | Notes |
|------|---------|-------|
| **Image** | JPG, PNG, WebP, GIF | Auto-generated thumbnails |
| **Video** | MP4, WebM | Thumbnails require FFmpeg |
| **Web URL** | Any URL | Embedded as an iframe |
| **HTML snippet** | Raw HTML | Up to 64KB, rendered inline |
| **Custom Slide** | Designed in the [Page Designer](page-designer.md) | Visual editor -- text, images, shapes, live widgets |

## Uploading media

Open the CMS and click **Media** in the sidebar. Drag files onto the upload zone or click to browse. Multiple files can be uploaded at once -- each shows a progress bar.

Uploaded files are stored in the `media/` directory. Thumbnails are auto-generated in `media/thumbs/`.

New uploads are automatically added to the default playlist. You can remove them from the default playlist or add them to other playlists later.

### Web URLs

Click **Add URL** and enter a web address. The URL is embedded as an iframe in the player. This works for any publicly accessible web page, dashboard, or web app.

### Custom Slides (Page Designer)

For announcements, event posters, lower thirds, live clocks, and other branded one-off content, use the **Page Designer** instead of writing HTML by hand. Click **Add Custom Slide** (the palette icon at the top of the Media page) or open **Designer** in the sidebar to launch the visual editor.

Custom Slides support text, images, shapes, and live widgets (clock, weather, countdown, scrolling text, and more). They scale automatically to any screen size and can be edited any number of times after saving.

See the [Page Designer](page-designer.md) guide for a full walkthrough.

### HTML snippets (raw editor)

For power users, **Add HTML** still exists as an escape hatch. Paste or type raw HTML (up to 64KB) and it's rendered directly in the player. This is useful when you have a hand-written snippet or need CSS that the visual designer doesn't expose. Slides created this way can only be edited in the raw HTML editor -- they don't open in the Page Designer.

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

## Live widgets

TinySignage includes built-in live widgets that update in real time on the player:

| Widget | Description |
|--------|-------------|
| **Clock** | Live digital clock, configurable 12/24h, seconds, timezone, font, color |
| **Date** | Current date with format and locale options |
| **Weather** | Current temperature from Open-Meteo (free, no API key) |
| **Centered Text** | Static centered message with configurable size and weight |
| **Heading + Subtitle** | Two-line heading + subtitle pair |
| **Scrolling Text** | Smooth horizontal marquee text |
| **Countdown** | Live countdown to a target date and time |

The easiest way to use widgets is to drop them onto a slide in the [Page Designer](page-designer.md) -- you get a visual property panel for each widget's settings, and you can mix widgets with text, images, and shapes on the same slide.

Widgets are also available through the API (`GET /api/widgets` lists every widget with its parameters and default HTML) for scripted asset creation.

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

- [Page Designer](page-designer.md) -- Visual editor for Custom Slides
- [Playlists](playlists.md) -- Organizing media into playlists
- [Multi-Zone Layouts](multi-zone-layouts.md) -- Displaying different content in screen regions
- [Configuration](configuration.md) -- Storage settings
- [API Reference](api-reference.md) -- Asset and tag endpoints
