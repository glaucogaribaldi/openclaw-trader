#!/usr/bin/env bash
# TRE OS v5.5 - Automated 1-Click Installer
# High-Frequency Quantitative Trading Engine for OKX Spot
set -e

echo "==============================================================="
echo "  TRE OS v5.5 - AUTOMATED 1-CLICK SYSTEM INSTALLER"
echo "==============================================================="

# Detect OS & User
USER_HOME=$HOME
INSTALL_DIR="$USER_HOME/openclaw-trader"

echo "[1/5] Installing System Dependencies (Debian/Ubuntu/macOS)..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y git curl sqlite3 python3-pip python3-venv nodejs npm build-essential
elif command -v brew &> /dev/null; then
    brew install git curl sqlite3 python3 node npm
fi

echo "[2/5] Installing OKX Trade CLI..."
sudo npm install -g @okx_ai/okx-trade-cli

echo "[3/5] Setting up Python Environment..."
mkdir -p "$INSTALL_DIR/config" "$INSTALL_DIR/exports" "$INSTALL_DIR/memory" "$INSTALL_DIR/dashboard/templates"
cd "$INSTALL_DIR"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt flask gunicorn requests python-dotenv

echo "[4/5] Creating Configuration Templates (Zero Keys Included)..."
if [ ! -f "config/config.toml" ]; then
    cp config/config.toml.example config/config.toml 2>/dev/null || true
fi
if [ ! -f ".env" ]; then
    cp config/.env.example .env 2>/dev/null || true
fi

echo "[5/5] Setting up Systemd Web Dashboard & 1-Minute Cron Daemon..."
# Setup Cron
(crontab -l 2>/dev/null | grep -v "watcher_daemon.py"; echo "PATH=/usr/local/bin:/usr/bin:/bin"; echo "* * * * * $INSTALL_DIR/venv/bin/python $INSTALL_DIR/scripts/watcher_daemon.py >> $INSTALL_DIR/memory/watcher.log 2>&1") | crontab -

echo "==============================================================="
echo "  INSTALLATION COMPLETE 100%!"
echo "  To start the Web Dashboard: $INSTALL_DIR/venv/bin/gunicorn --bind 0.0.0.0:8080 --chdir $INSTALL_DIR/dashboard app:app"
echo "==============================================================="
