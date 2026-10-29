#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# TRE OS v6.0 (Predator Edition) — 1-Click Kronos Oracle Installer
# Installs NeoQuasar/Kronos-mini (4.1M, CPU/Mini-VPS friendly) or
# NeoQuasar/Kronos-small (24.7M, GPU/Apple Silicon) on port 8090.
# Usage:
#   bash scripts/install_kronos_oracle.sh --size mini
#   bash scripts/install_kronos_oracle.sh --size small
# ============================================================================

KRONOS_SIZE="mini"
KRONOS_PORT="8090"
KRONOS_DIR="${HOME}/Kronos"
TRADER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --size)
      KRONOS_SIZE="$2"
      shift 2
      ;;
    --port)
      KRONOS_PORT="$2"
      shift 2
      ;;
    --dir)
      KRONOS_DIR="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

echo "=================================================================="
echo "🧠 Installing Kronos Foundation Model Oracle (Tier: ${KRONOS_SIZE})"
echo "=================================================================="

if [[ ! -d "${KRONOS_DIR}" ]]; then
  echo "[1/4] Cloning shiyu-coder/Kronos repository into ${KRONOS_DIR}..."
  git clone --depth 1 https://github.com/shiyu-coder/Kronos.git "${KRONOS_DIR}"
else
  echo "[1/4] Updating existing Kronos repository at ${KRONOS_DIR}..."
  git -C "${KRONOS_DIR}" pull --ff-only || true
fi

echo "[2/4] Creating Python virtual environment and installing dependencies..."
python3 -m venv "${KRONOS_DIR}/venv"
"${KRONOS_DIR}/venv/bin/pip" install --upgrade pip -q
"${KRONOS_DIR}/venv/bin/pip" install torch numpy pandas huggingface_hub safetensors tqdm einops -q

echo "[3/4] Copying universal Kronos Oracle server script..."
cp "${TRADER_DIR}/scripts/kronos_oracle_server.py" "${KRONOS_DIR}/kronos_oracle_server.py"
chmod +x "${KRONOS_DIR}/kronos_oracle_server.py"

echo "[4/4] Pre-downloading HuggingFace weights for Kronos-${KRONOS_SIZE}..."
"${KRONOS_DIR}/venv/bin/python" -c "
import sys
sys.path.insert(0, '${KRONOS_DIR}')
from model import Kronos, KronosTokenizer
size = '${KRONOS_SIZE}'
tok_id = 'NeoQuasar/Kronos-Tokenizer-2k' if size == 'mini' else 'NeoQuasar/Kronos-Tokenizer-base'
mod_id = f'NeoQuasar/Kronos-{size}'
print(f'Downloading {tok_id} & {mod_id}...')
KronosTokenizer.from_pretrained(tok_id)
Kronos.from_pretrained(mod_id)
print('Model weights cached successfully!')
"

if command -v systemctl >/dev/null 2>&1 && [[ "$(uname -s)" == "Linux" ]]; then
  echo "[+] Configuring systemd unit kronos-oracle.service..."
  sudo tee /etc/systemd/system/kronos-oracle.service >/dev/null <<EOF
[Unit]
Description=TRE OS v6.0 Kronos-${KRONOS_SIZE} Foundation Model Oracle Server
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${KRONOS_DIR}
Environment="KRONOS_SIZE=${KRONOS_SIZE}"
Environment="KRONOS_PORT=${KRONOS_PORT}"
Environment="KRONOS_REPO_DIR=${KRONOS_DIR}"
ExecStart=${KRONOS_DIR}/venv/bin/python ${KRONOS_DIR}/kronos_oracle_server.py --size ${KRONOS_SIZE} --port ${KRONOS_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable --now kronos-oracle.service
  echo "[+] kronos-oracle.service started on port ${KRONOS_PORT}!"
else
  echo "[+] To start the Kronos Oracle server manually on macOS/Linux:"
  echo "    ${KRONOS_DIR}/venv/bin/python ${KRONOS_DIR}/kronos_oracle_server.py --size ${KRONOS_SIZE} --port ${KRONOS_PORT}"
fi

echo "=================================================================="
echo "✅ Kronos-${KRONOS_SIZE} Oracle Ready! Endpoint: http://127.0.0.1:${KRONOS_PORT}/forecast?pairs=SOL-USDC"
echo "=================================================================="
