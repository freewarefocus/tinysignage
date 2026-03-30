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

```bash
cd tinysignage-bridge
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Dependencies: `gpiozero`, `websockets`, `pyyaml`.

---

## Configuration

Edit `tinysignage-bridge/config.yaml`:

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
[Bridge] WebSocket server on ws://0.0.0.0:8765
[Bridge] Watching 3 pins: 17, 27, 22
[Bridge] Pin 17 (Button 1): falling edge
```

### Mock mode

On machines without GPIO hardware (development, testing), the bridge falls back to a mock mode that reads events from stdin:

```
$ python bridge.py
[Bridge] gpiozero not available — running in mock mode
[Bridge] WebSocket server on ws://0.0.0.0:8765
Type pin number to simulate press (e.g., "17"):
17
[Bridge] Mock: Pin 17 falling edge
```

---

## Running as a systemd service

Create `/etc/systemd/system/tinysignage-bridge.service`:

```ini
[Unit]
Description=TinySignage GPIO Bridge
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/tinysignage-bridge
ExecStart=/home/pi/tinysignage-bridge/venv/bin/python bridge.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable tinysignage-bridge
sudo systemctl start tinysignage-bridge
```

---

## Event format

The bridge broadcasts JSON events over WebSocket:

```json
{
  "type": "gpio",
  "pin": 17,
  "edge": "falling",
  "timestamp": 1234567890.123
}
```

The player matches `pin` and `edge` against GPIO trigger branch configurations. The highest-priority matching branch fires.

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
