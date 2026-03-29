# Player Behavior

The TinySignage player is a static HTML page (`/player`) that runs entirely in the browser. It manages its own playback, caches content locally, and communicates with the server through polling.

---

## Polling model

The player communicates with the server on three intervals:

| Action | Interval | Endpoint |
|--------|----------|----------|
| **Playlist poll** | Every 30 seconds | `GET /api/devices/{id}/playlist` |
| **Heartbeat** | Every 60 seconds | `POST /api/player/heartbeat` |
| **Capability report** | On boot + every 60 minutes | `POST /api/devices/{id}/capabilities` |

### Playlist polling

Every 30 seconds, the player fetches the current playlist from the server. The response includes a content hash. If the hash matches what the player already has, no further processing occurs. If the hash changed, the player downloads the new playlist data and transitions to the updated content at the next item boundary.

This means changes made in the CMS take effect within 30 seconds on all players.

### Heartbeat

Every 60 seconds, the player sends a heartbeat with diagnostics:

- Current time (for clock drift detection)
- Timezone
- Player version
- Uptime
- Free storage (when available)

The server uses heartbeats to determine device status. A device with no heartbeat for 120+ seconds is marked offline.

### Capability reporting

On boot (after pairing) and every 60 minutes, the player reports hardware and software capabilities:

- Screen resolution
- RAM (via `navigator.deviceMemory`)
- CPU cores
- Touch support
- Audio support
- Browser storage quota

Browser players cannot detect GPIO, MAC address, device model, or real disk space. Those fields remain null and are shown as "unknown" in the health dashboard.

---

## Hash-based change detection

The server computes a SHA-256 hash of the playlist contents (items, order, settings). The player stores the last-known hash and compares it on each poll. This minimizes bandwidth -- most polls result in no data transfer beyond the hash comparison.

---

## Offline resilience

The player is designed to keep running indefinitely without a network connection.

### localStorage cache

The current playlist JSON is cached in `localStorage`. If the server is unreachable on the next poll, the player continues playing from its cached playlist. When connectivity returns, it resumes polling and picks up any changes.

### Browser HTTP cache

Media files (images, videos) are served with `Cache-Control: public, max-age=86400, immutable` headers. The browser caches them locally. Even if the server goes down, previously loaded media continues to display.

### No reconnect logic needed

Because the player polls on a fixed interval, there is no WebSocket to reconnect, no state to synchronize, and no persistent connection to maintain. The player simply keeps trying every 30 seconds. When the server comes back, it works.

---

## Transitions

### Dual-layer crossfade

The player uses two absolutely-positioned layers (`layer-a` and `layer-b`) that alternate. When advancing to the next item:

1. The next item is loaded into the hidden layer
2. The hidden layer fades in via CSS opacity transition (GPU-composited)
3. The previously visible layer fades out

This produces smooth crossfade transitions without flicker or blank frames.

### Transition settings priority

1. Per-asset transition overrides (highest)
2. Per-playlist transition settings
3. Global settings from CMS
4. config.yaml display defaults (lowest)

### Transition types

| Type | Behavior |
|------|----------|
| `fade` | Crossfade between layers |
| `slide` | Slide transition |
| `cut` | Instant switch, no animation |

---

## Video handling

Videos play in the visible layer with their native duration. When a video ends (fires the `onended` event), the player advances to the next item immediately -- it does not wait for the 30-second poll.

Videos with duration set to `0` in the database play to their natural end, capped at 300 seconds as a safety limit.

---

## Multi-zone rendering

When a device has a layout assigned, the player receives a multi-zone payload and renders each zone as an independent region:

- Each zone is an absolutely-positioned `<div>` using percentage-based CSS (`left`, `top`, `width`, `height`)
- Zones are stacked by `z-index`
- Each zone has its own dual-layer crossfade engine
- Each zone has its own playback timer and advances independently
- One zone loading or transitioning does not affect other zones

---

## Device pairing flow

On first boot (no stored device token in localStorage):

1. The player shows a pairing code entry form
2. The user enters the 6-character code displayed in the CMS
3. The player submits the code to `POST /api/devices/register`
4. The server validates the code (SHA-256 hash match, not expired)
5. The server returns a device token (`ts_` prefix, role `device`)
6. The player stores the token in localStorage and begins polling

---

## Split deployment

The player reads a `server_url` from a `<meta name="server-url">` tag injected by the backend. When set (via `server_url` in `config.yaml`), all API calls and media URLs use this as the base URL instead of the current origin.

This enables running the server on one machine and the player on another, even across different networks.

---

## Emergency override display

On every poll, the server includes any active override targeting this device. When an override is active:

- **Message overrides** display text on a full-screen styled overlay
- **Playlist overrides** replace the current content with the override playlist

The player schedules a client-side timeout to clear the override at its exact expiry time (if set), ensuring precise transition back to normal content.

---

## Status indicator

A small colored dot in the corner of the player screen indicates connection status:

- **Green** -- connected, polling successfully
- **Red** -- offline, playing from cache

---

## See also

- [Devices](devices.md) -- Pairing and health monitoring
- [Multi-Zone Layouts](multi-zone-layouts.md) -- Layout configuration
- [Emergency Overrides](emergency-overrides.md) -- Override behavior
- [Configuration](configuration.md) -- Display and player settings
- [Troubleshooting](troubleshooting.md) -- Player issues
