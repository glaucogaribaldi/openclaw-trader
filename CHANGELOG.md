# Changelog — OpenClaw Quantitative Trader (TRE OS)

## [v1.5.0] — 2026-11-04 (`TRE OS v29.0 — Co-Testing, 30-Day Historical Simulator & 6-Phase Systemic Architecture`)

### 🚀 Highlights for Co-Testers & Quant Operators
- **Built-In 30-Day OKX Historical Backtester & 8-Trap Verification Suite (`scripts/simulate_30d_and_traps_v28.py` + `config/trap_simulation_playbook.json`):**
  - Co-testers can now benchmark any parameter change on 30 days of real OKX EEA candles across all 3 Asset Classes (`CRYPTO`, `COMMODITY`, `US_EQUITY`) and verify 8 real-world market trap scenarios (`PASSED 8/8`) before deploying live:
    ```bash
    ./venv/bin/python scripts/simulate_30d_and_traps_v28.py
    ```
  - Verified 30-day benchmark improvement: Net PnL **`+57.5%`** (`+$1,220.00` vs `+$774.36`), Win-Rate **`60.6%`** (vs `43.0%`), Exchange Fees **`-51.3%`** (`$54.81` vs `$112.50`).
- **100% Neural `Kronos-mini (4.1M)` Mandate + Pre-Mean Trajectory SNR (`TRE OS v29.0`):**
  - Eliminated linear fallback approximations: no position can open unless backed by a live 7-horizon neural forecast from `NeoQuasar/Kronos-mini (4.1M)` (`5m, 10m, 1h, 2h, 6h, 12h, 24h`).
  - Wired Tsinghua Kronos Pre-Mean Monte Carlo trajectory metrics (`kronos_zscore_1h >= 0.20`, `tp_touch_prob_1h`, `pred_volume_surge_ratio`) and Multi-Horizon Acceleration (`+12 pt` when `1h >= 10m > 5m > 2 bps`) + WorldQuant `Alpha #101` candle-body conviction (`+10 pt`).
  - Upgraded `kronos_oracle_server.py` to natively ingest both `-USDC` Spot and `*-USD_UM_XPERP-*` Perpetual Futures candles.
- **100% Maker `post_only` (`2 bps`) Execution & Balanced `1 : 1 : 1.2` 6-Stage Free-Roll Pyramid:**
  - Converted Chandelier profit-taking exits and Tier 2/3 pyramid add-ons from Market Taker (`5 bps` + spread) to `Maker post_only (2 bps)` with automatic fallback.
  - **6-Stage Progressive Protection (`G0 -> G0.5 -> G1 -> G1 Lock -> G1.5 Trail -> G2/G3 3x Free-Roll`):**
    1. **Tier 0 (`0..+23 bps`):** `2x` isolated base entry (max risk locked at `-0.33% NAV`).
    2. **Tier 0.5 (`+24 bps`):** Halves hardware & software stop-loss to **`-28 bps`**.
    3. **Tier 1 (`+36 bps`):** Tightens stop-loss to **`-12 bps`** (preserving breathing room for Tier 2 runners).
    4. **Tier 1 Breakeven Lock (`+42 bps`):** Locks **`+6 bps` net breakeven** (zero loss after Maker fees).
    5. **Tier 1.5 Progressive Trail (`+52 bps`):** Trails stop at **`max(+26 bps, Peak - 24 bps)`** in Maker.
    6. **Tier 2 (`+64..+78 bps`, `3x` 1:1 Maker Add-On) & Tier 3 (`+85..+130 bps`, `3x` 1.2x Maker Add-On):** Executes `Peak Rebase` on the new weighted average price (`avgPx`) only upon verified order acceptance and locks hardware OCO at **`+38 bps` (`G2`) / `+48 bps` (`G3`) above `avgPx`** (strictly above the add-on purchase price).
- **Strict Asset-Class Session Guards & Twin-Commodity Cooldown:**
  - `US_EQUITY_XPERP` trades exclusively during US Cash hours (`14:35–20:30 UTC` Mon–Fri).
  - `COMMODITY_MACRO` (`CL, BZ, XAU, XAG`) blocks the illiquid nocturnal window (`21:30–04:45 UTC`) and enforces a 240-minute cross-instrument cooldown between `CL` and `BZ` after any stop-loss.