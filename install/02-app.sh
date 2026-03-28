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
echo "[2/4] Installing Python dependencies..."
pip install --quiet -r requirements.txt

# --- Directories ---
echo "[3/4] Creating directories..."
mkdir -p media media/thumbs db

# --- Config ---
echo "[4/4] Configuring..."
if [ ! -f config.yaml ]; then
    cp config.yaml.example config.yaml 2>/dev/null || true
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
echo ""
echo "Start manually:"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --host 0.0.0.0 --port 8080"
echo ""
echo "Or via systemd:"
echo "  sudo systemctl start signage-app"
echo "  sudo systemctl start signage-player"
echo ""
echo "Open: http://localhost:8080/cms"
