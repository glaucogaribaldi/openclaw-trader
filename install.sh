#!/usr/bin/env bash
# ==============================================================================
# ⚡ TRE OS v12.0 (SOVEREIGN PREDATOR EDITION) — UNIVERSAL INSTALLER
# Zero hardcoded portfolio amounts or fixed expiration dates.
# Supports both Interactive Human Setup and Non-Interactive AI Agent Setup.
#
# Usage (Interactive Human):
#   bash install.sh
#
# Usage (AI Agent / Non-Interactive CLI):
#   bash install.sh --non-interactive --baseline-nav AUTO --expiry-iso NONE --chamber1-pct 63 --max-loss-bps -400
# ==============================================================================
set -euo pipefail

echo "======================================================================"
echo "  ⚡ TRE OS v12.0 SOVEREIGN PREDATOR — UNIVERSAL SYSTEM INSTALLER"
echo "======================================================================"

USER_HOME="${HOME}"
INSTALL_DIR="${INSTALL_DIR:-${USER_HOME}/openclaw-trader}"

echo "[1/6] Installing System Dependencies (Debian/Ubuntu/macOS)..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y git curl sqlite3 python3-pip python3-venv build-essential
elif command -v brew &> /dev/null; then
    brew install git curl sqlite3 python3 || true
fi

echo "[2/6] Cloning / Updating TRE OS v12.0 Repository..."
if [ ! -d "${INSTALL_DIR}/.git" ]; then
    git clone https://github.com/glaucogaribaldi/openclaw-trader.git "${INSTALL_DIR}"
else
    git -C "${INSTALL_DIR}" pull --ff-only || true
fi

echo "[3/6] Setting up Python Virtual Environment & Dependencies..."
mkdir -p "${INSTALL_DIR}/config" "${INSTALL_DIR}/exports" "${INSTALL_DIR}/logs"
cd "${INSTALL_DIR}"
python3 -m venv venv
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt flask gunicorn requests python-dotenv gspread certifi -q

echo "[4/6] Initializing Clean Credentials Templates (Zero Keys Included)..."
mkdir -p "${USER_HOME}/.okx"
if [ ! -f "config/config.toml" ] && [ -f "config/config.toml.example" ]; then
    cp config/config.toml.example config/config.toml
fi
if [ ! -f ".env" ] && [ -f "config/.env.example" ]; then
    cp config/.env.example .env
    chmod 600 .env
fi

echo "[5/6] Running Portfolio, Expiration Date & Risk Calibration Wizard..."
if [ "$#" -gt 0 ]; then
    ./venv/bin/python scripts/configure_run.py "$@"
elif [ ! -f "config/purified_run_config.json" ]; then
    ./venv/bin/python scripts/configure_run.py
else
    echo "  • Existing config/purified_run_config.json detected (run ' ./venv/bin/python scripts/configure_run.py ' to recalibrate)."
fi

echo "[6/6] Configuring systemd Services (Linux VPS)..."
if command -v systemctl &> /dev/null && [[ "$(uname -s)" == "Linux" ]]; then
    sudo tee /etc/systemd/system/openclaw-predator.service >/dev/null <<EOF
[Unit]
Description=TRE OS v12.0 Sovereign Predator — Autonomous Quant Daemon (OKX Spot EEA)
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
    sudo systemctl enable openclaw-predator.service || true
fi

echo "======================================================================"
echo "  ✅ TRE OS v12.0 INSTALLATION COMPLETE!"
echo "  Next steps:"
echo "  1) Add your OKX Spot EEA & Free AI keys into: ${INSTALL_DIR}/.env"
echo "  2) Install the local 5-Horizon Kronos Foundation Model Oracle:"
echo "       bash ${INSTALL_DIR}/scripts/install_kronos_oracle.sh --size mini"
echo "  3) Snapshot your starting wallet balance & launch:"
echo "       ${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/predator_daemon.py --once --live --init-purified-run"
echo "       sudo systemctl restart openclaw-predator.service"
echo "  📖 AI Agent Installer Manual: ${INSTALL_DIR}/AI_INSTALLER_GUIDE.md"
echo "======================================================================"
