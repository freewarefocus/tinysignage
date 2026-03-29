# Emergency Overrides

Emergency overrides let admins push urgent content to devices immediately, bypassing all schedules and normal playlists.

---

## What overrides do

An active override takes absolute priority over everything else. When a device polls and an active override targets it, the override content is displayed regardless of the device's assigned playlist, active schedules, or priority settings.

This is designed for urgent situations: fire drills, weather alerts, venue closures, or any content that must appear on screens immediately.

---

## Creating an override

In the CMS, go to **Overrides** (admin-only) and click **New Override**.

### Content type

| Type | Description |
|------|-------------|
| **Message** | A text message displayed on a styled overlay (up to 4096 characters) |
| **Playlist** | A playlist that replaces normal content entirely |

### Target

| Target | Description |
|--------|-------------|
| **All devices** | Every device on the system |
| **Group** | All devices in a specific group |
| **Device** | A single device |

### Auto-expiry

Set an optional **expires at** timestamp. The override automatically deactivates when the expiry time passes. The player schedules a client-side timeout to clear the override at the exact expiry time, so the transition back to normal content is precise.

If no expiry is set, the override remains active until manually deactivated or deleted.

---

## Player response

The polling endpoint includes active override information in every response. The player checks for overrides on every poll cycle (every 30 seconds). When an override is active:

- Message overrides display the text on a full-screen styled overlay
- Playlist overrides replace the current content with the override playlist

When the override expires or is deactivated, the player reverts to its normal playlist within 30 seconds (the next poll cycle).

---

## Canceling an override

Admins can deactivate an override from the Overrides page. Toggle the **active** status or delete the override entirely. The change takes effect on the next device poll.

---

## Audit trail

All override operations (create, update, deactivate, delete) are logged in the audit trail with the admin user, timestamp, and action details.

---

## See also

- [Scheduling](scheduling.md) -- Normal time-based scheduling (overridden by emergencies)
- [Devices](devices.md) -- Device groups for override targeting
- [Users and Permissions](users-and-permissions.md) -- Admin role required for overrides
- [API Reference](api-reference.md) -- Override endpoints
