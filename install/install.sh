#!/bin/bash
# TinySignage — Full Install
# Runs system setup then app setup
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$(dirname "$SCRIPT_DIR")"
TARGET_DIR="/opt/tinysignage"
export INSTALL_DIR

echo "================================================"
echo "  TinySignage Installer"
echo "  Install directory: $INSTALL_DIR"
echo "================================================"
echo ""

# --- Display name prompt (also becomes the hostname) ---
echo "Give this display a name (e.g. \"Lobby TV\", \"Menu Board\")."
echo "This also sets the hostname so you can reach the CMS"
echo "from other devices (e.g. lobby-tv.local:8080/cms)."
echo ""
read -rp "Display Name [TinySignage]: " DISPLAY_NAME
DISPLAY_NAME="${DISPLAY_NAME:-TinySignage}"
export DISPLAY_NAME

# Sanitize display name into a valid hostname:
#   lowercase, replace spaces/underscores with hyphens,
#   strip anything that isn't alphanumeric or hyphen,
#   collapse multiple hyphens, trim leading/trailing hyphens,
#   truncate to 63 chars (DNS label limit)
SIGNAGE_HOSTNAME=$(echo "$DISPLAY_NAME" | tr '[:upper:]' '[:lower:]' | tr ' _' '-' | sed 's/[^a-z0-9-]//g; s/-\{2,\}/-/g; s/^-//; s/-$//' | cut -c1-63)
# Fallback if sanitization produces an empty string
SIGNAGE_HOSTNAME="${SIGNAGE_HOSTNAME:-tinysignage}"
export SIGNAGE_HOSTNAME

echo "  Hostname: ${SIGNAGE_HOSTNAME}.local"
echo ""

# Step 1: System setup (requires root)
if [ "$EUID" -ne 0 ]; then
    echo "This installer needs sudo for system setup."
    sudo INSTALL_DIR="$INSTALL_DIR" SIGNAGE_HOSTNAME="$SIGNAGE_HOSTNAME" bash "$SCRIPT_DIR/01-system.sh"
else
    bash "$SCRIPT_DIR/01-system.sh"
fi

# 01-system.sh may have moved the directory to /opt/tinysignage
INSTALL_DIR="$TARGET_DIR"
SCRIPT_DIR="$TARGET_DIR/install"
export INSTALL_DIR

echo ""

# Step 2: App setup (as service user or current user)
if id "tinysignage" &>/dev/null; then
    sudo -u tinysignage INSTALL_DIR="$INSTALL_DIR" DISPLAY_NAME="$DISPLAY_NAME" SIGNAGE_HOSTNAME="$SIGNAGE_HOSTNAME" bash "$SCRIPT_DIR/02-app.sh"
else
    DISPLAY_NAME="$DISPLAY_NAME" SIGNAGE_HOSTNAME="$SIGNAGE_HOSTNAME" bash "$SCRIPT_DIR/02-app.sh"
fi

echo ""
echo "================================================"
echo "  Installation complete! Reboot to start:"
echo ""
echo "    sudo reboot"
echo ""
echo "  After reboot:"
echo "    CMS:    http://${SIGNAGE_HOSTNAME}.local:8080/cms"
echo "    Player: launches automatically on the display"
echo "================================================"
