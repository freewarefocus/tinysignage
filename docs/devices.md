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

In the CMS, go to **Devices** and click **Add Device**. Enter a name for the device (e.g., "Lobby TV", "Menu Board").

A 6-character pairing code is generated. This code expires in 10 minutes.

## Pairing flow

1. Open `http://your-server:8080/player` on the device's browser
2. The player shows a pairing code entry form (since it has no stored token)
3. Enter the 6-character code from the CMS
4. The player exchanges the code for a device token via `POST /api/devices/register`
5. The token is stored in the browser's localStorage
6. The player immediately begins polling and displaying content

After pairing, the device appears as "online" in the CMS within 60 seconds.

### Re-pairing

If a device loses its token (browser data cleared), generate a new pairing code from the CMS device page and pair again.

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
