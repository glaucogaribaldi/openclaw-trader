# 🚀 TRE OS v5.5 • Autonomous Quantitative Trading OS for OKX Spot

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![OKX](https://img.shields.io/badge/Exchange-OKX%20Spot-emerald)
![License](https://img.shields.io/badge/License-MIT-purple)
![OpenClaw](https://img.shields.io/badge/Agent-OpenClaw-cyan)

**TRE OS v5.5** is an autonomous, high-frequency quantitative trading operating system designed for **OKX Spot (EEA Retail Account)** with zero leverage, zero liquidation risk, and zero taker fees.

---

## ⚡ 1-Click Copy-Paste Installation Command

Run this single command on any **Debian 12/13, Ubuntu, or macOS** machine to install the complete environment, dependencies, OKX CLI, web portal service, and cron daemon:

```bash
curl -fsSL https://raw.githubusercontent.com/glaucogaribaldi/openclaw-trader/main/install.sh | bash
```

---

## 🔑 Security Guarantee: Zero Keys Included

This repository contains **NO API keys, passwords, or secrets**. All configuration files use clean template files (`.example`) that you populate locally:

- `config/config.toml.example` ➔ `config/config.toml` (OKX API Credentials)
- `config/.env.example` ➔ `.env` (OpenRouter AI API Key)

---

## 🎯 Architecture & Key Features

### 1. High-Frequency 1-Minute Execution Engine (`watcher_daemon.py`)
- Runs every 60 seconds (`* * * * *`) via system cron.
- Dynamically scales compounding lot sizes based on total USDC equity.
- Preserves 25+ Limit Buy/Sell traps across **8 High-Beta Tokens**: `NEAR`, `LINK`, `SOL`, `SUI`, `RENDER`, `AVAX`, `FET`, `SEI`.
- Enforces **Maker-Only STP Mode** (`--stpMode cancel_maker`) to eliminate taker fees and slippage.

### 2. SQLite Ledger & Penny-Match Reconciliation (`okx_trader.db`)
- Append-only `trade_ledger` table records every fill with timestamp, price, fee, and realized PnL.
- Includes `rebuild_ledger.py` script for 100% accurate historical reconciliation against OKX Fills API.

### 3. 24/7 Cyberpunk Web Terminal Dashboard (`dashboard/`)
- Powered by Flask + Gunicorn on port **8080**.
- **Auto-refreshes every 20 minutes** (and on manual click).
- Displays live NAV Compounding Curve, Daily ROI % Benchmark meter, usable USDC cash, active traps, and CSV export buttons.

### 4. OpenRouter AI Co-Auditor (`openrouter_client.py`)
- Integrates with OpenRouter's free auto-router (`openrouter/free`).
- Performs secondary risk auditing, anomaly detection, and health checks at **zero API cost**.

---

## 🤖 OpenClaw Agent Integration

If you use **OpenClaw**, this package includes a pre-configured AgentSkill and Agent Persona:

1. Copy the skill folder to your OpenClaw workspace:
   ```bash
   cp -r skills/openclaw-trader ~/.openclaw/workspace/skills/
   ```
2. The agent (`Lehman Brody`) will automatically recognize the skill and allow you to monitor balances, audit fills, and trigger co-audit reports using natural language commands in WebChat or Telegram.

---

## 🛠️ Step-by-Step Manual Setup Guide

### Step 1: Clone Repository
```bash
git clone https://github.com/glaucogaribaldi/openclaw-trader.git
cd openclaw-trader
```

### Step 2: Configure Credentials
1. Copy the OKX configuration template and fill in your API Key, Secret, and Passphrase:
   ```bash
   cp config/config.toml.example config/config.toml
   nano config/config.toml
   ```
2. Copy the OpenRouter template and add your free key (from [OpenRouter Keys](https://openrouter.ai/keys)):
   ```bash
   cp config/.env.example .env
   nano .env
   ```

### Step 3: Launch Web Terminal & Enable Cron
```bash
# Activate Python Virtualenv
source venv/bin/activate

# Test Watcher Daemon
python scripts/watcher_daemon.py

# Launch Web Dashboard on Port 8080
gunicorn --bind 0.0.0.0:8080 --chdir dashboard app:app
```

---

## 📜 License & Compliance

MIT License. Designed for EEA Retail Compliance on OKX Spot Market (Zero Derivatives, Zero Margin, Zero Leverage).
