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
TARGET_DIR="/opt/tinysignage"
SERVICE_USER="tinysignage"

# --- Move to /opt if cloned inside a user's home directory ---
if [ "$INSTALL_DIR" != "$TARGET_DIR" ]; then
    echo "Moving install from $INSTALL_DIR to $TARGET_DIR..."
    if [ -d "$TARGET_DIR" ]; then
        echo "  $TARGET_DIR already exists — removing old copy"
        rm -rf "$TARGET_DIR"
    fi
    mv "$INSTALL_DIR" "$TARGET_DIR"
    INSTALL_DIR="$TARGET_DIR"
    echo "  Done. Install directory is now $INSTALL_DIR"
fi

# --- Detect Pi OS Lite (no desktop environment) ---
IS_LITE=false
if command -v systemctl &>/dev/null; then
    if systemctl get-default 2>/dev/null | grep -q "multi-user.target"; then
        IS_LITE=true
    fi
fi

# --- System packages ---
echo "[1/5] Installing system packages..."
apt-get update -qq
PACKAGES="git python3 python3-venv python3-pip nodejs npm chromium ffmpeg avahi-daemon curl"
if [ "$IS_LITE" = true ]; then
    echo "  Detected Pi OS Lite — will install kiosk compositor (cage)"
    # xwayland is required due to cage 0.1.4 bug (Bookworm) — it crashes
    # without Xwayland binary even for Wayland-native apps (fixed in 0.1.5+)
    PACKAGES="$PACKAGES cage xwayland"
fi
apt-get install -y -qq $PACKAGES > /dev/null

# --- Service user ---
echo "[2/5] Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --create-home --shell /bin/bash "$SERVICE_USER"
    # Add to video group for GPU access
    usermod -aG video "$SERVICE_USER"
fi
if [ "$IS_LITE" = true ]; then
    # cage needs access to display and input devices
    usermod -aG input,render "$SERVICE_USER"
fi

# --- Hostname & mDNS ---
echo "[3/5] Configuring hostname and mDNS..."
if [ -n "$SIGNAGE_HOSTNAME" ]; then
    CURRENT_HOSTNAME=$(hostname)
    if [ "$SIGNAGE_HOSTNAME" != "$CURRENT_HOSTNAME" ]; then
        hostnamectl set-hostname "$SIGNAGE_HOSTNAME"
        # Update /etc/hosts so sudo doesn't complain about unresolvable hostname
        if grep -q "127.0.1.1.*$CURRENT_HOSTNAME" /etc/hosts; then
            sed -i "s/127.0.1.1.*$CURRENT_HOSTNAME.*/127.0.1.1\t$SIGNAGE_HOSTNAME/" /etc/hosts
        else
            echo -e "127.0.1.1\t$SIGNAGE_HOSTNAME" >> /etc/hosts
        fi
        echo "  Hostname set to: $SIGNAGE_HOSTNAME"
    else
        echo "  Hostname already set to: $SIGNAGE_HOSTNAME"
    fi
fi
if [ -d /etc/avahi ]; then
    systemctl enable avahi-daemon
    systemctl start avahi-daemon
    echo "  mDNS enabled — reachable at ${SIGNAGE_HOSTNAME:-$(hostname)}.local"
fi

# --- Systemd units ---
echo "[4/5] Installing systemd units..."
cp "$INSTALL_DIR/systemd/signage-app.service" /etc/systemd/system/

# Pick the right player service for Lite vs Desktop
if [ "$IS_LITE" = true ]; then
    echo "  Using Lite kiosk service (cage + Chromium)"
    cp "$INSTALL_DIR/systemd/signage-player-lite.service" /etc/systemd/system/signage-player.service
else
    cp "$INSTALL_DIR/systemd/signage-player.service" /etc/systemd/system/signage-player.service
fi

# Update paths
sed -i "s|/home/pi/TinySignage|$INSTALL_DIR|g" /etc/systemd/system/signage-app.service
sed -i "s|/home/pi/TinySignage|$INSTALL_DIR|g" /etc/systemd/system/signage-player.service
sed -i "s|User=pi|User=$SERVICE_USER|g" /etc/systemd/system/signage-app.service
sed -i "s|User=pi|User=$SERVICE_USER|g" /etc/systemd/system/signage-player.service

# Set ownership
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

systemctl daemon-reload
systemctl enable signage-app signage-player

# --- Transparent cursor theme (hides mouse pointer in kiosk mode) ---
echo "[5/6] Installing transparent cursor theme..."
CURSOR_DIR="/usr/share/icons/hidden/cursors"
mkdir -p "$CURSOR_DIR"
python3 "$INSTALL_DIR/install/create_hidden_cursors.py" "$CURSOR_DIR"
tee /usr/share/icons/hidden/index.theme > /dev/null <<THEME
[Icon Theme]
Name=Hidden
Comment=Transparent cursor theme for kiosk mode
THEME
echo "  Transparent cursor theme installed"

# Set cursor theme in labwc environment (Pi OS Desktop with Wayland)
if command -v labwc &>/dev/null; then
    SIGNAGE_HOME=$(eval echo "~$SERVICE_USER")
    LABWC_ENV="$SIGNAGE_HOME/.config/labwc/environment"
    mkdir -p "$(dirname "$LABWC_ENV")"
    grep -q 'XCURSOR_THEME' "$LABWC_ENV" 2>/dev/null || {
        echo 'XCURSOR_THEME=hidden' >> "$LABWC_ENV"
        echo 'XCURSOR_SIZE=1' >> "$LABWC_ENV"
    }
    chown -R "$SERVICE_USER:$SERVICE_USER" "$SIGNAGE_HOME/.config/labwc"
    echo "  labwc cursor environment configured"
fi

# --- Kiosk mode (Pi) ---
echo "[6/6] Checking kiosk mode..."
if [ -f /boot/config.txt ] || [ -f /boot/firmware/config.txt ]; then
    CONFIG_FILE="/boot/config.txt"
    [ -f /boot/firmware/config.txt ] && CONFIG_FILE="/boot/firmware/config.txt"
    if ! grep -q "gpu_mem=128" "$CONFIG_FILE"; then
        echo "gpu_mem=128" >> "$CONFIG_FILE"
        echo "  GPU memory set to 128MB (reboot required)"
    fi

    # Enable hardware watchdog — auto-reboots Pi on kernel panic or OS freeze
    if ! grep -q "dtparam=watchdog=on" "$CONFIG_FILE"; then
        echo "dtparam=watchdog=on" >> "$CONFIG_FILE"
        echo "  Hardware watchdog enabled (reboot required)"
    fi
fi

# --- Hardware watchdog (systemd integration) ---
# RuntimeWatchdogSec tells systemd to pet the hardware watchdog.
# If systemd itself hangs, the hardware watchdog reboots the Pi.
if [ -f /etc/systemd/system.conf ]; then
    if ! grep -q "^RuntimeWatchdogSec=" /etc/systemd/system.conf; then
        sed -i 's/^#RuntimeWatchdogSec=.*/RuntimeWatchdogSec=14/' /etc/systemd/system.conf
        echo "  systemd hardware watchdog integration enabled (14s timeout)"
    fi
fi

echo ""
echo "System setup complete."
echo "  If running manually: sudo -u tinysignage bash install/02-app.sh"
