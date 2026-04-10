#!/usr/bin/env bash
# TinySignage GPIO Bridge — installer
# Sets up apt packages, Python venv, udev rules, groups, and systemd service.
# Run with: sudo bash /opt/tinysignage/tinysignage-bridge/install.sh

set -euo pipefail

BRIDGE_DIR="/opt/tinysignage/tinysignage-bridge"
SERVICE_USER="tinysignage"
SERVICE_FILE="/etc/systemd/system/tinysignage-bridge.service"
UDEV_RULE="/etc/udev/rules.d/99-input.rules"

# --- Preflight checks ------------------------------------------------------

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: must run as root (sudo)."
    exit 1
fi

if [ ! -f "$BRIDGE_DIR/bridge.py" ]; then
    echo "Error: bridge.py not found in $BRIDGE_DIR"
    echo "Run the main TinySignage installer first."
    exit 1
fi

if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Error: service user '$SERVICE_USER' does not exist."
    echo "Run the main TinySignage installer first."
    exit 1
fi

echo "Installing TinySignage GPIO Bridge..."

# --- System packages -------------------------------------------------------

echo "Installing system packages..."
apt-get install -y -qq python3-lgpio > /dev/null 2>&1
echo "  python3-lgpio installed (GPIO pin factory for Pi 5)."

# --- Python venv + dependencies --------------------------------------------

echo "Setting up Python venv..."
sudo -u "$SERVICE_USER" python3 -m venv --system-site-packages "$BRIDGE_DIR/venv"
sudo -u "$SERVICE_USER" "$BRIDGE_DIR/venv/bin/pip" install --quiet \
    gpiozero websockets pyyaml evdev
echo "  Dependencies installed."

# --- Groups for hardware access ---------------------------------------------

# gpio group — required for /dev/gpiochip* access (GPIO pins)
if getent group gpio &>/dev/null; then
    if ! id -nG "$SERVICE_USER" | grep -qw gpio; then
        usermod -aG gpio "$SERVICE_USER"
        echo "  Added '$SERVICE_USER' to 'gpio' group."
    else
        echo "  '$SERVICE_USER' already in 'gpio' group."
    fi
fi

# input group — required for /dev/input/event* access (joysticks/gamepads)
if ! getent group input &>/dev/null; then
    groupadd input
    echo "  Created 'input' group."
fi

if ! id -nG "$SERVICE_USER" | grep -qw input; then
    usermod -aG input "$SERVICE_USER"
    echo "  Added '$SERVICE_USER' to 'input' group."
else
    echo "  '$SERVICE_USER' already in 'input' group."
fi

# --- TLS cert access for WSS support ----------------------------------------

CERT_DIR="/opt/tinysignage/certs"
if [ -d "$CERT_DIR" ]; then
    # Ensure tinysignage user can read cert files
    chown "$SERVICE_USER":"$SERVICE_USER" "$CERT_DIR"/*.pem 2>/dev/null || true
    chmod 644 "$CERT_DIR/cert.pem" 2>/dev/null || true
    chmod 600 "$CERT_DIR/key.pem" 2>/dev/null || true
    echo "  Cert access verified for bridge TLS."
fi

# Enable TLS in bridge config if main server uses HTTPS
MAIN_CONFIG="/opt/tinysignage/config.yaml"
BRIDGE_CONFIG="$BRIDGE_DIR/config.yaml"
if [ -f "$MAIN_CONFIG" ] && grep -q 'enabled: true' "$MAIN_CONFIG" 2>/dev/null; then
    if grep -q 'tls:' "$BRIDGE_CONFIG" 2>/dev/null; then
        sed -i '/^tls:/{n;s/^  enabled: false/  enabled: true/}' "$BRIDGE_CONFIG"
        echo "  TLS enabled in bridge config (matching main server HTTPS)."
    fi
fi

# --- udev rule for /dev/input/event* access ---------------------------------

UDEV_LINE='KERNEL=="event*", SUBSYSTEM=="input", MODE="0664", GROUP="input"'

if [ -f "$UDEV_RULE" ] && grep -qF "$UDEV_LINE" "$UDEV_RULE"; then
    echo "  udev rule already in place."
else
    echo "$UDEV_LINE" > "$UDEV_RULE"
    udevadm control --reload-rules
    echo "  udev rule created at $UDEV_RULE"
fi

# --- systemd service --------------------------------------------------------

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=TinySignage GPIO Bridge
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$BRIDGE_DIR
ExecStart=$BRIDGE_DIR/venv/bin/python bridge.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable tinysignage-bridge
systemctl start tinysignage-bridge

echo "  systemd service enabled and started."

# --- Done -------------------------------------------------------------------

echo ""
echo "GPIO Bridge installed successfully."
echo "  Status:  sudo systemctl status tinysignage-bridge"
echo "  Logs:    journalctl -u tinysignage-bridge -f"
echo "  Config:  $BRIDGE_DIR/config.yaml"
echo ""
echo "If you changed joystick settings in config.yaml, restart with:"
echo "  sudo systemctl restart tinysignage-bridge"
