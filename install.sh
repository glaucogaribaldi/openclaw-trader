#!/usr/bin/env bash
# TRE OS v6.0 (Predator Edition) — Automated 1-Click Installer
# Predictive Microstructure + Kronos Foundation Model Oracle for OKX Spot EEA
set -euo pipefail

echo "==============================================================="
echo "  ⚡ TRE OS v6.0 PREDATOR EDITION — 1-CLICK SYSTEM INSTALLER"
echo "==============================================================="

USER_HOME="${HOME}"
INSTALL_DIR="${USER_HOME}/openclaw-trader"

echo "[1/5] Installing System Dependencies (Debian/Ubuntu/macOS)..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y git curl sqlite3 python3-pip python3-venv build-essential
elif command -v brew &> /dev/null; then
    brew install git curl sqlite3 python3
fi

echo "[2/5] Cloning / Updating TRE OS v6.0 Repository..."
if [ ! -d "${INSTALL_DIR}/.git" ]; then
    git clone https://github.com/glaucogaribaldi/openclaw-trader.git "${INSTALL_DIR}"
else
    git -C "${INSTALL_DIR}" pull --ff-only || true
fi

echo "[3/5] Setting up Python Virtual Environment..."
mkdir -p "${INSTALL_DIR}/config" "${INSTALL_DIR}/exports" "${INSTALL_DIR}/memory" "${INSTALL_DIR}/dashboard/templates"
cd "${INSTALL_DIR}"
python3 -m venv venv
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt flask gunicorn requests python-dotenv gspread certifi -q

echo "[4/5] Creating Clean Configuration Templates (Zero Keys Included)..."
mkdir -p "${USER_HOME}/.okx"
if [ ! -f "config/config.toml" ]; then
    cp config/config.toml.example config/config.toml 2>/dev/null || true
fi
if [ ! -f ".env" ]; then
    cp config/.env.example .env 2>/dev/null || true
fi

echo "[5/5] Configuring TRE OS v6.0 Predator Service & Scheduled Reporters..."
if command -v systemctl &> /dev/null && [[ "$(uname -s)" == "Linux" ]]; then
    sudo tee /etc/systemd/system/openclaw-predator.service >/dev/null <<EOF
[Unit]
Description=TRE OS v6.0 Predator Edition — Live Production Quant Daemon (OKX Spot EEA)
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/predator_daemon.py --live --interval 15
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable --now openclaw-predator.service || true
fi

# Clean legacy watcher_daemon.py from crontab and keep only scheduled audits/reporters
(crontab -l 2>/dev/null | grep -v "watcher_daemon.py" | grep -v "predator_reporter.py" || true) | crontab -

echo "==============================================================="
echo "  ✅ TRE OS v6.0 PREDATOR INSTALLATION COMPLETE!"
echo "  • Main Daemon: predator_daemon.py --live --interval 15"
echo "  • Optional Kronos-mini (4.1M) / Kronos-small (24.7M) Oracle:"
echo "      bash ${INSTALL_DIR}/scripts/install_kronos_oracle.sh --size mini"
echo "      bash ${INSTALL_DIR}/scripts/install_kronos_oracle.sh --size small"
echo "==============================================================="
