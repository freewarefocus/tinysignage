#!/bin/bash
# X11 kiosk session for Pi OS Lite
# Started by xinit from systemd — replaces cage as the display server

# Python binary (passed by systemd ExecStart)
PYTHON="${1:-python3}"

# Derive install directory from this script's location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$(dirname "$SCRIPT_DIR")"

# Disable screen blanking & DPMS
xset s off
xset -dpms
xset s noblank

# Hide cursor after 3 seconds of inactivity
unclutter -idle 3 -root &

# Start matchbox window manager (no decorations, no taskbar)
matchbox-window-manager -use_titlebar no -use_desktop_mode plain &

# Launch the TinySignage player browser
exec "$PYTHON" "$INSTALL_DIR/launcher.py"
