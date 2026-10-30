# TRE OS v14.3 — Sovereign Anti-Crash Fortress (Perpetual Futures 4.0x Isolated Edition)

> **100% Customizable, Non-Personalized Quantitative Perpetual Futures (`LONG + SHORT`) & Spot Trading OS for OKX (EEA `*-USD_UM_XPERP-*` & Global `*-USDT-SWAP`), powered by Tsinghua 7-Horizon Kronos-mini (4.1M) Local RAM Oracle & Sovereign Free AI Auditor (`$0.00` AI Cost).**

---

## 🚀 1. QUICK START FOR NEW USERS (OR YOUR AI ASSISTANT)

Every parameter of **TRE OS v14.3** (Starting Baseline Capital, Leverage, Slot Allocation %, Expiration Date or Perpetual Mode, Stop-Loss Cap, and Break-Even Shield) is **100% user-configurable** via `install.sh` and `scripts/configure_run.py`.

### Option A — 1-Command Interactive Setup (Human Operator)
```bash
git clone https://github.com/glaucogaribaldi/openclaw-trader.git
cd openclaw-trader
bash install.sh
```

### Option B — Non-Interactive CLI Setup (Customizing Your Portfolio)
```bash
# Example 1: Perpetual Run (No Expiration), Auto-Read OKX Balance, 4.0x Isolated (4 Slots x 20% NAV = 80% Active / 20% Cash Reserve)
./venv/bin/python scripts/configure_run.py --baseline-nav AUTO --expiry-iso NONE --chamber1-pct 80.0 --max-loss-bps -100 --fast-shield-bps 20

# Example 2: Fixed-Term Run with 6-Day Progressive Reduce-Only Cashout Taper
./venv/bin/python scripts/configure_run.py --baseline-nav 1000.0 --expiry-iso 2026-12-31T21:00:00Z --cashout-days 6 --chamber1-pct 80.0 --max-loss-bps -100 --fast-shield-bps 20
```
*(If you use an AI assistant such as OpenClaw, Claude Code, or Cursor, point it to [`AI_INSTALLER_GUIDE.md`](./AI_INSTALLER_GUIDE.md) for autonomous setup).*

---

## 🛡️ 2. THE 6-BLOCK ARCHITECTURE & ANTI-CRASH FORTRESS (`TRE OS v14.3`)

1. **Block 1 — 7-Horizon Tsinghua Kronos-mini (4.1M) RAM Oracle (`scripts/kronos_oracle_server.py`):**
   - Local FastAPI server (`127.0.0.1:8090`, `~380 MB` RAM) computing 7 simultaneous horizons (`5m, 10m, 1h, 2h, 6h, 12h, 24h`) across all 12 core pairs in `0.00ms` O(1) RAM cache lookup.
2. **Block 2 — Calibrated L2 Microstructure (`core/microstructure.py`):**
   - Cont-Stoikov 5-level Order Flow Imbalance (`OFI`), Futures-calibrated `$25,000` `VPIN` bucket toxicity filter, and Hawkes burst intensity.
3. **Block 3 — Sovereign Free AI Fee-Drag & Risk Auditor (`predator_futures_demo.py`):**
   - Uses Google AI Studio Free Tier (`gemini-3.5-flash-lite -> gemini-3.5-flash -> gemini-3.8-flash`) and OpenRouter Free Tier (`:free`) at **`$0.00` API cost** to enforce **`Fee-Drag Ratio <= 12.0%`** and dynamically calibrate `min_kronos_10m_bps`.
4. **Block 4 — Bidirectional `LONG + SHORT` Perpetual Futures Engine (`predator_futures_live.py`):**
   - **OKX Europe (EEA MiFID II / MiCA) Native Support:** Automatically operates on regulated **`*-USD_UM_XPERP-*` (`instType=FUTURES`, `ruleType=xperp`, `settleCcy=USD`)** using your **`USDC` balance 1:1 directly** with **`0.02%` (`2 bps`) Maker / `0.05%` (`5 bps`) Taker fees** (4x cheaper than Spot!).
   - **High-Conviction `4.0x Isolated` Sizing:** 4 Slots x `20.0%` of live NAV (`80.0%` active margin capacity = `3.2x` total notional firepower + `20.0%` pure `USDC` cash reserve).
5. **Block 5 — Dual Hardware + Mathematical Anti-Crash Fortress:**
   - **Hardware Shield (`attachAlgoOrds` inside OKX Matching Engine):** Every entry order embeds native exchange-side `slTriggerPx = -105 bps` (`slOrdPx: -1` Market) and `tpTriggerPx = +110 bps`. Even if your VPS goes completely offline during a `-25%` flash crash, OKX's own servers close the position automatically in `< 10ms`!
   - **Mathematical Shield (Free-Roll Pyramiding):** Maximum **2 unshielded slots** in the same direction (`LONG` or `SHORT`). Slots 3 and 4 can only open in the same direction once earlier slots have armed their **`+20 bps` Break-Even Shield (`shield_armed == 1`, zero downside risk)**, or in the opposite direction as a natural portfolio hedge.
   - **2-Stage Smart Shield & 1h-Inversion Exit:** Locks `+8 bps` net profit as soon as a trade touches `+20 bps` (`+12 bps` after 45m), trails at `65%` up to `+65 bps` so runners ride full `+110 bps` waves, tightens to `82%` above `+65 bps`, and exits early if `5m + 10m + 1h` invert against the position.
6. **Block 6 — Institutional Web Terminal (`dashboard/app.py` on `:8080`) & Surgical Test/Simulation Suites:**
   - Live React/Flask dashboard at `http://<YOUR_VPS_IP>:8080`, instant CLI inspector (`scripts/brody_fast_status.py`), 6-Block verification suite (`scripts/test_v14_xperp_suite.py`), Normality/Madness simulator (`scripts/simulate_normality_and_madness.py`), and 72-Hour Milestone Audit (`docs/AUDIT_72H_LIVE_XPERP_MILESTONES.md`).

---

## 📊 3. REFERENCE CASE STUDY: OUR CURRENT LIVE PRODUCTION RUN

For complete transparency, the exact parameters and 72-hour validation milestones of our live production deployment are documented in:
- [`docs/CURRENT_PRODUCTION_RUN.md`](./docs/CURRENT_PRODUCTION_RUN.md)
- [`docs/AUDIT_72H_LIVE_XPERP_MILESTONES.md`](./docs/AUDIT_72H_LIVE_XPERP_MILESTONES.md)