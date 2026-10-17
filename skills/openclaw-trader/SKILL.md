# 📈 TRE OS v5.6 • OPENCLAW QUANT TRADER AGENTSKILL

This skill defines the autonomous agent procedure for **Lehman Brody / TRE OS v5.6**, an autonomous quantitative trading and risk management system operating on **OKX Spot** (zero leverage, zero liquidation risk, EEA compliant).

---

## 🎯 AGENT PURPOSE & PERSONA
- **Name:** Lehman Brody
- **Role:** Autonomous Quant OS & Asset Operator
- **Target Exchange:** OKX Spot (Maker-Only Post-Only `--stpMode cancel_maker`)
- **Whitelisted Token Universe:** 8 High-Beta Tokens (`NEAR`, `LINK`, `SOL`, `SUI`, `RENDER`, `AVAX`, `FET`, `SEI`)
- **Target Compounding Channel:** `+0.7%` to `+5.0%` daily organic growth

---

## 💰 MANDATORY STEP: OKX SIMPLE EARN 1-CLICK ACTIVATION

To enable the autonomous yield module (`scripts/okx_earn_helper.py`) to track and generate **10.0% APR passive interest** on unallocated USDC cash, the operator **MUST PERFORM A ONE-TIME 1-CLICK ACTIVATION** on OKX:

1. Open OKX Web (`my.okx.com`) ➔ Menu **Earn** ➔ **Simple Earn**.
2. Search for **USDC** and click **Subscribe / Flexible (Flessibile)**.
3. Enter amount (e.g. `1 USDC` or click `Max`), check *"I have read and agree to Margin Rewards User Agreement"*, and click **Subscribe**.
4. Enable **"Auto-subscribe"** on the confirmation screen.

*Once confirmed once via browser, OKX unlocks the user agreement authorization and the API tracks all idle cash yield automatically.*

---

## 🚀 CORE CAPABILITIES & WORKFLOWS

### 1. Multi-Microstructure Execution Engine (`scripts/watcher_daemon.py`)
- Runs every 60 seconds via Linux `crontab` (`* * * * *`).
- **Avellaneda-Stoikov Inventory Skew ($q_{\text{skew}}$):** Dynamically skews buy offsets and sell Take-Profits based on token holding weight in NAV.
- **Event-Driven AI Triggers:** Automatically triggers background OpenRouter AI calls (`--trigger FILL_<coin>`) on every buy/sell trade fill to adapt micro-tactics instantly.
- **Cash-Aware Lot Sizing:** Automatically caps order sizes to available free USDC cash to prevent balance errors.
- **Order Book Imbalance (OBI Alpha) & LOB Micro-Depth:** Reads top 10 orderbook bid/ask volumes to adjust dip traps and expand Moonbag Take-Profits (+5.10%).

### 2. Hourly AI Steering Co-Pilot (`scripts/hourly_ai_steer.py`)
- Runs every hour (`0 * * * *`) via Linux `crontab`.
- Queries OpenRouter AI (`openrouter/free`) for an hourly strategic directive analyzing 1h price trends, volume surges, and market inclination.
- Writes directives to `config/ai_hourly_directive.json` for real-time daemon parameter tuning.

### 3. Daily 24h AI Audit & Google Sheets Sync (`scripts/daily_openrouter_sync.py`)
- Runs every midnight (`0 0 * * *`) via Linux `crontab`.
- Queries OpenRouter AI (`openrouter/free`) to generate a 24-hour performance & risk evaluation.
- Updates the official Google Sheet (`1gNr4yEpdynK4juTIzG5m5AJ365y8E5MzZ33AEDaUjwU`) and commits the report to `docs/RUN_REPORT.md` on GitHub.

### 4. Interactive On-Demand AI Auditor (`scripts/nemotron_client.py`)
- Queries Nemotron 3.5 Lightning (32.9B parameter MoE GGUF) on the AI VPS GPU (`100.125.189.103:11434`) when explicitly requested in chat by the operator.

### 5. Web Terminal Dashboard (`dashboard/app.py`)
- Modern, dark OpenTerminal-style web dashboard running on port 8080 (`http://100.106.15.28:8080/`).
- Features a 20-minute auto-refresh countdown timer, live Chart.js NAV curve, high-density order/fill tables, one-click CSV exports, and an integrated OpenRouter AI Chat drawer panel (`/api/chat`).

---

## 🛠️ 1-CLICK INSTALLATION & DEPLOYMENT

To deploy this agent on any fresh Debian 12/13 or Ubuntu VPS:

```bash
curl -fsSL https://raw.githubusercontent.com/glaucogaribaldi/openclaw-trader/main/install.sh | bash
```

### Configuration Setup (Zero Keys in Repository)
Copy the example templates and insert your credentials:

```bash
cp config/config.toml.example ~/.okx/config.toml
cp config/.env.example .env
chmod 600 .env ~/.okx/config.toml
```

---

## 🛡️ SAFETY & RED LINES
- **Zero Leverage:** Spot cash collateral only (`tdMode: cash`). Zero liquidation risk.
- **Zero Taker Fee Drag:** Maker-Only Post-Only mode (`--stpMode cancel_maker`).
- **Protected Secrets:** No API keys, passphrases, or tokens are ever committed to Git or printed in chat logs.
