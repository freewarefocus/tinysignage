# GPIO Bridge

The GPIO bridge (`tinysignage-bridge`) is a lightweight companion script that connects physical buttons on a Raspberry Pi to TinySignage's interactive trigger system. It reads GPIO pin state and broadcasts events over a local WebSocket.

---

## How it works

```
Physical button  →  gpiozero (GPIO library)  →  tinysignage-bridge  →  WebSocket  →  player.js
                                                  ws:// or wss://localhost:8765
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

The `python3-dev` package (needed to compile the `evdev` joystick library) is installed automatically by both the main TinySignage installer and the bridge installer.

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

### During main install (recommended)

The main TinySignage installer offers to install the GPIO bridge at the end of Pi installs (`--mode both` or `--mode player`). Answer **Y** when prompted, or use the `--install-bridge` flag:

```bash
sudo python3 install.py --install-bridge
sudo python3 install.py --mode player --server-url https://cms.local:8080 --install-bridge
```

In `--non-interactive` mode the bridge is only installed when `--install-bridge` is explicitly set.

### Standalone

The bridge can also be installed separately after the main installer has run. It's located at `/opt/tinysignage/tinysignage-bridge/`:

```bash
sudo python3 /opt/tinysignage/tinysignage-bridge/install.py
```

The interactive wizard asks two questions (GPIO buttons? Joystick?) and handles everything else: system packages (`python3-lgpio`, `python3-dev`), Python dependencies (`gpiozero`, `websockets`, `pyyaml`, `evdev`), group membership (`gpio`, `input`), udev rules, TLS certificate generation, and the systemd service.

For unattended installs, use `--non-interactive` (defaults to 3 GPIO buttons, no joystick).

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

### Joystick / gamepad

USB gamepads are auto-detected when plugged in. Enable joystick support in `config.yaml`:

```yaml
joystick:
  enabled: true
  dead_zone: 0.1
  axis_threshold: 0.5
  poll_interval: 0.01
  # Button name map — gives gamepad buttons friendly names in events.
  # Buttons work without being listed here; this just adds readable names.
  # Run "sudo evtest" to discover your gamepad's button codes.
  # Common codes (Xbox / PlayStation):
  #   304 = A / Cross       305 = B / Circle
  #   306 = X / Square      307 = Y / Triangle
  #   310 = LB / L1         311 = RB / R1
  #   314 = Select / Share  315 = Start / Options
  buttons:
    304: "A Button"
```

| Field | Description |
|-------|-------------|
| `enabled` | Turn joystick support on/off |
| `dead_zone` | Ignore axis values below this threshold (0.0–1.0) |
| `axis_threshold` | Axis value that triggers an event (0.0–1.0) |
| `poll_interval` | Seconds between device scans |
| `buttons` | Optional name map — maps evdev button codes to friendly names |

The `buttons` map is optional. Unmapped buttons still broadcast events with their numeric code; mapped buttons also include a `"name"` field. The installer includes a default mapping for button 304 (A / Cross) as a starting example.

To discover your gamepad's button codes, run:

```bash
sudo evtest
```

Select your device from the list, then press buttons to see their codes.

---

## TLS / WSS (when using HTTPS)

When TinySignage serves the player over HTTPS, the bridge must also use
TLS (WSS) to avoid mixed-content blocking. The bridge uses a self-signed
certificate from `/opt/tinysignage/certs/`.

### Automatic certificate handling

Certificates are generated automatically in two places:

1. **Main installer** (`install.py`): When `--mode player` with an `https://` server URL, the installer pre-generates `certs/cert.pem` and `certs/key.pem` before the bridge is installed.
2. **Bridge installer** (`tinysignage-bridge/install.py`): If TLS is needed but certs are missing, the bridge installer generates them itself.

In co-located deployments (`--mode both`), the bridge reuses the CMS server's existing certificates.

### TLS detection

The bridge installer detects that TLS is needed from either signal:
- **Split deployment**: `server_url` in `config.yaml` starts with `https://`
- **Co-located**: `server.https.enabled: true` in `config.yaml`

### Manual TLS config

TLS settings in `tinysignage-bridge/config.yaml`:

```yaml
tls:
  enabled: true
  cert_file: /opt/tinysignage/certs/cert.pem
  key_file: /opt/tinysignage/certs/key.pem
```

Restart the bridge after changing TLS settings:

```bash
sudo systemctl restart tinysignage-bridge
```

If TLS is disabled or the cert files are missing, the bridge falls back
to plain `ws://` (works fine when the player loads over HTTP).

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
2026-03-29 12:00:00 [INFO] MOCK MODE: Type a pin number, or joystick command (j0b0, j0a0+, j0a0-)
17
2026-03-29 12:00:05 [INFO] MOCK event: pin=17
j0b304
2026-03-29 12:00:10 [INFO] MOCK joystick 0 button 304 (A Button) pressed
```

Mock joystick commands: `j<device>b<button>` for button press, add `u` suffix for release, `j<device>a<axis>+` or `-` for axis.

---

## Running as a systemd service

The installer (`install.py`) creates and enables the service automatically. To manage it manually:

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

### Joystick button event

```json
{
  "type": "joystick",
  "event": "button",
  "device": 0,
  "device_name": "Xbox Wireless Controller",
  "button": 304,
  "name": "A Button",
  "value": 1,
  "timestamp": 1711699200000
}
```

The `name` field is included only when the button code has an entry in the `buttons` config map. `value` is `1` for press, `0` for release.

### Joystick axis event

```json
{
  "type": "joystick",
  "event": "axis",
  "device": 0,
  "device_name": "Xbox Wireless Controller",
  "axis": 0,
  "direction": "positive",
  "value": 0.85,
  "timestamp": 1711699200000
}
```

Axis events fire on edge transitions (positive/negative/neutral) using the configured `axis_threshold` and `dead_zone` for hysteresis.

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

- **Mixed-content blocking (HTTPS):** If the player loads over `https://` but the bridge serves plain `ws://`, the browser silently blocks the connection. Enable TLS in the bridge config (see [TLS / WSS](#tls--wss-when-using-https) above)
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
