# 🗺️ TRE OS v10.0 (SOVEREIGN PURIFIED TWO-CHAMBER X-USDC EDITION) — ULTRA-FAST AI & MODEL ARCHITECTURE MAP

> **Purpose:** This document is a zero-latency structural index for **Lehman Brody** and any AI model / sub-agent. Read this file first (`openclaw-trader/ARCHITECTURE_MAP.md` or `memory/TRE_OS_V8_INDEX.md`) to locate any function, SQLite table, systemd service, or mathematical formula in **1 tool call** without scanning whole files.

---

## ⚡ 1. INSTANT 1-SHOT COMMANDS FOR AI MODELS (FROM MAC TO `BRODY`)

Never run slow multi-step SSH discovery. Use `scripts/brody_fast_status.py` on `brody` (`34.28.19.242` / `100.106.15.28`):

### A. Instant Read-Only Snapshot (< 0.4s total, zero OKX API load):
```bash
ssh -F /dev/null -o IdentityAgent=none -o IdentitiesOnly=yes -i ~/.ssh/brody_ed25519 -o StrictHostKeyChecking=no zavattoni_giacomo@34.28.19.242 "/home/zavattoni_giacomo/openclaw-trader/venv/bin/python /home/zavattoni_giacomo/openclaw-trader/scripts/brody_fast_status.py"
```

### B. Full Live Executive Report + Telegram Push (`"report"` command):
```bash
ssh -F /dev/null -o IdentityAgent=none -o IdentitiesOnly=yes -i ~/.ssh/brody_ed25519 -o StrictHostKeyChecking=no zavattoni_giacomo@34.28.19.242 "/home/zavattoni_giacomo/openclaw-trader/venv/bin/python /home/zavattoni_giacomo/openclaw-trader/scripts/brody_fast_status.py --live"
```

---

## 📂 2. FILE & LINE-NUMBER MAP (`openclaw-trader`)

| File Path | Key Functions / Classes & Exact Line Ranges | Responsibility |
| :--- | :--- | :--- |
| **`predator_daemon.py`** | • `DEFAULT_UNIVERSE` (`L55–72`): 10 Active + 2 Harvest (`FET`, `SEI`)<br>• `init_predator_db` (`L100–165`): SQLite tables + 4 composite indexes<br>• `run_predator_cycle` (`L168–980`):<br>  - `L180–205`: 4-Thread Parallel Auth & Kronos Prefetch<br>  - `L230–345`: Fills Sync, `Re-Entry Pullback Guard (45m/-25bps)`, `fresh_scalp_tranches` Auto-Rebind<br>  - `L365–395`: 6-Thread Parallel L2 OrderBook & Trade Tape Fetch + `BTC-USDC` Radar<br>  - `L398–445`: `Ratchet Pool`, `Darwinian 24h Velocity`, `Intraday Rebound Catcher (2h low/high)`, `Session Multiplier (Asia/EU/US/Weekend)`<br>  - `L480–585`: `Cost-Basis Floor (+25 bps = 1.0025)`, `Micro-Slice Ratchet ($10)`, `Adaptive Upside Runner (+135 bps)`, `Parabolic Bubble Guard`, `Legacy Averaging Bonus (+6.5 pts)`, `Kronos Eq.12 Volatility Bonus`<br>  - `L630–785`: Order Self-Healing (`Stale BUY Chaser 22bps`, `Fee-Safe Floor Lift +24bps`, `Time-Decay Fast-Exit +24bps >=4h`, `Trailing 78% Profit-Lock`, `Cost-Basis Refresh up to -1500bps`)<br>  - `L790–845`: `Fresh Tranche Quick-Scalp TP` + `Auto-Dust Sweeper`<br>  - `L850–890`: `Bull-Wave Legacy Runner` & Protected Legacy SELL Placement<br>  - `L925–985`: `Opportunity-Ranked Cash Sweeper` (`>= $5.01`, `2-Slot Split $10+$10`) + `predator_live_snapshot.json` | Main 15-second autonomous trading engine (`openclaw-predator.service`) |
| **`core/predictor.py`** | • `KalmanPriceVelocityFilter` (`L35–90`)<br>• `OnlineRLSPredictor` (`L93–175`): `>= 1.2 bps` noise gate, L2 prior shrinkage `[0,6,10,6,8,5]`, clamp `[-25,+25]`<br>• `PredatorPredictiveEngine.evaluate` (`L215–335`): 4-Factor Blend (`45% RLS + 35% Kronos 3-Horizon + 12% LLM + 8% BTC`) + **`Macro Trend Veto`** (80% discount on 5m if 2h `< -20 bps` or 12h `< -30 bps`) + Regime Classification | Streaming ML & Regime Engine |
| **`scripts/kronos_oracle_server.py`** | • `_predict_paths_pre_mean` (`L92–168`): Preserves raw `(N, pred_len, 6)` tensor BEFORE `np.mean` (`Issue #375`) + enforces `tokenizer.eval()` & `model.eval()` (`Issues #415 & #407`)<br>• `forecast_pair` (`L170–295`): Tsinghua Paper (`arXiv:2508.02739v1`) + Pre-Mean Metrics (`tp_touch_prob_1h`, `path_dispersion_bps`, `kronos_zscore_1h`, `pred_volume_surge_ratio`, `pred_volatility_1h_bps`) | Local CPU Foundation Model Server (`127.0.0.1:8090`, `kronos-oracle.service`) |
| **`core/kronos_oracle.py`** | • `KronosForecast` & `KronosOracleClient` (`L20–85`) | `0.00ms` O(1) RAM HTTP Client |
| **`execution/okx_hybrid_executor.py`** | • `_SHARED_HTTP_SESSION` (`L35–48`): 16-connection Keep-Alive TLS Pool<br>• `get_perp_radar_snapshot` (`L205–232`): 1-call cached Perpetual Swap Basis Radar (`120s TTL`)<br>• `OKXNativeClient` (`L65–265`): `post_only`, `tdMode: cash`, `stpMode: cancel_maker` | Native OKX EEA REST v5 Adapter |
| **`agents/llm_council.py`** | • `_build_deterministic_debate` (`L68–135`): Kronos 3-Horizon aware convictions<br>• `run_council_debate` (`L175–255`): Prevents OpenRouter from throttling `agg_mult` below deterministic floor (`1.35x`) | 3-Agent Adversarial Council |
| **`core/predator_auditor.py`** | • `sync_okx_fills` (`L125–245`): Syncs fills (`>= 2026-10-22T19:00:00Z`) with exact `fresh_scalp_tranches` `buy_px` attribution | Deterministic Accounting & Audit |
| **`dashboard/app.py` & `dashboard/ui/`** | • `build_live_predator_state` (`L48–375`): Reads SQLite WAL `?mode=ro` + `predator_live_snapshot.json`<br>• `EquityGoldenChart.tsx`: `[ 24h | 1 Sett | 1 Mese | 1Y | YTD ]` selector | Institutional Web Terminal (`:8080`, `openclaw-dashboard.service`) |

---

## 🗄️ 3. SQLITE WAL DATABASE SCHEMA (`config/okx_trader.db`)

1. **`fresh_scalp_tranches`** (`trade_id PK, inst_id, buy_px, buy_sz, tp_ord_id, tp_px, status ['PENDING_TP'|'TP_PLACED'|'CLOSED_PROFIT'], created_at`) — *Binario B Quick-Scalp Sub-Ledger*.
2. **`predator_fills_ledger`** (`trade_id PK, ord_id, inst_id, side, fill_px, fill_sz, notional_usd, fee_usd, exec_type, wacb_px, realized_pnl_usd, fill_time`) — *Official Run Fills since `2026-10-22T19:00:00Z`*.
3. **`microstructure_telemetry`** (`id PK, timestamp, inst_id, mid_price, micro_price, spread_bps, obi_top5, ofi_norm, vpin_toxicity, hawkes_net_burst, composite_alpha, predicted_return_bps, kalman_velocity_bps, confidence, regime`) — *Auto-pruned to 10,000 rows, indexed by `idx_micro_inst_ts` & `idx_micro_ts`*.
4. **`predator_audit_history`** (`id PK, timestamp, current_nav_usd, net_pnl_usd, realized_pnl_usd, unrealized_mtm_usd, total_fills, audit_score, auditor_model, verdict`) — *NAV Curve History*.

---

## 🔒 4. INVIOLABLE MATHEMATICAL & FINANCIAL INVARIANTS

- **Baseline Nuova Run:** `$298.89 USDC` (`22/10/2026 21:00 CEST` = `2026-10-22T19:00:00Z`).
- **Regola Aurea Giornaliera:** `+0.70% <-> +5.00% / day` organic compounding through `31/12/2026`.
- **OKX EEA VIP0 Maker Fee Structure:** `10 bps` (`0.10%`) buy + `10 bps` (`0.10%`) sell = **`20.0 bps` (`0.20%`) round-trip**.
- **Fee-Safe Profit Floors:**
  - Quick-Scalp Fast-Exit Floor (`>= 4h`): **`buy_px * 1.0024` (`+24.0 bps` gross = `+4.0 bps` guaranteed net profit)**.
  - Legacy Cost-Basis Floor: **`openAvgPx * 1.0025` (`+25.0 bps` gross = `+5.0 bps` guaranteed net profit)**.
