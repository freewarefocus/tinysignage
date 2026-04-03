# BrightSign Player Support (Experimental)

> **Status: Experimental.** This feature has not been tested on real BrightSign hardware. The autorun script and MRSS feed endpoint are functional but may require adjustments for specific BrightSign firmware versions. If you try this, please report your results.

TinySignage can manage BrightSign players alongside regular browser-based displays. BrightSign devices use a Chromium-based HTML widget, so the existing TinySignage player runs on them with no changes to your content or playlists.

There are two ways to connect a BrightSign device:

| Method | What it does | Feature parity |
|--------|-------------|----------------|
| **HTML Player** (recommended) | Runs the full TinySignage player inside BrightSign's HTML widget | Full -- schedules, overrides, triggers, multi-zone, heartbeats |
| **MRSS Feed** | BrightSign polls an RSS feed for media URLs | Limited -- image/video rotation only, no advanced features |

---

## Method 1: HTML Player on BrightSign

This is the recommended approach. The BrightSign device loads `player.js` in its built-in Chromium browser and behaves exactly like any other TinySignage player -- it auto-registers using the display name from config.json, polls for playlists, sends heartbeats, and renders content identically.

### Setup

1. In the TinySignage CMS, go to **Devices** and click **Download BrightSign Setup**
2. Extract the downloaded ZIP to the root of the BrightSign's SD card
3. The ZIP contains two files:
   - `autorun.brs` -- BrightScript that launches the HTML player
   - `config.json` -- pre-filled with your server's URL
4. Insert the SD card into the BrightSign player and power it on
5. The player will load, register with TinySignage, and appear in the CMS as a pending device
6. Approve the device in the CMS

### Manual setup

If you prefer to set up the files manually instead of using the setup bundle:

1. Copy `brightsign/autorun.brs` to the SD card root
2. Create `config.json` on the SD card root:

```json
{
  "server_url": "http://YOUR_SERVER_IP:8080",
  "display_name": "Lobby Display"
}
```

3. Insert the SD card and power on the BrightSign

### What the autorun does

The `autorun.brs` script (~80 lines) does the following:

1. Reads `config.json` from the SD card for the server URL and display name
2. Sets the display to auto video mode (full screen)
3. Creates an `roHtmlWidget` covering the entire screen
4. Navigates to `{server_url}/player?name={display_name}` -- the `?name=` parameter triggers headless auto-registration so the device registers without needing user interaction
5. Enters an event loop that handles network errors by retrying after 10 seconds

The BrightSign's hardware video acceleration is enabled, and a local cache directory is allocated on the SD card.

### Security settings

The autorun configures two security parameters on the HTML widget:

- **`websecurity: "off"`** -- Disables same-origin policy enforcement. Required because the player page makes API calls to the TinySignage server by IP address, which the Chromium engine would otherwise block as cross-origin requests.
- **`insecure_https_enabled: true`** -- Allows connections to HTTPS servers with self-signed or untrusted certificates. Needed for LAN deployments where the TinySignage server uses a self-signed TLS certificate. If your server uses a valid CA-signed certificate, this setting has no effect.

Both settings are standard for BrightSign HTML widget deployments on local networks. They do not affect security of the TinySignage server itself.

### How TinySignage detects BrightSign

The player automatically detects BrightSign's user agent string and reports `player_type: "brightsign"` instead of `"browser"`. This shows up in the CMS device detail panel as a purple "BrightSign" badge. No configuration needed -- it just works.

### Requirements

- BrightSign player with HTML5 support (Series 4 or newer -- see compatibility table below)
- BOS firmware 8.5 or newer (required for stable `roHtmlWidget`)
- Network access to the TinySignage server
- SD card with the autorun files

### Compatible Hardware

**Product tiers:**

| Tier | Examples | Best for | TinySignage support |
|------|----------|----------|---------------------|
| LS | LS425, LS445 | Menu boards | MRSS only -- limited HTML performance |
| HD | HD225, HD1025, HD226, HD1026 | Single-zone signage | Full (recommended entry point) |
| XD | XD235, XD1035, XD236, XD1036 | Multi-zone / PoE | Full (recommended) |
| XT | XT245, XT1145, XT2145 | Advanced interactive | Full |
| XC | XC2055, XC4055 | Video walls / 8K | Full (overkill for most) |

**Series / generation:**

| Series | Status | Chromium | Recommendation |
|--------|--------|----------|----------------|
| Series 3 (xx3) | End of life | 87 max | Not recommended |
| Series 4 (xx4) | Legacy (end of production) | 87 max | Works, but buy Series 5+ for new installs |
| Series 5 (xx5) | Current | Up to 120 | Recommended |
| Series 6 (xx6) | Current (2025) | 120 native | Recommended |

TinySignage's `player.js` requires only ES2020 features, which are supported by Chromium 87+. Any Series 4 or newer player with BOS 8.5+ firmware will work.

---

## Method 2: MRSS Feed

MRSS (Media RSS) is a standard XML feed format that BrightSign and many other commercial signage players can consume natively. This method is simpler but limited -- it only supports image and video rotation with no schedules, overrides, triggers, or multi-zone layouts.

Use MRSS when:
- You have an existing BrightSign setup using MRSS and want to manage content from TinySignage
- You want to feed content to other MRSS-compatible players (not just BrightSign)
- You don't need advanced features

### Getting the MRSS URL

1. Open the CMS and go to **Devices**
2. Click on any device to open its detail panel
3. The **MRSS Feed URL** is shown with a copy button
4. The URL format is: `http://your-server:8080/api/devices/{device_id}/mrss?token=ts_xxx`

### Configuring BrightSign for MRSS

In BrightSign's setup (BrightAuthor or local configuration):

1. Create a new presentation with an MRSS data feed
2. Paste the MRSS URL from the TinySignage CMS
3. Set the poll interval (recommended: 60 seconds or longer)
4. Deploy to the player

### What the MRSS feed includes

- Image and video assets from the device's current effective playlist
- Respects schedule evaluation and emergency overrides
- Each item includes: media URL, MIME type, duration, and file size
- HTML snippets and URL assets are excluded (not MRSS-compatible)

### MRSS feed format

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>TinySignage - My Playlist</title>
    <item>
      <title>Welcome Banner</title>
      <media:content url="http://server:8080/media/welcome.jpg"
                     type="image/jpeg" duration="10"
                     fileSize="245760" />
    </item>
    <item>
      <title>Promo Video</title>
      <media:content url="http://server:8080/media/promo.mp4"
                     type="video/mp4" duration="30"
                     fileSize="15728640" />
    </item>
  </channel>
</rss>
```

### Authentication

The MRSS endpoint uses query-string token authentication (`?token=ts_xxx`) since most MRSS consumers cannot set HTTP headers. The token shown in the CMS MRSS URL is your current session token. For production use, create a dedicated API token (admin or viewer role) in **Settings > API Tokens**.

### Lightweight heartbeat

Each MRSS poll updates the device's `last_seen` timestamp, so the device will show as online in the CMS health dashboard even when using MRSS instead of the full player.

---

## Comparison

| Feature | HTML Player | MRSS Feed |
|---------|:-----------:|:---------:|
| Image playback | Yes | Yes |
| Video playback | Yes | Yes |
| HTML snippets | Yes | No |
| URL content | Yes | No |
| Schedules | Yes | Yes (server-evaluated) |
| Emergency overrides | Yes | Yes (server-evaluated) |
| Multi-zone layouts | Yes | No |
| Interactive triggers | Yes | No |
| Transitions and effects | Yes | Depends on player |
| Heartbeat and health | Yes | Partial (last_seen only) |
| Offline resilience | Yes (cached) | Depends on player |
| Per-item duration | Yes | Yes |

---

## Troubleshooting

### BrightSign player shows a blank screen
- Verify the SD card contains both `autorun.brs` and `config.json` at the root level
- Check that `server_url` in `config.json` points to a reachable TinySignage server
- Ensure the BrightSign has network connectivity (try pinging the server IP)
- Check BrightSign firmware supports `roHtmlWidget` (Series 4 or newer)

### Device registers but stays pending
- Approve the device in the CMS Devices page -- all new registrations require admin approval

### MRSS feed returns empty
- Verify the device has a playlist assigned in the CMS
- Check that the playlist contains image or video assets (HTML/URL assets are excluded)
- Ensure the API token in the URL is valid and active

### MRSS feed returns 401
- The token may have expired -- generate a new one in Settings > API Tokens
- Make sure the token has at least viewer permissions (or is the device's own token)

---

## See also

- [Devices](devices.md) -- Device registration and management
- [Player Behavior](player-behavior.md) -- How the player communicates with the server
- [API Reference](api-reference.md) -- Endpoint documentation
