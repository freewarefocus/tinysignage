#!/bin/bash
# X11 kiosk session for Pi OS Lite
# Started by xinit from systemd — replaces cage as the display server

# Python binary (passed by systemd ExecStart)
PYTHON="${1:-python3}"

# Derive install directory from this script's location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$(dirname "$SCRIPT_DIR")"

# Set up a runtime directory and D-Bus session for the service user.
# Chromium requires D-Bus + PipeWire/PulseAudio for audio output.
# The kiosk runs as a dedicated service user (tinysignage) which has
# no login session, so we start these services here.
#
# /run/user/<UID> may not exist for system users (logind doesn't create it)
# so fall back to a writable tmpfs path if mkdir fails.
_WANT_DIR="${XDG_RUNTIME_DIR:-/tmp/tinysignage-runtime}"
if mkdir -p "$_WANT_DIR" 2>/dev/null && [ -w "$_WANT_DIR" ]; then
    export XDG_RUNTIME_DIR="$_WANT_DIR"
else
    export XDG_RUNTIME_DIR="/tmp/tinysignage-runtime"
    mkdir -p "$XDG_RUNTIME_DIR"
fi

# Start a session D-Bus daemon. dbus-launch (from dbus-x11) is unreliable
# in service contexts — it often exits without setting the address, leaving
# PipeWire and Chromium unable to find D-Bus. Start dbus-daemon directly
# with a known socket path instead.
_dbus_sock="unix:path=$XDG_RUNTIME_DIR/bus"
if dbus-daemon --session --address="$_dbus_sock" --fork --nopidfile 2>/dev/null; then
    export DBUS_SESSION_BUS_ADDRESS="$_dbus_sock"
elif command -v dbus-launch >/dev/null 2>&1; then
    eval $(dbus-launch --sh-syntax 2>/dev/null)
    export DBUS_SESSION_BUS_ADDRESS
fi

# Start PipeWire audio stack for this user
if command -v pipewire >/dev/null 2>&1; then
    pipewire &
    sleep 0.3
    pipewire-pulse &
    wireplumber &
    sleep 1

    # Auto-select USB audio DAC if one is connected.
    # WirePlumber gives USB sinks a default priority (~1000) which loses to
    # built-in audio. Find the first USB audio sink and promote it.
    if command -v wpctl >/dev/null 2>&1; then
        # Parse wpctl status: extract Sinks section, find USB device,
        # pull the numeric sink ID (e.g. "47" from "  47. USB Audio ...").
        _usb_sink=$(wpctl status 2>/dev/null | \
            sed -n '/Sinks/,/endpoint\|Source\|Stream/p' | \
            grep -i usb | \
            head -1 | \
            sed 's/[^0-9]*\([0-9][0-9]*\)\..*/\1/')
        if [ -n "$_usb_sink" ]; then
            wpctl set-default "$_usb_sink" 2>/dev/null && \
                echo "Audio: USB DAC (sink $_usb_sink) set as default"
        fi
    fi
fi

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
