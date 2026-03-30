#!/usr/bin/env python3
"""
TinySignage GPIO Bridge — WebSocket relay for hardware buttons.

Reads pin configuration from config.yaml, sets up gpiozero listeners,
and broadcasts GPIO events to all connected WebSocket clients.

Runs standalone on a Raspberry Pi (or in mock mode on any machine).
Does not know about TinySignage internals — it only relays pin events.
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

import yaml

try:
    import websockets
except ImportError:
    print("ERROR: websockets package required. Install with: pip install websockets>=12.0")
    sys.exit(1)

# Try to import gpiozero; fall back to mock mode if unavailable
MOCK_MODE = False
try:
    from gpiozero import Button
except ImportError:
    MOCK_MODE = True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("tinysignage-bridge")

# Connected WebSocket clients
clients: set = set()


def load_config() -> dict:
    """Load pin configuration from config.yaml."""
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        log.error("config.yaml not found at %s", config_path)
        sys.exit(1)
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


async def broadcast(message: dict):
    """Send a JSON message to all connected WebSocket clients."""
    if not clients:
        return
    payload = json.dumps(message)
    disconnected = set()
    for ws in clients:
        try:
            await ws.send(payload)
        except websockets.exceptions.ConnectionClosed:
            disconnected.add(ws)
    clients.difference_update(disconnected)


def make_callback(pin_number: int, pin_name: str, edge: str, loop: asyncio.AbstractEventLoop):
    """Create a GPIO callback that broadcasts the event.

    The loop parameter is captured at setup time because gpiozero fires
    callbacks from a background thread that has no running asyncio loop.
    """
    def callback():
        event = {
            "type": "gpio",
            "pin": pin_number,
            "name": pin_name,
            "edge": edge,
            "timestamp": int(time.time() * 1000),
        }
        log.info("GPIO event: pin=%d name=%s edge=%s", pin_number, pin_name, edge)
        # Schedule broadcast on the event loop (safe from any thread)
        loop.call_soon_threadsafe(asyncio.ensure_future, broadcast(event))
    return callback


def setup_gpio(config: dict, loop: asyncio.AbstractEventLoop) -> list:
    """Set up gpiozero Button listeners from config."""
    buttons = []
    for pin_cfg in config.get("pins", []):
        pin = pin_cfg["pin"]
        name = pin_cfg.get("name", f"Pin {pin}")
        pull_up = pin_cfg.get("pull_up", True)
        bounce_time = pin_cfg.get("bounce_time", 0.2)

        btn = Button(pin, pull_up=pull_up, bounce_time=bounce_time)
        btn.when_pressed = make_callback(pin, name, "falling", loop)
        btn.when_released = make_callback(pin, name, "rising", loop)
        buttons.append(btn)
        log.info("Configured pin %d (%s) pull_up=%s bounce=%.2fs", pin, name, pull_up, bounce_time)

    return buttons


async def mock_gpio_loop(config: dict):
    """In mock mode, simulate GPIO events from stdin."""
    log.info("MOCK MODE: Type a pin number and press Enter to simulate a button press.")
    pin_map = {str(p["pin"]): p for p in config.get("pins", [])}
    loop = asyncio.get_running_loop()

    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        line = line.strip()
        if not line:
            continue
        if line in pin_map:
            pin_cfg = pin_map[line]
            event = {
                "type": "gpio",
                "pin": pin_cfg["pin"],
                "name": pin_cfg.get("name", f"Pin {pin_cfg['pin']}"),
                "edge": "falling",
                "timestamp": int(time.time() * 1000),
            }
            log.info("MOCK event: pin=%d", pin_cfg["pin"])
            await broadcast(event)
        else:
            log.warning("Unknown pin '%s'. Available: %s", line, list(pin_map.keys()))


async def handler(websocket):
    """Handle a new WebSocket connection."""
    clients.add(websocket)
    remote = websocket.remote_address
    log.info("Client connected: %s", remote)
    try:
        async for _ in websocket:
            pass  # We only send, never receive meaningful data
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)
        log.info("Client disconnected: %s", remote)


async def main():
    config = load_config()
    port = config.get("websocket_port", 8765)

    if not MOCK_MODE:
        loop = asyncio.get_running_loop()
        buttons = setup_gpio(config, loop)
        log.info("GPIO mode: %d pin(s) configured", len(buttons))
    else:
        log.warning("gpiozero not available — running in MOCK mode")

    async with websockets.serve(handler, "0.0.0.0", port):
        log.info("WebSocket server listening on ws://0.0.0.0:%d", port)
        if MOCK_MODE:
            await mock_gpio_loop(config)
        else:
            await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())
