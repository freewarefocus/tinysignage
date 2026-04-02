#!/bin/bash
# TinySignage — App Setup
# Creates venv, installs dependencies, generates config, initializes database
set -e

echo "=== TinySignage App Setup ==="

INSTALL_DIR="${INSTALL_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$INSTALL_DIR"

# --- Python venv ---
echo "[1/4] Creating virtual environment..."
PYTHON=$(command -v python3.11 || command -v python3)
if [ -z "$PYTHON" ]; then
    echo "Error: Python 3 not found"
    exit 1
fi
$PYTHON -m venv venv
source venv/bin/activate

# --- Dependencies ---
echo "[2/5] Installing Python dependencies..."
pip install --quiet -r requirements.txt

# --- Build CMS ---
echo "[3/5] Building CMS..."
cd "$INSTALL_DIR/cms"
npm install --silent
npm run build
cd "$INSTALL_DIR"

# --- Directories ---
echo "[4/5] Creating directories..."
mkdir -p media media/thumbs db logs

# --- Config ---
echo "[5/5] Configuring..."
if [ ! -f config.yaml ]; then
    echo "  Error: config.yaml not found in repo"
    exit 1
fi

# Player configuration — display name and hostname are inherited from install.sh
# server_url is localhost because the player runs on the Pi itself
DISPLAY_NAME="${DISPLAY_NAME:-New Display}"
SERVER_URL="http://localhost:8080"

# Write player settings to config.yaml
if [ -n "$SERVER_URL" ]; then
    SERVER_URL="$SERVER_URL" DISPLAY_NAME="$DISPLAY_NAME" python3 -c "
import os, yaml
from pathlib import Path
p = Path('config.yaml')
c = yaml.safe_load(p.read_text())
c['server_url'] = os.environ['SERVER_URL']
c['display_name'] = os.environ['DISPLAY_NAME']
p.write_text(yaml.dump(c, default_flow_style=False, sort_keys=False))
"
    echo "  Wrote server_url, display_name to config.yaml"
fi

# Generate SECRET_KEY if config.env doesn't exist
if [ ! -f config.env ]; then
    SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
    cat > config.env <<EOF
# TinySignage environment config (auto-generated)
SECRET_KEY=$SECRET_KEY
EOF
    echo "  Generated config.env with SECRET_KEY"
fi

# Init database
echo "  Initializing database..."
python3 -c "
import asyncio
from app.database import init_db, engine

async def setup():
    await init_db()
    await engine.dispose()

asyncio.run(setup())
"

echo ""
echo "=== App setup complete ==="
