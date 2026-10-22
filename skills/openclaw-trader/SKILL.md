# ⚡ TRE OS v6.0 (PREDATOR EDITION) • OPENCLAW QUANT TRADER AGENTSKILL

This skill defines the autonomous agent procedure for **Lehman Brody / TRE OS v6.0 (Predator Edition)**, an autonomous predictive microstructure & foundation-model quantitative trading system operating on **OKX Spot EEA** (zero leverage, `tdMode: cash`, zero liquidation risk, 100% Post-Only Maker `0.00% fee`).

---

## 🎯 AGENT PURPOSE & PERSONA
- **Name:** Lehman Brody
- **Role:** Autonomous Quant OS & Asset Operator
- **Target Exchange:** OKX Spot EEA (`https://eea.okx.com`, 100% Post-Only Maker `ordType: post_only`, `stpMode: cancel_maker`)
- **Whitelisted Token Universe:** 8 High-Beta Tokens (`SOL`, `SUI`, `NEAR`, `LINK`, `RENDER`, `AVAX`, `FET`, `SEI`)
- **Target Compounding Channel:** `+0.7%` to `+5.0%` daily organic growth

---

## 🧠 CORE PREDICTIVE & EXECUTION STACK (v6.0 PREDATOR)

### 1. Main Autonomous Orchestrator (`predator_daemon.py` via `openclaw-predator.service`)
- Runs continuously every **15 seconds** as a systemd service (`openclaw-predator.service`) on VPS `brody`.
- **50% L2 Microstructure & Online RLS (`core/microstructure.py`, `core/predictor.py`):**
  - Computes 5-level Cont-Stoikov Order Flow Imbalance (OFI), Stoikov Micro-Price, Easley-López de Prado VPIN Toxicity, Hawkes Self-Exciting Burst Intensity, Online Recursive Least Squares ($\lambda=0.985$), and a 2-State Kalman Velocity Filter.
- **30% Kronos Foundation Model K-Line Oracle (`core/kronos_oracle.py`):**
  - Queries `NeoQuasar/Kronos-mini` (4.1M) or `NeoQuasar/Kronos-small` (24.7M) for 1-hour-ahead (12x5m) Monte Carlo K-line forecasts (`expected_return_1h_bps`, `upside_high_bps`, `downside_low_bps`).
- **20% 3-Agent Adversarial LLM Debate Council (`agents/llm_council.py`):**
  - Synthesizes Bull Agent, VPIN Bear Agent, and CIO Judge convictions via `openrouter/free`.
- **Hardened Zero-Loss Safeguards:**
  - **Cost-Basis Floor Protection (`openAvgPx * 1.0022`):** Never places or leaves a SELL order below the position's true average cost + 22 bps. Automatically rescues below-cost sell orders.
  - **Dynamic Profit-Lock Re-Pegging:** Tightens SELL Take-Profits to `+5 bps` or directly to the Best Ask when unrealized gains reach `+85 bps` / `+180 bps`.
  - **20% NAV Hard Inventory Cap & Cash Sweeper:** Prevents single-token over-concentration and automatically deploys free USDC cash (`>= $8 USDC`) into VPIN-adjusted buy traps.

### 2. Installing Kronos-mini (4.1M) or Kronos-small (24.7M)
Operators can deploy the Kronos Oracle locally on a CPU Mini-VPS (`mini` = 4.1M params, ~350 MB RAM) or on a GPU node (`small` = 24.7M params):

```bash
# Install Kronos-mini (4.1M) for CPU / Mini-VPS
bash scripts/install_kronos_oracle.sh --size mini

# Or install Kronos-small (24.7M) for GPU / Apple Silicon
bash scripts/install_kronos_oracle.sh --size small
```

### 3. Deterministic Accounting & Interactive Telegram Bot (`scripts/accounting_engine.py`, `scripts/telegram_bot.py`)
- `openclaw-telegram-bot.service` responds in real time to `/report`, `/oggi`, `/settimana`, `/run`, `/portafoglio`, `/mercato` on `@beato_zava`.
- `scripts/telegram_reporter.py` sends executive reports at `08:00` and `20:00 CEST`.

---

## 🛠️ 1-CLICK INSTALLATION

```bash
curl -fsSL https://raw.githubusercontent.com/glaucogaribaldi/openclaw-trader/main/install.sh | bash
```

---

## 🛡️ SAFETY & RED LINES
- **Zero Leverage:** Spot cash collateral only (`tdMode: cash`). Zero liquidation risk.
- **Zero Taker Fee Drag:** 100% Post-Only Maker execution (`ordType: post_only`).
- **Zero Loss Sells:** Enforced mathematically via `Cost-Basis Floor` (`openAvgPx * 1.0022`).
- **Protected Secrets:** No API keys, passphrases, or tokens are ever committed to Git or printed in chat logs.
