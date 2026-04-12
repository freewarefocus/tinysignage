#!/usr/bin/env python3
"""
TinySignage GPIO Bridge — WebSocket relay for hardware buttons and joysticks.

Reads pin configuration from config.yaml, sets up gpiozero listeners,
and broadcasts GPIO/joystick events to all connected WebSocket clients.

Runs standalone on a Raspberry Pi (or in mock mode on any machine).
Does not know about TinySignage internals — it only relays pin events.
"""

import asyncio
import json
import logging
import re
import ssl
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

# Try to import evdev for joystick support
JOYSTICK_AVAILABLE = False
try:
    import evdev
    from evdev import ecodes
    JOYSTICK_AVAILABLE = True
except ImportError:
    pass

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


# --- Joystick support via evdev ---

def find_joystick_devices():
    """Scan /dev/input/event* for joystick/gamepad devices."""
    if not JOYSTICK_AVAILABLE:
        return []
    devices = []
    for path in sorted(evdev.list_devices()):
        try:
            dev = evdev.InputDevice(path)
            caps = dev.capabilities(verbose=False)
            # Look for devices with absolute axes (EV_ABS) or joystick buttons
            has_abs = ecodes.EV_ABS in caps
            has_joy_btn = False
            if ecodes.EV_KEY in caps:
                key_caps = caps[ecodes.EV_KEY]
                # Joystick/gamepad buttons are typically in 0x120-0x13F range
                has_joy_btn = any(0x120 <= k <= 0x13F for k in key_caps)
                # Also check for common gamepad buttons (BTN_A=0x130, BTN_SOUTH=0x130, etc.)
                if not has_joy_btn:
                    has_joy_btn = any(0x130 <= k <= 0x13F for k in key_caps)
            if has_abs or has_joy_btn:
                devices.append(dev)
                log.info("Found joystick: %s (%s)", dev.name, dev.path)
            else:
                dev.close()
        except (PermissionError, OSError) as e:
            log.debug("Cannot open %s: %s", path, e)
    return devices


async def read_single_joystick(device, device_index, config):
    """Read events from a single joystick device and broadcast them."""
    dead_zone = config.get("dead_zone", 0.1)
    axis_threshold = config.get("axis_threshold", 0.5)
    device_name = device.name

    # Track axis states for edge-triggering: (axis_code) -> "positive" | "negative" | None
    axis_states = {}

    log.info("Reading joystick %d: %s (%s)", device_index, device_name, device.path)

    try:
        async for ev in device.async_read_loop():
            if ev.type == ecodes.EV_KEY:
                # Button event
                # ev.value: 0=release, 1=press, 2=repeat (ignore repeat)
                if ev.value == 2:
                    continue
                event = {
                    "type": "joystick",
                    "event": "button",
                    "device": device_index,
                    "device_name": device_name,
                    "button": ev.code,
                    "value": ev.value,
                    "timestamp": int(time.time() * 1000),
                }
                log.info("Joystick %d button %d %s", device_index, ev.code,
                         "pressed" if ev.value else "released")
                await broadcast(event)

            elif ev.type == ecodes.EV_ABS:
                # Axis event — normalize and edge-trigger
                absinfo = device.absinfo(ev.code)
                if absinfo is None:
                    continue

                # Normalize to -1.0 .. 1.0
                mid = (absinfo.max + absinfo.min) / 2.0
                range_val = (absinfo.max - absinfo.min) / 2.0
                if range_val == 0:
                    continue
                normalized = (ev.value - mid) / range_val
                normalized = max(-1.0, min(1.0, normalized))

                abs_val = abs(normalized)
                prev_state = axis_states.get(ev.code)

                # Determine current direction
                if abs_val >= axis_threshold:
                    current_dir = "positive" if normalized > 0 else "negative"
                else:
                    current_dir = None

                # Edge-trigger: fire only on state change
                # Reset uses hysteresis: must drop below (threshold - dead_zone)
                if current_dir and current_dir != prev_state:
                    axis_states[ev.code] = current_dir
                    event = {
                        "type": "joystick",
                        "event": "axis",
                        "device": device_index,
                        "device_name": device_name,
                        "axis": ev.code,
                        "direction": current_dir,
                        "value": round(normalized, 3),
                        "timestamp": int(time.time() * 1000),
                    }
                    log.info("Joystick %d axis %d %s (%.3f)",
                             device_index, ev.code, current_dir, normalized)
                    await broadcast(event)
                elif prev_state and abs_val < (axis_threshold - dead_zone):
                    # Returned below hysteresis threshold — reset state
                    axis_states[ev.code] = None

    except (OSError, IOError):
        log.warning("Joystick %d (%s) disconnected", device_index, device_name)
    except Exception:
        log.exception("Joystick %d (%s) unexpected error", device_index, device_name)
    finally:
        try:
            device.close()
        except Exception:
            pass


async def read_joystick_events(config):
    """Supervisor: discover joystick devices, start readers, re-scan for hot-plug."""
    joy_config = config.get("joystick", {})
    active_paths = {}  # device.path -> asyncio.Task
    device_index_counter = 0

    while True:
        # Clean up finished tasks
        for path in list(active_paths):
            if active_paths[path].done():
                del active_paths[path]

        # Skip rescan when all tracked joystick tasks are still running
        if not active_paths or any(t.done() for t in active_paths.values()):
            for dev in find_joystick_devices():
                if dev.path not in active_paths or active_paths[dev.path].done():
                    idx = device_index_counter
                    device_index_counter += 1
                    task = asyncio.create_task(read_single_joystick(dev, idx, joy_config))
                    active_paths[dev.path] = task
                else:
                    dev.close()  # Already being read

        # Re-scan every 5 seconds for hot-plug
        await asyncio.sleep(5)


# --- Mock mode ---

# Mock command patterns:
#   "17"       -> GPIO pin 17 press
#   "j0b1"     -> Joystick 0, button 1 pressed
#   "j0b1u"    -> Joystick 0, button 1 released
#   "j0a0+"    -> Joystick 0, axis 0 positive
#   "j0a0-"    -> Joystick 0, axis 0 negative
MOCK_JOYSTICK_RE = re.compile(r"^j(\d+)(b|a)(\d+)([u+\-]?)$")


async def mock_gpio_loop(config: dict):
    """In mock mode, simulate GPIO and joystick events from stdin."""
    joy_enabled = config.get("joystick", {}).get("enabled", False)
    if joy_enabled:
        log.info("MOCK MODE: Type a pin number, or joystick command (j0b0, j0a0+, j0a0-)")
    else:
        log.info("MOCK MODE: Type a pin number and press Enter to simulate a button press.")
    pin_map = {str(p["pin"]): p for p in config.get("pins", [])}
    loop = asyncio.get_running_loop()

    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        line = line.strip()
        if not line:
            continue

        # Check for joystick mock command
        m = MOCK_JOYSTICK_RE.match(line)
        if m and joy_enabled:
            dev_idx = int(m.group(1))
            input_type = m.group(2)  # 'b' for button, 'a' for axis
            code = int(m.group(3))
            modifier = m.group(4)  # 'u' for release, '+'/'-' for axis direction, '' for press

            if input_type == "b":
                value = 0 if modifier == "u" else 1
                event = {
                    "type": "joystick",
                    "event": "button",
                    "device": dev_idx,
                    "device_name": f"Mock Joystick {dev_idx}",
                    "button": code,
                    "value": value,
                    "timestamp": int(time.time() * 1000),
                }
                log.info("MOCK joystick %d button %d %s", dev_idx, code,
                         "pressed" if value else "released")
            else:
                direction = "negative" if modifier == "-" else "positive"
                event = {
                    "type": "joystick",
                    "event": "axis",
                    "device": dev_idx,
                    "device_name": f"Mock Joystick {dev_idx}",
                    "axis": code,
                    "direction": direction,
                    "value": 0.85 if direction == "positive" else -0.85,
                    "timestamp": int(time.time() * 1000),
                }
                log.info("MOCK joystick %d axis %d %s", dev_idx, code, direction)

            await broadcast(event)
        elif line in pin_map:
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
            available = list(pin_map.keys())
            if joy_enabled:
                available.append("j<dev>b<btn>, j<dev>a<axis>+/-")
            log.warning("Unknown command '%s'. Available: %s", line, available)


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
    joy_config = config.get("joystick", {})
    joy_enabled = joy_config.get("enabled", False)

    if not MOCK_MODE:
        loop = asyncio.get_running_loop()
        buttons = setup_gpio(config, loop)
        log.info("GPIO mode: %d pin(s) configured", len(buttons))
    else:
        log.warning("gpiozero not available — running in MOCK mode")

    # Start joystick reader if enabled and available
    joystick_task = None
    if joy_enabled and JOYSTICK_AVAILABLE and not MOCK_MODE:
        joystick_task = asyncio.create_task(read_joystick_events(config))
        log.info("Joystick support enabled (evdev)")
    elif joy_enabled and not JOYSTICK_AVAILABLE and not MOCK_MODE:
        log.warning("Joystick enabled in config but evdev not installed")
    elif joy_enabled and MOCK_MODE:
        log.info("Joystick mock commands enabled (j0b0, j0a0+, j0a0-)")

    # --- TLS / WSS support ---
    tls_config = config.get("tls", {})
    ssl_context = None
    if tls_config.get("enabled", False):
        cert_file = tls_config.get("cert_file", "/opt/tinysignage/certs/cert.pem")
        key_file = tls_config.get("key_file", "/opt/tinysignage/certs/key.pem")
        if Path(cert_file).exists() and Path(key_file).exists():
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(cert_file, key_file)
            log.info("TLS enabled — serving wss:// with cert %s", cert_file)
        else:
            log.warning("TLS enabled but cert/key not found (%s, %s) — falling back to ws://", cert_file, key_file)

    proto = "wss" if ssl_context else "ws"
    async with websockets.serve(handler, "0.0.0.0", port, ssl=ssl_context):
        log.info("WebSocket server listening on %s://0.0.0.0:%d", proto, port)
        if MOCK_MODE:
            await mock_gpio_loop(config)
        else:
            await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())
