#!/bin/bash
# TinySignage — Full Install
# Runs system setup then app setup
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$(dirname "$SCRIPT_DIR")"
export INSTALL_DIR

echo "================================================"
echo "  TinySignage Installer"
echo "  Install directory: $INSTALL_DIR"
echo "================================================"
echo ""

# Step 1: System setup (requires root)
if [ "$EUID" -ne 0 ]; then
    echo "This installer needs sudo for system setup."
    sudo INSTALL_DIR="$INSTALL_DIR" bash "$SCRIPT_DIR/01-system.sh"
else
    bash "$SCRIPT_DIR/01-system.sh"
fi

echo ""

# Step 2: App setup (as service user or current user)
if id "tinysignage" &>/dev/null; then
    sudo -u tinysignage INSTALL_DIR="$INSTALL_DIR" bash "$SCRIPT_DIR/02-app.sh"
else
    bash "$SCRIPT_DIR/02-app.sh"
fi

echo ""
echo "================================================"
echo "  Installation complete!"
echo "  Open http://tinysignage.local:8080/cms"
echo "================================================"
