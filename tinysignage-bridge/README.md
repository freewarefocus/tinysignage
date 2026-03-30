# TinySignage GPIO Bridge

Lightweight companion process that relays Raspberry Pi GPIO button presses to the TinySignage player via WebSocket.

## Overview

The bridge runs on a Raspberry Pi alongside the TinySignage player (or on the same network). It monitors physical buttons connected to GPIO pins and broadcasts events over WebSocket. The player listens for these events and maps them to trigger flow branches.

```
┌──────────────┐   WebSocket    ┌────────────┐
│  GPIO Bridge │───────────────►│  player.js │
│  (this app)  │  ws://localhost│  (browser) │
│  gpiozero    │  :8765         │            │
└──────────────┘                └────────────┘
```

## Hardware Setup

### Wiring

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

## Installation

```bash
cd tinysignage-bridge
python -m venv venv
source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

## Configuration

Edit `config.yaml` to match your hardware:

```yaml
websocket_port: 8765

pins:
  - pin: 17          # BCM pin number
    name: "Button 1"  # Human-readable name (included in events)
    pull_up: true      # Use internal pull-up resistor
    bounce_time: 0.2   # Debounce in seconds
```

## Running

```bash
python bridge.py
```

The bridge starts a WebSocket server on the configured port (default 8765) and logs GPIO events to the console.

### Mock Mode

On machines without GPIO hardware (e.g., development laptops), the bridge automatically falls back to **mock mode**. Type a pin number and press Enter to simulate a button press:

```
$ python bridge.py
2026-03-29 12:00:00 [WARNING] gpiozero not available — running in MOCK mode
2026-03-29 12:00:00 [INFO] WebSocket server listening on ws://0.0.0.0:8765
2026-03-29 12:00:00 [INFO] MOCK MODE: Type a pin number and press Enter to simulate a button press.
17
2026-03-29 12:00:05 [INFO] MOCK event: pin=17
```

### Running as a Service (systemd)

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

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tinysignage-bridge
sudo systemctl start tinysignage-bridge
```

## WebSocket Event Format

Each GPIO event is broadcast as JSON:

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

## TinySignage Integration

1. In the TinySignage CMS, create an advanced playlist with a trigger flow
2. Add GPIO-type branches matching your pin numbers
3. The player automatically connects to `ws://localhost:8765` when GPIO branches exist
4. Button presses fire the corresponding trigger transitions

## Troubleshooting

- **"gpiozero not available"**: Install gpiozero (`pip install gpiozero`) or run on a Raspberry Pi
- **No WebSocket connections**: Check firewall rules; ensure the player and bridge are on the same host/network
- **Button not responding**: Verify wiring (pin to GND), check pin number in config matches BCM numbering
- **Bouncing/double triggers**: Increase `bounce_time` in config (e.g., 0.3 or 0.5)
