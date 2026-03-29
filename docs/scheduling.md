# Scheduling

Schedules let you automatically switch playlists based on time of day, day of week, date range, or recurring patterns. The server evaluates schedules when a device polls, so the player itself has no scheduling logic.

---

## How scheduling works

When a device polls for its playlist (`GET /api/devices/{id}/playlist`), the server checks all active schedules that target that device (directly, via a group, or via "all"). If a schedule matches the current time, its playlist is served instead of the device's default playlist. If no schedule matches, the device's assigned playlist plays.

Scheduling is entirely server-side. The player does not know about schedules -- it just plays whatever playlist the server returns.

---

## Creating a schedule

In the CMS, go to **Schedules** and click **New Schedule**.

### Required fields

- **Name** -- Descriptive name (e.g., "Weekend evening menu")
- **Playlist** -- The playlist to play when this schedule is active

### Target

Choose what this schedule applies to:

| Target | Description |
|--------|-------------|
| **All devices** | Every device on the system |
| **Group** | All devices in a specific group |
| **Device** | A single device |

### Time window

Set when the schedule is active:

- **Start time / End time** -- 24-hour format (e.g., `09:00` to `17:00`). Leave both empty for "all day."
- **Days of week** -- Select specific days (Monday=0 through Sunday=6). Leave empty for "every day."

### Date range

Optionally restrict the schedule to a date range:

- **Start date** -- Schedule becomes active on this date
- **End date** -- Schedule stops after this date

---

## Priority system

When multiple schedules match the same device at the same time, the one with the highest **priority** value wins. Higher numbers = higher priority.

| Priority | Typical use |
|----------|-------------|
| 0 (default) | Base schedules |
| 1-5 | Seasonal or event overrides |
| 10+ | High-priority special content |

If two schedules have the same priority, the **priority weight** (default 1.0) is used for weighted random selection.

Emergency overrides always take absolute priority over all schedules, regardless of priority values.

---

## RRULE recurrence

For complex recurring patterns, schedules support iCal RRULE syntax:

| Pattern | RRULE |
|---------|-------|
| Every day | `FREQ=DAILY` |
| Every week | `FREQ=WEEKLY` |
| Every Monday and Wednesday | `FREQ=WEEKLY;BYDAY=MO,WE` |
| First Monday of each month | `FREQ=MONTHLY;BYDAY=1MO` |
| Every 2 weeks | `FREQ=WEEKLY;INTERVAL=2` |
| Every year on March 15 | `FREQ=YEARLY;BYMONTHDAY=15;BYMONTH=3` |

The RRULE is evaluated server-side on each poll to determine if the schedule is active right now.

---

## Transition playlists

A schedule can optionally specify a **transition playlist** -- a short playlist (e.g., a "please stand by" animation) that plays briefly when switching between the previous content and the scheduled content. This creates smoother transitions between scheduled blocks.

---

## Timeline preview

The timeline preview (`GET /api/schedules/preview/timeline`) shows a 48-slot view (half-hour increments) of what playlist will play on a given device for a given date. Use this to verify that your schedules are configured correctly before they go live.

---

## Fallback behavior

If no schedule matches the current time, the device falls back to its directly assigned playlist. If no playlist is assigned to the device at all, the player shows its splash screen.

---

## Common patterns

### Business hours content, after-hours screensaver

1. Assign a generic screensaver playlist as the device's default
2. Create a schedule for business hours (Mon-Fri, 08:00-18:00) with your main content playlist

### Lunch menu

1. Create a "Lunch Menu" playlist with menu images
2. Create a schedule targeting your dining area group, 11:00-14:00, Mon-Fri

### Holiday content

1. Create a "Holiday" playlist
2. Create a schedule with a date range (e.g., Dec 20 to Jan 2), priority 5 (overrides normal schedules)

### Rotating weekly specials

1. Create separate playlists for each day's specials
2. Create schedules for each day of the week targeting the relevant devices

---

## See also

- [Playlists](playlists.md) -- Creating playlists to schedule
- [Devices](devices.md) -- Device groups for schedule targeting
- [Emergency Overrides](emergency-overrides.md) -- Overrides that bypass all schedules
- [API Reference](api-reference.md) -- Schedule endpoints and timeline preview
