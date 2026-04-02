# Devices

Devices are the screens that display your content. Each device is a browser running the TinySignage player, paired to your server and assigned a playlist.

---

## How devices work

A device is any browser that opens the `/player` page and pairs with the server. Once paired, the device:

1. Polls for playlist changes every 30 seconds
2. Sends a heartbeat every 60 seconds with diagnostics
3. Reports hardware capabilities on boot and every 60 minutes

The server tracks each device's status, health signals, and assigned content.

---

## Adding a device

### Raspberry Pi (local install)

On a Pi running TinySignage locally, the player auto-pairs with the default device on first boot — no user interaction needed. The player calls `POST /api/player/bootstrap` (localhost-only), which creates a token for the seeded device from `config.yaml`. The device is immediately active.

### Remote / browser-based

1. Open `http://your-server:8080/player` on the device's browser
2. The player shows a registration form (since it has no stored token and bootstrap is not available)
3. Enter the server URL and a display name (e.g., "Lobby TV", "Menu Board")
4. The player submits the registration via `POST /api/devices/register`
5. The device appears as **pending** in the CMS Devices page
6. An admin approves the device in the CMS
7. The player begins polling and displaying content

## Registration flow

For local installs, the player auto-pairs via local bootstrap — no interaction needed. For remote players, the player registers itself and waits for admin approval. No shared keys or codes are needed -- the admin approval step is the security gate.

### Re-registering

If a device loses its token (browser data cleared) or was registered with the wrong server URL, reset it from the command line:

```bash
python launcher.py --reset
```

This deletes the browser profile and returns the player to the registration screen on next launch. See the [Raspberry Pi](install-raspberry-pi.md#resetting-the-player), [Windows](install-windows.md#resetting-the-player), or [macOS](install-macos.md#resetting-the-player) install guides for platform-specific steps. The old device entry can be deleted from the CMS.

---

## Device dashboard

The device list in the CMS shows each device with:

- **Name** and assigned playlist
- **Status** -- online (green), offline (red), or unknown
- **Last seen** -- timestamp of last poll or heartbeat
- **IP address** -- reported by the polling endpoint

Click a device to see full details including hardware capabilities and health signals.

## Health monitoring

The health dashboard (`GET /api/health/dashboard`) surfaces per-device health signals:

| Signal | What it checks | Warning condition |
|--------|---------------|-------------------|
| **Heartbeat** | Last heartbeat time | No heartbeat for 120+ seconds |
| **Clock drift** | Difference between device and server time | Drift exceeds threshold |
| **Timezone** | Device timezone vs. server timezone | Mismatch |
| **Storage** | Free disk space on device | Below threshold |
| **Resolution** | Screen resolution | Reported for informational purposes |
| **RAM** | Available memory | Below threshold |

Health signals are displayed as colored dots: green (healthy), yellow (unknown/warning), red (problem).

### Capabilities

Devices report their hardware and software capabilities on boot and every 60 minutes:

- Screen resolution
- RAM (via `navigator.deviceMemory`)
- CPU cores
- Touch support
- Audio support
- Browser storage quota

Browser-based players cannot detect GPIO, MAC address, device model, or real disk space -- those fields remain unknown.

---

## Pre-flight checks

Before assigning a playlist to a device, the CMS runs pre-flight checks to identify potential issues (e.g., the playlist contains video but the device has limited RAM). Pre-flight results are advisory -- you can always click **Assign Anyway** to proceed.

Bulk pre-flight checks are available when assigning a playlist to multiple devices at once.

---

## Device groups

Groups let you manage multiple devices together.

### Creating a group

Go to **Groups** in the CMS and click **New Group**. Enter a name and optional description.

### Adding members

Open a group and add devices to it. A device can belong to multiple groups.

### Bulk assign

Assign a playlist to all devices in a group at once. This is faster than assigning devices one by one when you have many screens showing the same content.

Groups are also used as targets for schedules and emergency overrides -- you can push content to a group instead of individual devices.

---

## Split deployment

For setups where the player runs on a different machine than the server, configure `server_url` in `config.yaml`. The backend injects this URL into the player page as a `<meta>` tag, and the player uses it as the base URL for all API calls and media requests.

This lets you run the server on one machine and the player on another, even across different networks.

---

## See also

- [Playlists](playlists.md) -- Creating content to assign to devices
- [Scheduling](scheduling.md) -- Time-based playlist switching per device
- [Multi-Zone Layouts](multi-zone-layouts.md) -- Assigning layouts to devices
- [Emergency Overrides](emergency-overrides.md) -- Pushing urgent content to devices
- [Player Behavior](player-behavior.md) -- How the player communicates with the server
- [API Reference](api-reference.md) -- Device and group endpoints
