# 🏆 CURRENT REFERENCE PRODUCTION RUN — TRE OS v12.0 (SOVEREIGN TWO-CHAMBER EDITION)

> **Note:** This document describes the active **Reference Production Run** currently operating live on OKX Spot EEA. New users installing this repository are **not** bound to these dates or dollar amounts — use `scripts/configure_run.py` (see [`AI_INSTALLER_GUIDE.md`](../AI_INSTALLER_GUIDE.md)) to calibrate the engine to your own wallet and schedule.

---

## 📊 1. REFERENCE RUN PARAMETERS (`config/purified_run_config.json` on Production Host)

| Parameter | Reference Production Value | Description |
| :--- | :--- | :--- |
| **Exchange & Market Mode** | **OKX Spot EEA** (`tdMode: cash`) | Zero leverage, zero derivatives, 0.00% liquidation risk |
| **Order Execution Policy** | **100% Post-Only Maker** (`ordType: post_only`) | `10 bps` buy + `10 bps` sell = `20 bps` round-trip VIP0 Maker fee; `0.00%` Taker fee |
| **Purified Run Inauguration** | `2026-10-28T21:06:37Z` (`22:06:37 CET`) | Initialized after 100% legacy block unwind |
| **Purified Baseline Capital (`X`)** | **`$285.74 USDC`** | Reference starting capital for the Purified Two-Chamber Run |
| **Daily Compounding Target** | **`+0.70% <-> +5.00% / day`** | Golden Rule organic daily compounding channel |
| **Target Expiration Date** | **`2026-12-31T21:00:00Z`** | Configurable 4-Stage Cashout Engine (6-day taper starting `2026-12-25`) |
| **Chamber 1 (Assault Sniper)** | **`63% of NAV`** | Dynamic high-liquidity altcoin & major dip-sniper bullets |
| **Chamber 2 (Pure Cash Shield)** | **`37% of NAV`** | Pure `USDC` reserve held in cash during ordinary sessions |

---

## 🧠 2. COGNITIVE & MATHEMATICAL STACK OF THE CURRENT RUN (`TRE OS v12.0`)

1. **5-Horizon Local Kronos Foundation Model (`kronos-oracle.service` on `127.0.0.1:8090`):**
   - Runs Tsinghua University's `NeoQuasar/Kronos-mini (4.1M)` locally in RAM with a single-worker `PRIORITY_QUEUE` (`0.2 ms` HTTP response, `~3.5s` background CPU inference per pair).
   - Computes 5 simultaneous horizons per asset:
     - **`1h` (`expected_return_1h_bps`):** `12 × 5m` rollout with pre-mean trajectory tensor (`Eq. 12` realized volatility & `tp_touch_prob_1h`);
     - **`2h` (`macro_return_2h_bps`):** `8 × 15m` intraday trend;
     - **`6h` (`horizon_6h_bps`):** `6 × 1H` session perspective;
     - **`12h` (`swing_return_12h_bps`):** `12 × 1H` overnight swing perspective;
     - **`24h` (`daily_return_24h_bps`):** `24 × 1H` daily structural perspective.
   - **5-Horizon Crash Shield (`has_5h_perspective_safety`):** Automatically blocks new `BUY` entries if `2h < -12 bps`, `6h < -22 bps`, `12h < -35 bps`, or `24h < -50 bps`.
2. **Dual Free AI Council (`agents/llm_council.py`):**
   - **Primary Engine:** Google AI Studio Free Tier (`gemini-3.5-flash-lite` ➔ `gemini-3.5-flash` ➔ `gemini-3.8-flash`) with native `application/json` output.
   - **Secondary Automatic Failover:** 1-Single-Call OpenRouter Free Router (`"model": "nvidia/nemotron-3-ultra-550b-a55b:free"`, `"models": ["google/gemma-4-31b-it:free", "openrouter/free"]`).
   - **70% Conviction Authority & Full Negative Veto:** If the AI Judge assigns `conviction <= -0.15`, new `BUY` orders on that asset are vetoed.
3. **3-Stage Asymmetric Risk & Profit Protection:**
   - **Stage 1 — Fast Break-Even + Profit Shield at `+38 bps` (`+0.38%`):** Locks `76%–88%` of unrealized profit (minimum `+26 bps` gross = `+6 bps` net after `20 bps` OKX Maker fees).
   - **Stage 2 — Cognitive Early Exit (`-1.80% .. -3.99%`):** Exits early in `Post-Only Maker` at `best_ask` if both Kronos (`2h <= -25 bps` + bearish `6h/12h/24h`) and the AI Council (`llm_bias <= -0.25`) confirm thesis invalidation.
   - **Stage 3 — Hard Max-Loss Cap at `-4.00%` (`-400 bps`):** Inviolable automatic `Post-Only Maker` exit at `best_ask` so no position can ever exceed a `-4.0%` drawdown.
