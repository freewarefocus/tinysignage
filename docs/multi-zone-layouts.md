# Multi-Zone Layouts

Layouts let you split a screen into multiple zones, each showing independent content. A lobby screen could show a main content area, a scrolling ticker, and a sidebar with a clock -- all running simultaneously.

---

## Zone types

| Type | Typical use |
|------|------------|
| **main** | Primary content area (largest zone) |
| **ticker** | Scrolling text or narrow content strip |
| **sidebar** | Side panel for secondary content |
| **pip** | Picture-in-picture overlay |

Zone types are labels for organizational purposes. All zones are positioned the same way -- the type does not affect rendering behavior.

---

## Creating a layout

In the CMS, go to **Layouts** and click **New Layout**. Enter a name and optional description.

A layout starts empty. Add zones to define the screen regions.

## Adding zones

Click **Add Zone** in the layout editor. Each zone has:

| Property | Description | Default |
|----------|-------------|---------|
| **Name** | Descriptive label (e.g., "Main Content", "Bottom Ticker") | Required |
| **Type** | `main`, `ticker`, `sidebar`, or `pip` | `main` |
| **X position** | Horizontal offset as percentage of screen width | `0.0` |
| **Y position** | Vertical offset as percentage of screen height | `0.0` |
| **Width** | Zone width as percentage of screen width | `100.0` |
| **Height** | Zone height as percentage of screen height | `100.0` |
| **Z-index** | Stacking order (higher = on top) | `0` |
| **Playlist** | Content to play in this zone | None |

All positioning uses percentages, so layouts scale to any screen resolution.

---

## Per-zone playlists

Each zone has its own playlist assignment. Zones operate independently -- each has its own playback timer, its own dual-layer crossfade engine, and advances through its playlist at its own pace.

This means you can have a main zone cycling through images every 10 seconds while a ticker zone cycles through announcements every 30 seconds.

---

## Assigning a layout to a device

In the CMS, edit a device and set its **Layout**. When a device has a layout assigned, the player renders all zones instead of displaying a single fullscreen playlist.

If the device also has a playlist assigned, the layout takes precedence. The device's assigned playlist is used as a fallback only if the layout has no zones or no zone playlists.

---

## Player rendering

When the player receives a multi-zone payload:

1. Each zone is rendered as an absolutely-positioned container using percentage-based CSS
2. Zones are stacked according to z-index
3. Each zone runs its own instance of the dual-layer crossfade engine
4. Each zone has its own independent playback timer
5. Zones do not interfere with each other -- one zone loading a video does not pause another zone's transitions

---

## Common layout patterns

### Main content with bottom ticker

| Zone | X | Y | Width | Height | Type |
|------|---|---|-------|--------|------|
| Main | 0 | 0 | 100 | 85 | main |
| Ticker | 0 | 85 | 100 | 15 | ticker |

### Main content with sidebar

| Zone | X | Y | Width | Height | Type |
|------|---|---|-------|--------|------|
| Main | 0 | 0 | 75 | 100 | main |
| Sidebar | 75 | 0 | 25 | 100 | sidebar |

### Three-zone (main, sidebar, ticker)

| Zone | X | Y | Width | Height | Type |
|------|---|---|-------|--------|------|
| Main | 0 | 0 | 75 | 85 | main |
| Sidebar | 75 | 0 | 25 | 85 | sidebar |
| Ticker | 0 | 85 | 100 | 15 | ticker |

### Picture-in-picture

| Zone | X | Y | Width | Height | Z-index | Type |
|------|---|---|-------|--------|---------|------|
| Background | 0 | 0 | 100 | 100 | 0 | main |
| PiP | 70 | 5 | 25 | 25 | 1 | pip |

---

## See also

- [Playlists](playlists.md) -- Creating content for zones
- [Devices](devices.md) -- Assigning layouts to devices
- [Player Behavior](player-behavior.md) -- Multi-zone rendering details
- [API Reference](api-reference.md) -- Layout and zone endpoints
