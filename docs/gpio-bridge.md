# GPIO Bridge

The GPIO bridge (`tinysignage-bridge`) is a lightweight companion script that connects physical buttons on a Raspberry Pi to TinySignage's interactive trigger system. It reads GPIO pin state and broadcasts events over a local WebSocket.

---

## How it works

```
Physical button  →  gpiozero (GPIO library)  →  tinysignage-bridge  →  WebSocket  →  player.js
                                                  ws://localhost:8765
```

The bridge is a separate process that runs alongside TinySignage on a Raspberry Pi. It:

1. Reads pin configuration from `config.yaml`
2. Sets up `gpiozero.Button` listeners with configurable debounce
3. Runs a WebSocket server on port 8765
4. Broadcasts GPIO events to all connected clients

The bridge knows nothing about TinySignage internals -- it just reports pin state changes. The player matches incoming events against trigger branch configurations.

---

## Requirements

- Raspberry Pi with GPIO pins (Pi 3, 4, or 5)
- Python 3.9+
- Physical buttons wired to GPIO pins

---

## Wiring

Connect momentary push buttons between GPIO pins and ground:

```
GPIO Pin 17 ──── Button ──── GND
GPIO Pin 27 ──── Button ──── GND
GPIO Pin 22 ──── Button ──── GND
```

The bridge configures internal pull-up resistors by default, so no external resistors are needed. When the button is pressed, the pin goes LOW (falling edge).

---

## Installation

After running the main TinySignage installer, the bridge is located at `/opt/tinysignage/tinysignage-bridge/`. The install script sets up the Python venv, udev rules for joystick access, and a systemd service:

```bash
sudo bash /opt/tinysignage/tinysignage-bridge/install.sh
```

This installs system packages (`python3-lgpio` for Pi 5 GPIO access), Python dependencies (`gpiozero`, `websockets`, `pyyaml`, `evdev`), adds the `tinysignage` user to the `gpio` and `input` groups, creates the udev rule for `/dev/input/event*` access, and enables the `tinysignage-bridge` systemd service.

Edit the configuration **before** running the installer if you want to enable joystick support or change pin assignments.

---

## Configuration

Edit `/opt/tinysignage/tinysignage-bridge/config.yaml`:

```yaml
websocket_port: 8765
pins:
  - pin: 17
    name: "Button 1"
    pull_up: true
    bounce_time: 0.2
  - pin: 27
    name: "Button 2"
    pull_up: true
    bounce_time: 0.2
  - pin: 22
    name: "Button 3"
    pull_up: true
    bounce_time: 0.2
```

| Field | Description |
|-------|-------------|
| `websocket_port` | Port for the WebSocket server (default: 8765) |
| `pin` | BCM GPIO pin number |
| `name` | Human-readable label (for logging) |
| `pull_up` | Enable internal pull-up resistor (default: true) |
| `bounce_time` | Debounce time in seconds (default: 0.2) |

---

## Running

```bash
source venv/bin/activate
python bridge.py
```

The bridge logs pin events to the console:

```
2026-03-29 12:00:00 [INFO] WebSocket server listening on ws://0.0.0.0:8765
2026-03-29 12:00:00 [INFO] Configured pin 17 (Button 1) pull_up=True bounce=0.20s
2026-03-29 12:00:05 [INFO] GPIO event: pin=17 name=Button 1 edge=falling
```

### Mock mode

On machines without GPIO hardware (development, testing), the bridge falls back to a mock mode that reads events from stdin:

```
$ python bridge.py
2026-03-29 12:00:00 [WARNING] gpiozero not available — running in MOCK mode
2026-03-29 12:00:00 [INFO] WebSocket server listening on ws://0.0.0.0:8765
2026-03-29 12:00:00 [INFO] MOCK MODE: Type a pin number and press Enter to simulate a button press.
17
2026-03-29 12:00:05 [INFO] MOCK event: pin=17
```

---

## Running as a systemd service

The install script (`install.sh`) creates and enables the service automatically. To manage it manually:

```bash
sudo systemctl status tinysignage-bridge   # check status
sudo systemctl restart tinysignage-bridge  # restart after config changes
journalctl -u tinysignage-bridge -f        # follow logs
```

---

## Event format

The bridge broadcasts JSON events over WebSocket:

```json
{
  "type": "gpio",
  "pin": 17,
  "name": "Button 1",
  "edge": "falling",
  "timestamp": 1711699200000
}
```

Fields: `pin` (GPIO number), `name` (from config), `edge` (`"falling"` or `"rising"`), `timestamp` (integer milliseconds since epoch). The player matches `pin` and `edge` against GPIO trigger branch configurations. The highest-priority matching branch fires.

---

## Troubleshooting

### Bridge won't start

- Check Python version: `python --version` (requires 3.9+)
- Verify `gpiozero` is installed: `pip list | grep gpiozero`
- On non-Pi hardware, the bridge runs in mock mode automatically

### Buttons not detected

- Verify wiring: button connects GPIO pin to GND
- Check pin numbers in `config.yaml` use BCM numbering (not physical pin numbers)
- Test with `gpiozero` directly: `python -c "from gpiozero import Button; b = Button(17); b.wait_for_press(); print('pressed')"`
- Increase `bounce_time` if getting duplicate events

### Player not responding to buttons

- Ensure the bridge is running on the same machine as the player browser
- Check that the player has GPIO trigger branches configured for the correct pins
- Open browser console and look for `[TinySignage] GPIO bridge connected`
- If you see reconnection messages, the bridge may be restarting -- check its logs

### WebSocket connection refused

- Verify the bridge is running: `curl -v ws://localhost:8765` (expect a 101 Switching Protocols or connection refused if not running)
- Check the port isn't in use by another process: `lsof -i :8765`
- Ensure no firewall is blocking localhost connections

---

## See also

- [Interactive Triggers](interactive-triggers.md) -- Full trigger system documentation
- [Install on Raspberry Pi](install-raspberry-pi.md) -- Pi setup guide
- [Player Behavior](player-behavior.md) -- How the player works
