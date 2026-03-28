#!/bin/bash
# TinySignage — System Setup
# Installs packages, creates service user, sets up systemd and kiosk mode
set -e

echo "=== TinySignage System Setup ==="

# Must be run as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run with: sudo bash install/01-system.sh"
    exit 1
fi

INSTALL_DIR="${INSTALL_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SERVICE_USER="tinysignage"

# --- System packages ---
echo "[1/5] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-venv python3-pip \
    chromium-browser \
    ffmpeg \
    avahi-daemon \
    curl \
    > /dev/null

# --- Service user ---
echo "[2/5] Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --create-home --shell /bin/bash "$SERVICE_USER"
    # Add to video group for GPU access
    usermod -aG video "$SERVICE_USER"
fi

# --- mDNS ---
echo "[3/5] Configuring mDNS (tinysignage.local)..."
if [ -d /etc/avahi ]; then
    systemctl enable avahi-daemon
    systemctl start avahi-daemon
fi

# --- Systemd units ---
echo "[4/5] Installing systemd units..."
cp "$INSTALL_DIR/systemd/signage-app.service" /etc/systemd/system/
cp "$INSTALL_DIR/systemd/signage-player.service" /etc/systemd/system/

# Update paths
sed -i "s|/home/pi/TinySignage|$INSTALL_DIR|g" /etc/systemd/system/signage-app.service
sed -i "s|/home/pi/TinySignage|$INSTALL_DIR|g" /etc/systemd/system/signage-player.service
sed -i "s|User=pi|User=$SERVICE_USER|g" /etc/systemd/system/signage-app.service
sed -i "s|User=pi|User=$SERVICE_USER|g" /etc/systemd/system/signage-player.service

# Set ownership
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

systemctl daemon-reload
systemctl enable signage-app signage-player

# --- Kiosk mode (Pi) ---
echo "[5/5] Checking kiosk mode..."
if [ -f /boot/config.txt ] || [ -f /boot/firmware/config.txt ]; then
    CONFIG_FILE="/boot/config.txt"
    [ -f /boot/firmware/config.txt ] && CONFIG_FILE="/boot/firmware/config.txt"
    if ! grep -q "gpu_mem=128" "$CONFIG_FILE"; then
        echo "gpu_mem=128" >> "$CONFIG_FILE"
        echo "  GPU memory set to 128MB (reboot required)"
    fi
fi

echo ""
echo "System setup complete. Run install/02-app.sh next."
