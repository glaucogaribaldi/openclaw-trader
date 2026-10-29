# ⚡ TRE OS v12.0 (SOVEREIGN PREDATOR EDITION) • 5-HORIZON KRONOS FOUNDATION MODEL + DUAL FREE AI COUNCIL QUANT OS (OKX SPOT EEA)

**TRE OS v12.0 — Sovereign Predator Edition** (`openclaw-trader`) is an autonomous quantitative trading operating system for **OKX Spot (`tdMode: cash`, zero leverage, `0.00%` liquidation risk, `100% Post-Only Maker` execution `ordType: post_only`, `stpMode: cancel_maker`)**.

It combines:
1. **Local 5-Horizon Tsinghua Kronos Foundation Model (`kronos-oracle.service` on `127.0.0.1:8090`):**
   - Runs `NeoQuasar/Kronos-mini (4.1M)` locally in RAM (`0.2 ms` HTTP lookup) and computes 5 simultaneous price trajectory horizons for every asset: **`1h` (`12×5m`), `2h` (`8×15m`), `6h` (`6×1H`), `12h` (`12×1H`), and `24h` (`24×1H`)**, plus **Tsinghua Paper Equation 12 Realized Volatility (`pred_volatility_1h_bps`)** and **Pre-Mean Trajectory `tp_touch_prob_1h`**.
   - **5-Horizon Crash Shield:** Automatically blocks buying any dip if the `2h`, `6h`, `12h`, or `24h` Kronos horizons forecast a structural dump.
2. **100% Free Dual AI Council (`agents/llm_council.py`):**
   - **Primary Engine:** **Google AI Studio Free Tier** (`gemini-3.5-flash-lite` ➔ `gemini-3.5-flash` ➔ `gemini-3.8-flash`) with native `application/json` output.
   - **Secondary Automatic Failover:** **OpenRouter Free Tier** in 1 single HTTP call (`"model": "nvidia/nemotron-3-ultra-550b-a55b:free"`, `"models": ["google/gemma-4-31b-it:free", "openrouter/free"]`).
   - Holds **70% conviction authority** and **full negative Veto power** (`conviction <= -0.15`) over new entries and cognitive early exits.
3. **Configurable Two-Chamber Architecture & 3-Stage Asymmetric Risk Shield:**
   - **Chamber 1 (Assault Sniper — Default `63%` of Capital):** Hunts high-liquidity altcoin & major V-rebounds with Kronos-calibrated micro-profit targets (`+42 .. +125 bps` gross).
   - **Chamber 2 (Pure Cash Shield — Default `37%` of Capital):** Kept in pure `USDC` cash during ordinary sessions to protect portfolio MTM.
   - **Stage 1 Fast Break-Even Shield (`+38 bps` / `+0.38%`):** Locks `76%–88%` of unrealized profit (minimum `+26 bps` gross = `+6 bps` net after `20 bps` round-trip Maker fees).
   - **Stage 2 Cognitive Early Stop (`-1.80% .. -3.99%`):** Exits early at `best_ask` if both Kronos `2h/6h/12h/24h` and the AI Council confirm thesis invalidation.
   - **Stage 3 Inviolable Hard Max-Loss Cap (Default `-400 bps` = `-4.00%`):** Automatic `Post-Only Maker` exit at `best_ask` so no position can ever become a deep bag.

---

## 🛠️ 1. UNIVERSAL INSTALLER & CUSTOM PORTFOLIO CALIBRATION (ZERO HARDCODED ASSUMPTIONS)

The installer (`install.sh` + `scripts/configure_run.py`) contains **zero hardcoded portfolio amounts or fixed expiration dates**. Every user (or installing AI agent) calibrates the system to their own wallet size, risk tolerance, and target schedule:

### A. Interactive Human Installation
```bash
git clone https://github.com/glaucogaribaldi/openclaw-trader.git ~/openclaw-trader
cd ~/openclaw-trader
bash install.sh
```
The wizard will ask you for:
- **Starting Capital in `USDC`** (or `AUTO` to detect your live OKX wallet balance automatically on first run);
- **Run Expiration Date** (any ISO-8601 UTC date such as `2026-12-31T21:00:00Z` with configurable cashout taper days, **or `NONE` for perpetual operation**);
- **Chamber 1 / Chamber 2 Capital Split %** (default `63% / 37%`);
- **Hard Max-Loss Cap** (default `-400 bps` = `-4.00%`) & **Fast Break-Even Shield** (default `+38 bps` = `+0.38%`);
- **Daily Compounding Target Channel** (default `+0.70% <-> +5.00%`).

### B. Non-Interactive AI Agent Installation (`AI_INSTALLER_GUIDE.md`)
If an AI Agent (**OpenClaw**, **Claude Code**, **Cursor**, **Codex**, **Devin**) is installing this repository for its human user, follow the complete step-by-step runbook in **[🤖 `AI_INSTALLER_GUIDE.md`](./AI_INSTALLER_GUIDE.md)**:
```bash
bash install.sh --non-interactive \
  --baseline-nav AUTO \
  --expiry-iso NONE \
  --cashout-days 6.0 \
  --chamber1-pct 63.0 \
  --max-loss-bps -400.0 \
  --fast-shield-bps 38.0
```

---

## 🏆 2. CURRENT LIVE REFERENCE PRODUCTION RUN (`docs/CURRENT_PRODUCTION_RUN.md`)

To see how **TRE OS v12.0** is calibrated in our live production environment on `brody` (OKX Spot EEA), see **[📊 `docs/CURRENT_PRODUCTION_RUN.md`](./docs/CURRENT_PRODUCTION_RUN.md)**:
- **Purified Run Inauguration:** `28 October 2026 at 21:06:37 UTC` (`22:06:37 CET`)
- **Starting Baseline Capital (`X`):** **`$285.74 USDC`** (100% legacy blocks unwound; live `Free USDC` recovered to `$199.35 USDC` = `70.3%` pure cash on `29/10/2026`)
- **Target Expiration & Cashout Schedule:** **`2026-12-31T21:00:00Z`** (4-Stage Progressive `USDC` Cashout Taper starting `2026-12-25`, `6.0` days prior to expiration)
- **Golden Rule Compounding Channel:** **`+0.70% <-> +5.00% / day`**
- **Risk Parameters:** `63%` Chamber 1 Assault / `37%` Chamber 2 Cash Shield, `+38 bps` Fast Break-Even Shield, `-400 bps` (`-4.00%`) Hard Max-Loss Cap.

---

## 📚 3. DOCUMENTATION INDEX

- **[🤖 `AI_INSTALLER_GUIDE.md`](./AI_INSTALLER_GUIDE.md):** Step-by-step deterministic runbook for AI agents installing and calibrating TRE OS v12.0.
- **[🏆 `docs/CURRENT_PRODUCTION_RUN.md`](./docs/CURRENT_PRODUCTION_RUN.md):** Full specification of the active Reference Production Run.
- **[🧠 `docs/NEURAL_ARCHITECTURE_V8.md`](./docs/NEURAL_ARCHITECTURE_V8.md):** PyTorch layer-by-layer topology of `NeoQuasar/Kronos-mini` + Online RLS + Kalman.
- **[🗺️ `ARCHITECTURE_MAP.md`](./ARCHITECTURE_MAP.md):** Fast file/line structural index and SQLite WAL schema map.
