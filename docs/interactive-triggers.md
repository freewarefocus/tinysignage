# Interactive Triggers

Interactive triggers let you link playlists together with trigger-driven transitions. Press a button, tap a touch zone, receive a webhook, or let a timer expire -- and the player switches to a different playlist. This enables museum kiosks, wayfinding displays, emergency alerts, and other interactive signage.

---

## Concepts

### TriggerFlows

A TriggerFlow is a layer above playlists. Playlists remain simple linear sequences. A TriggerFlow links multiple playlists together via **branches** -- each branch defines a trigger condition that, when met, transitions the player from one playlist to another.

```
TriggerFlow: "Museum Exhibit Kiosk"

  Playlist A (idle loop)
    ├── keyboard "1"  →  Playlist B (exhibit 1)
    ├── keyboard "2"  →  Playlist C (exhibit 2)
    └── GPIO pin 17   →  Playlist D (exhibit 3)

  Playlist B (exhibit 1)
    └── timeout 30s   →  Playlist A (idle loop)
```

### Branches

Each branch connects a **source playlist** to a **target playlist** via a **trigger type**. When the player is showing the source playlist and the trigger condition is met, it switches to the target playlist.

Branches have a **priority** (higher wins). If multiple branches could fire at the same time, the highest-priority branch wins.

### Simple vs Advanced mode

Playlists have a `mode` field: `simple` (default) or `advanced`. Only advanced playlists can have a TriggerFlow assigned. This keeps the CMS clean for users who don't need triggers.

---

## Trigger types

| Type | Where it runs | Latency | Description |
|------|--------------|---------|-------------|
| **Keyboard** | Browser | Instant | Key press with optional modifiers (Shift, Ctrl, Alt) |
| **Touch zone** | Browser | Instant | Tap/click an invisible overlay area on screen |
| **Timeout** | Browser | Configurable | Timer fires after N seconds |
| **Loop count** | Browser | At loop boundary | Fires after the playlist loops N times |
| **GPIO** | Bridge + Browser | <10ms | Physical button press via GPIO bridge |
| **Webhook** | Server + Browser | Up to 30s | External HTTP POST triggers on next poll |

### Keyboard

Matches a specific key press. Configure the key (e.g., `ArrowRight`, `1`, `Enter`, `Space`, `Escape`) and optional modifier keys.

```json
{ "key": "ArrowRight", "modifiers": [] }
{ "key": "1", "modifiers": ["Shift"] }
```

### Touch zone

An invisible overlay positioned on screen using percentage coordinates. Tapping or clicking the zone fires the trigger.

```json
{ "x_percent": 80, "y_percent": 80, "width_percent": 20, "height_percent": 20 }
```

### Timeout

After the current playlist starts playing, a countdown begins. When it reaches zero, the trigger fires.

```json
{ "seconds": 30 }
```

### Loop count

Tracks how many times the playlist has looped. When the count reaches the target, the trigger fires.

```json
{ "count": 3 }
```

### GPIO

Requires the [GPIO Bridge](gpio-bridge.md) running on a Raspberry Pi. Matches a GPIO pin and edge (falling or rising).

```json
{ "pin": 17, "edge": "falling" }
```

### Webhook

External systems POST to `/api/triggers/webhook/{branch_id}` with a token. The server records the event; the player picks it up on the next poll (up to 30 seconds).

```json
{ "token": "a1b2c3d4e5f6g7h8" }
```

Webhook tokens are auto-generated when creating a webhook branch. You can regenerate them in the CMS.

---

## Setting up triggers in the CMS

### 1. Make a playlist advanced

Open a playlist in the CMS editor. Click **Make Advanced** in the header. This reveals the trigger configuration panel.

### 2. Create or assign a flow

In the trigger panel, either create a new flow or select an existing one from the dropdown. A flow can be shared across playlists.

### 3. Add branches

Click **Add Branch** to define a trigger:

1. Select the **source playlist** (which playlist the player must be showing)
2. Select the **target playlist** (which playlist to switch to)
3. Choose a **trigger type** and configure it
4. Set **priority** (higher priority branches fire first if multiple match)

### 4. Use presets (optional)

If the trigger panel shows no branches, you can start from a preset template:

| Preset | Use case | Triggers |
|--------|----------|----------|
| **Museum Button** | Physical buttons trigger exhibits | GPIO + timeout return |
| **Kiosk Touch** | Touch zones on screen | Touch zones + timeout return |
| **Wayfinding** | Directory with destinations | 3 touch zones + timeout return |
| **Emergency Alert** | External system triggers alert | Webhook (no return) |
| **Scheduled Interrupt** | Periodic content break | Timeout + loop count return |

Presets pre-fill the branch form. You still select which playlists to use.

---

## Webhook triggers

### Firing a webhook

Send a POST request to fire a webhook trigger:

```
POST /api/triggers/webhook/{branch_id}
Content-Type: application/json

{ "token": "your-webhook-token" }
```

No authentication required -- the token in the body validates the request.

### Latency

Webhook triggers have up to 30 seconds of latency because the player discovers new webhook fires through polling. The server records the fire timestamp; the player compares it to the last seen timestamp on each poll.

### Use cases

- **Fire alarm system** triggers emergency playlist on all displays
- **POS integration** switches to a promotional playlist after a transaction
- **Building management** displays wayfinding content when an event starts
- **External scheduling** triggers content changes from a third-party system

---

## Priority and interaction

### Override priority

Triggers sit below emergency overrides and schedules in the priority cascade:

1. Emergency Override (absolute priority)
2. Active Schedule (time-based playlist swap)
3. **TriggerFlow branches** (interactive triggers)
4. Device default playlist

If an override activates while triggers are running, triggers are suspended. When the override ends, the player returns to the flow's entry playlist.

### Offline behavior

All trigger data is cached in `localStorage`. If the server goes offline:

- Keyboard, touch, GPIO, timeout, and loop count triggers continue working
- Webhook triggers stop (they require server communication)
- When connectivity resumes, trigger config updates automatically

---

## Troubleshooting

### Triggers not firing

- Verify the playlist is set to **advanced** mode
- Check that a TriggerFlow is assigned to the playlist
- Ensure branches exist for the current source playlist
- For keyboard triggers, check that the player window has focus

### Webhook not working

- Verify the branch ID and token are correct
- Check that the branch `trigger_type` is `webhook`
- Remember webhook latency is up to 30 seconds (poll interval)
- Check the server logs for 403 or 404 errors

### GPIO not connecting

- Ensure the [GPIO Bridge](gpio-bridge.md) is running on the same machine as the player
- The bridge runs on `ws://localhost:8765` by default
- Check bridge logs for connection errors

---

## See also

- [GPIO Bridge](gpio-bridge.md) -- Setting up physical buttons on Raspberry Pi
- [Playlists](playlists.md) -- Playlist basics
- [Player Behavior](player-behavior.md) -- How the player works
- [Emergency Overrides](emergency-overrides.md) -- Override priority
- [API Reference](api-reference.md) -- Trigger flow and webhook endpoints
