# TinySignage GPIO Bridge

Lightweight companion process that relays Raspberry Pi GPIO button presses and USB joystick/gamepad events to the TinySignage player via WebSocket.

## Overview

The bridge runs on a Raspberry Pi alongside the TinySignage player (or on the same network). It monitors physical buttons connected to GPIO pins and USB joysticks/gamepads, broadcasting events over WebSocket. The player listens for these events and maps them to trigger flow branches.

```
┌──────────────┐   WebSocket    ┌────────────┐
│  GPIO Bridge │───────────────►│  player.js │
│  (this app)  │  ws://localhost│  (browser) │
│  gpiozero +  │  :8765         │            │
│  evdev       │                │            │
└──────────────┘                └────────────┘
```

## Hardware Setup

### GPIO Wiring

Connect buttons between GPIO pins and GND (ground). The bridge uses internal pull-up resistors by default, so no external resistors are needed.

```
GPIO Pin ──── Button ──── GND
```

### Common Pin Layout (Raspberry Pi)

| Pin | BCM | Default Config |
|-----|-----|----------------|
| 11  | 17  | Button 1       |
| 13  | 27  | Button 2       |
| 15  | 22  | Button 3       |

### Joystick / Gamepad

Plug a USB joystick or gamepad into the Raspberry Pi. The bridge auto-detects devices with joystick capabilities (absolute axes or gamepad buttons).

**Permissions**: `/dev/input/event*` devices require the user to be in the `input` group:

```bash
sudo usermod -aG input pi
# Log out and back in for the change to take effect
```

Alternatively, create a udev rule for broader access:

```bash
echo 'KERNEL=="event*", SUBSYSTEM=="input", MODE="0664", GROUP="input"' | \
  sudo tee /etc/udev/rules.d/99-input.rules
sudo udevadm control --reload-rules
```

## Installation

After running the main TinySignage installer, the bridge is located at `/opt/tinysignage/tinysignage-bridge/`. The installer walks you through a short setup wizard (2-3 questions) and handles everything — Python venv, udev rules, input group, config.yaml, and systemd service:

```bash
sudo python3 /opt/tinysignage/tinysignage-bridge/install.py
```

The wizard asks which buttons and gamepad options you want, then generates `config.yaml` to match. For scripted or headless installs, use `--non-interactive` to skip prompts and use defaults (3 GPIO buttons, no joystick):

```bash
sudo python3 /opt/tinysignage/tinysignage-bridge/install.py --non-interactive
```

Note: `evdev` is Linux-only. On non-Linux systems, joystick support is unavailable but GPIO mock mode still works.

## Configuration

Edit `config.yaml` to match your hardware:

```yaml
websocket_port: 8765

pins:
  - pin: 17          # BCM pin number
    name: "Button 1"  # Human-readable name (included in events)
    pull_up: true      # Use internal pull-up resistor
    bounce_time: 0.2   # Debounce in seconds

joystick:
  enabled: false       # Set to true to enable joystick support
  dead_zone: 0.1       # Ignore axis values below this (0.0–1.0)
  axis_threshold: 0.5  # Axis value that triggers an event (0.0–1.0)
  poll_interval: 0.01  # Seconds between device scans
```

### Joystick Config

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `false` | Master switch for joystick support |
| `dead_zone` | `0.1` | Axis values below this are ignored (prevents drift) |
| `axis_threshold` | `0.5` | Axis must cross this value to fire an event |
| `poll_interval` | `0.01` | How often to check for new events (seconds) |

The bridge uses **edge-triggering with hysteresis** for axes: an event fires once when the axis crosses `axis_threshold`, and resets only when the axis returns below `axis_threshold - dead_zone`. This prevents rapid-fire events when holding a joystick at the threshold boundary.

## Running

```bash
python bridge.py
```

The bridge starts a WebSocket server on the configured port (default 8765) and logs GPIO/joystick events to the console.

### Hot-Plug

The bridge re-scans for new joystick devices every 5 seconds. Plug in a gamepad after the bridge is running and it will be detected automatically.

### Mock Mode

On machines without GPIO hardware (e.g., development laptops), the bridge automatically falls back to **mock mode**. Type commands and press Enter to simulate events:

**GPIO mock:**
```
17          → Simulate pin 17 button press
```

**Joystick mock** (when `joystick.enabled: true`):
```
j0b0        → Joystick 0, button 0 pressed
j0b0u       → Joystick 0, button 0 released
j0a0+       → Joystick 0, axis 0 positive direction
j0a0-       → Joystick 0, axis 0 negative direction
j1b3        → Joystick 1, button 3 pressed
```

Format: `j<device>b<button>[u]` for buttons, `j<device>a<axis><+|->` for axes.

Example session:
```
$ python bridge.py
2026-04-09 12:00:00 [WARNING] gpiozero not available — running in MOCK mode
2026-04-09 12:00:00 [INFO] Joystick mock commands enabled (j0b0, j0a0+, j0a0-)
2026-04-09 12:00:00 [INFO] WebSocket server listening on ws://0.0.0.0:8765
j0b0
2026-04-09 12:00:05 [INFO] MOCK joystick 0 button 0 pressed
```

### Running as a Service (systemd)

The installer (`install.py`) creates and enables the service automatically. To manage it manually:

```bash
sudo systemctl status tinysignage-bridge   # check status
sudo systemctl restart tinysignage-bridge  # restart after config changes
journalctl -u tinysignage-bridge -f        # follow logs
```

## WebSocket Event Format

### GPIO Events

```json
{
  "type": "gpio",
  "pin": 17,
  "name": "Button 1",
  "edge": "falling",
  "timestamp": 1711699200000
}
```

- `type`: Always `"gpio"`
- `pin`: BCM pin number
- `name`: Human-readable name from config
- `edge`: `"falling"` (button pressed) or `"rising"` (button released)
- `timestamp`: Unix timestamp in milliseconds

### Joystick Button Events

```json
{
  "type": "joystick",
  "event": "button",
  "device": 0,
  "device_name": "USB Gamepad",
  "button": 288,
  "value": 1,
  "timestamp": 1711699200000
}
```

- `type`: Always `"joystick"`
- `event`: `"button"`
- `device`: Sequential device index (0-based)
- `device_name`: Device name reported by the OS
- `button`: Raw evdev button code (see table below)
- `value`: `1` = pressed, `0` = released
- `timestamp`: Unix timestamp in milliseconds

### Joystick Axis Events

```json
{
  "type": "joystick",
  "event": "axis",
  "device": 0,
  "device_name": "USB Gamepad",
  "axis": 0,
  "direction": "positive",
  "value": 0.85,
  "timestamp": 1711699200000
}
```

- `event`: `"axis"`
- `axis`: Raw evdev axis code
- `direction`: `"positive"` or `"negative"` (edge-triggered)
- `value`: Normalized value (-1.0 to 1.0) at the time of the event

### Common Button Codes

| Code | Name | Typical Device |
|------|------|---------------|
| 288 | BTN_TRIGGER | Cheap USB joysticks |
| 289 | BTN_THUMB | Cheap USB joysticks |
| 304 | BTN_SOUTH / BTN_A | Xbox / modern gamepads |
| 305 | BTN_EAST / BTN_B | Xbox / modern gamepads |
| 306 | BTN_C | 6-button controllers |
| 307 | BTN_NORTH / BTN_X | Xbox / modern gamepads |
| 308 | BTN_WEST / BTN_Y | Xbox / modern gamepads |

Button codes vary by device — use `evtest` to discover the codes for your specific gamepad (see below).

### Finding Your Button Codes with evtest

Every gamepad uses different raw codes. To find the exact codes for your device, use `evtest`:

```bash
sudo apt install evtest
sudo evtest
```

It will list your input devices:

```
/dev/input/event0:  USB Gamepad
/dev/input/event1:  gpio-keys
Select the device event number [0-1]: 0
```

Pick your joystick, then press buttons or move sticks. Each input prints its raw code:

```
Event: time 1711699200.123, type 1 (EV_KEY), code 288 (BTN_TRIGGER), value 1
Event: time 1711699200.456, type 1 (EV_KEY), code 289 (BTN_THUMB), value 1
Event: time 1711699200.789, type 3 (EV_ABS), code 0 (ABS_X), value 255
```

The number after `code` is what you enter in the CMS — for example, `288` for the first button above. Axis codes (like `0` for ABS_X) are used in the axis number field.

Press Ctrl+C to exit when done.

## TinySignage Integration

1. In the TinySignage CMS, create an advanced playlist with a trigger flow
2. Add GPIO or Joystick-type branches matching your hardware
3. The player automatically connects to `ws://localhost:8765` when GPIO or joystick branches exist
4. Button presses and joystick inputs fire the corresponding trigger transitions

## Troubleshooting

- **"gpiozero not available"**: Install gpiozero (`pip install gpiozero`) or run on a Raspberry Pi
- **"BadPinFactory" on Pi 5**: Install `python3-lgpio` via apt (`sudo apt install python3-lgpio`) and ensure the venv uses `--system-site-packages`. The `tinysignage` user must also be in the `gpio` group (`sudo usermod -aG gpio tinysignage`). The install script handles all of this automatically.
- **"evdev not installed"**: Install evdev (`pip install evdev`) — Linux only
- **No joystick detected**: Check `input` group membership (`groups` command), verify device with `evtest`
- **No WebSocket connections**: Check firewall rules; ensure the player and bridge are on the same host/network
- **Button not responding**: Verify wiring (pin to GND), check pin number in config matches BCM numbering
- **Bouncing/double triggers**: Increase `bounce_time` in config (e.g., 0.3 or 0.5)
- **Axis rapid-fire**: Increase `dead_zone` or `axis_threshold` in config
- **Device index changes across reboots**: Use `device: null` in CMS config to match any joystick (best for single-device setups)
