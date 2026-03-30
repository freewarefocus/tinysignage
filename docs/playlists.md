# Playlists

Playlists define the sequence of content that plays on a device. Each playlist contains an ordered list of media assets with configurable timing and transitions.

---

## What playlists are

A playlist is an ordered collection of media assets. Each device plays one playlist at a time (unless using multi-zone layouts, where each zone has its own playlist). Schedules can switch which playlist a device plays based on time.

A **default playlist** is created during setup. New uploads are automatically added to it. You can rename it, but it cannot be deleted.

---

## Creating a playlist

In the CMS, click **Playlists** in the sidebar, then **New Playlist**. Enter a name and click create.

You now have an empty playlist. Click into it to start adding media.

## Adding media

In the playlist editor, click **Add Media**. Select one or more assets from the media library. They are appended to the end of the playlist.

Each item in the playlist shows a thumbnail, name, type, and duration.

## Reordering

Drag items up and down to change their play order. The player follows this exact order (unless shuffle is enabled).

## Removing items

Click the remove button on a playlist item to remove it from the playlist. This does not delete the underlying media asset -- it only removes it from this playlist. The same asset can exist in multiple playlists.

---

## Per-item duration

Each playlist item inherits the global default duration (configured in Settings, default 10 seconds). To override for a specific item, edit the asset's duration.

Videos with duration set to `0` play to their natural end (capped at 300 seconds as a safety limit).

---

## Per-playlist settings

Each playlist can override global display settings:

| Setting | Description | Default |
|---------|-------------|---------|
| **Transition type** | `fade`, `slide`, or `cut` | Inherits from global settings |
| **Transition duration** | Seconds for the transition | Inherits from global settings |
| **Default duration** | Seconds per image/URL | Inherits from global settings |
| **Shuffle** | Randomize play order | Off |

When set on a playlist, these override the global settings for any device playing that playlist. Per-asset transition overrides take precedence over per-playlist settings.

---

## Mini preview

The playlist editor includes a mini preview player that cycles through the playlist items in the browser. Use it to verify content order and transitions without opening the fullscreen player.

---

## Content hash

Each playlist has a content hash (SHA-256) that changes when items are added, removed, or reordered. The player uses this hash to detect changes efficiently -- it polls every 30 seconds, compares the hash, and only downloads the full playlist when something changed.

---

## Deleting a playlist

You can delete any playlist except the default playlist. Before deletion, TinySignage checks for references from devices, schedules, overrides, and layout zones. If the playlist is in use, you must reassign those references first.

---

## Simple and advanced mode

Each playlist has a mode: **simple** (default) or **advanced**.

- **Simple** playlists work exactly as described above -- a linear sequence of assets
- **Advanced** playlists can have an interactive TriggerFlow assigned, enabling trigger-driven transitions between playlists

To make a playlist advanced, open it in the editor and click **Make Advanced**. This reveals the trigger configuration panel where you can assign a TriggerFlow and define branches. To revert, click **Simplify** (with confirmation if branches exist).

Advanced playlists show a purple "Advanced" badge in the playlist list.

See [Interactive Triggers](interactive-triggers.md) for the full trigger system documentation.

---

## See also

- [Managing Media](managing-media.md) -- Uploading and organizing assets
- [Devices](devices.md) -- Assigning playlists to devices
- [Scheduling](scheduling.md) -- Time-based playlist switching
- [Multi-Zone Layouts](multi-zone-layouts.md) -- Per-zone playlists
- [Interactive Triggers](interactive-triggers.md) -- Trigger-driven playlist transitions
- [API Reference](api-reference.md) -- Playlist endpoints
