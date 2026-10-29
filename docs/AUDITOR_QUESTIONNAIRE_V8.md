# 🕵️‍♂️ TRE OS v8.3 (SOVEREIGN PREDATOR EDITION) — EXTERNAL AUDITOR INVESTIGATION QUESTIONNAIRE & VERIFICATION PROTOCOL

**Document ID:** `TRE-OS-V8.3-AUDITOR-PROTOCOL`  
**Target System:** [`github.com/glaucogaribaldi/openclaw-trader`](https://github.com/glaucogaribaldi/openclaw-trader)  
**Purpose:** This document defines the **12 Investigative Audit Questions** that an independent external quantitative auditor, security reviewer, or AI review model must answer by directly inspecting the source code, SQLite WAL database (`config/okx_trader.db`), systemd services, and live OKX Spot orderbook telemetry.

> **Instructions for the External Auditor:** Do not accept high-level claims at face value. For each question below, run the specified verification command or inspect the exact file and line range listed in `ARCHITECTURE_MAP.md`, then record your empirical finding (**PASS / FAIL**) and evidence.

---

## 🔍 SECTION A: EXCHANGE EXECUTION, ZERO-LEVERAGE & FEE-SAFETY INVARIANTS

### Question A1 — Zero-Leverage & Zero-Liquidation Guarantee (`OKX Spot EEA`)
- **What to Investigate:** Can the system ever open a leveraged position, margin loan, futures contract, or perpetual swap, or suffer forced exchange liquidation?
- **Where to Inspect:** `execution/okx_hybrid_executor.py` (`place_spot_order`, lines `205–232`) and `predator_daemon.py` (`DEFAULT_UNIVERSE`, lines `55–72`).
- **Auditor Verification Check:**
  1. Verify that every order payload hardcodes `"tdMode": "cash"` and targets exclusively `-USDC` Spot instruments on `https://eea.okx.com`.
  2. Verify that no margin/derivative endpoints (`/api/v5/account/set-leverage`, `cross`, `isolated`, `SWAP`, `FUTURES`) exist anywhere in the repository.

### Question A2 — 100% Post-Only Maker Execution & Self-Trade Prevention (`0.00% Taker Fee`)
- **What to Investigate:** Does the execution adapter ever cross the spread as a Taker (paying `0.15%–0.20%` Taker fees), or are all orders strictly enforced as Maker-only?
- **Where to Inspect:** `execution/okx_hybrid_executor.py` (`L216–224`), `predator_daemon.py` (`allow_ioc = False`, `L475`), and SQLite table `predator_fills_ledger` (`exec_type` column).
- **Auditor Verification Check:**
  1. Run: `SELECT exec_type, COUNT(*) FROM predator_fills_ledger WHERE fill_time >= '2026-10-22T19:00:00Z' GROUP BY exec_type;`
  2. Confirm that **100.0% of fills have `exec_type = 'M'` (Maker)** and that `"ordType": "post_only"` + `"stpMode": "cancel_maker"` are enforced on every order submission.

### Question A3 — Round-Trip VIP0 Maker Fee Coverage (`+24 bps` / `+25 bps` Fee-Safe Floor)
- **What to Investigate:** On OKX EEA VIP0, Maker fees are `0.10%` (`10 bps`) on BUY and `0.10%` (`10 bps`) on SELL (`20.0 bps` total round-trip). Can a Quick-Scalp fast-exit or a Legacy Cost-Basis Floor order ever execute at a gross profit smaller than `20.0 bps`, resulting in a net loss after fees?
- **Where to Inspect:** `predator_daemon.py` (`L476–488`, `L655–688`, `L810–825`).
- **Auditor Verification Check:**
  1. Confirm that `raw_floor_mult = 1.0025` (`+25.0 bps` gross $\rightarrow$ **`+5.0 bps` net profit** after `20 bps` round-trip fees) and Ratchet relief is strictly bounded by `max(1.0021, ...)`.
  2. Confirm that `fast_exit_px = round(max(tr_buy_px * 1.0024, asks[0][0]), dec_px)` (`+24.0 bps` gross $\rightarrow$ **`+4.0 bps` net profit**) and that `FEE_SAFE_FLOOR_LIFT_24BPS` automatically cancels and lifts any tranche order below `tr_buy_px * 1.0023`.

---

## 🧠 SECTION B: PREDICTIVE ENGINE (`KRONOS-MINI` TSINGHUA PAPER + `ONLINE RLS` + `OFI/VPIN`)

### Question B1 — Fidelity to the Tsinghua University Kronos Paper (`arXiv:2508.02739v1`)
- **What to Investigate:** How accurately does the local `kronos-oracle.service` implement the mathematical specifications of Shi et al. (*"Kronos: A Foundation Model for the Language of Financial Markets"*), and does it block the 15-second trading loop?
- **Where to Inspect:** `scripts/kronos_oracle_server.py` (`forecast_pair`, `L92–225`) and `core/kronos_oracle.py`.
- **Auditor Verification Check:**
  1. Verify **Table 8 Lookback Windows**: `5m = 300`, `15m = 160`, `1H = 80`.
  2. Verify **Table 6 & Appendix E Hyperparameters**: `T = 0.60`, `top_p = 0.90` with multi-sample Monte Carlo ensembling.
  3. Verify **Equation 13 (Path-Averaged Return Signal)** and **Equation 12 (Realized Volatility Forecast `pred_volatility_1h_bps`)**.
  4. Verify that `_background_refresh_loop()` pre-computes all 12 pairs in a background daemon thread so HTTP `GET /forecast` responds from RAM in **`0.00 ms`**.

### Question B2 — Protection Against 5m Counter-Trend Bull Traps (`Macro Trend Veto`)
- **What to Investigate:** During a macro market crash, 5-minute K-line models frequently exhibit mean-reversion bias (predicting a bounce after 3–4 red candles while the 2-hour and 12-hour trends are collapsing). How does the system prevent buying falling knives?
- **Where to Inspect:** `core/predictor.py` (`PredatorPredictiveEngine.evaluate`, `L238–255`).
- **Auditor Verification Check:**
  1. Inspect the **Macro Trend Veto**: verify that when `eff_k1h > 0` but `kronos_macro_2h_bps < -20.0` or `kronos_swing_12h_bps < -30.0` (and horizons are not aligned), `eff_k1h` is discounted by **`80%` (`* 0.20`)**.
  2. Verify the **Cross-Asset `BTC-USDC` Lead-Lag Radar** (`predator_daemon.py` `L385–395`): confirm that when `btc_lead_lag_bps < -12.0`, all pairs enter `TOXIC_DIP_DEFENSE` and new Cash Sweeper buys are halted below `-14.0 bps`.

### Question B3 — Immunity of `OnlineRLSPredictor` to Flat-Tick Noise Saturation
- **What to Investigate:** High-frequency 15-second polling produces thousands of flat ticks (`0.0 bps` move) or bid-ask micro-bounces. Does the Recursive Least Squares (`OnlineRLSPredictor`) covariance matrix explode or saturate weights to extreme bounds over time?
- **Where to Inspect:** `core/predictor.py` (`OnlineRLSPredictor.update_and_predict`, `L118–165`) and `config/rls_model_state.json`.
- **Auditor Verification Check:**
  1. Confirm that weight updates are gated by **`if abs(realized_bps) >= 1.2:`**, ignoring flat 15-second noise.
  2. Confirm L2 shrinkage (`0.995 * w + 0.005 * priors`) toward microstructure priors `[0, 6, 10, 6, 8, 5]` and hard clamping within `[-25.0, +25.0]`.

---

## 🔄 SECTION C: DUAL-BINARY SUB-LEDGER, COST-BASIS AVERAGING & ANTI-CHURN HARMONY

### Question C1 — Strict Isolation Between `Binario A` (Legacy Bags) and `Binario B` (`fresh_scalp_tranches`)
- **What to Investigate:** When a token has both a historical legacy position (e.g., `51.55 SUI` at `$0.9734`) and a newly bought Quick-Scalp tranche (e.g., `5.32 SUI` at `$0.9361`), can a legacy order re-peg accidentally swallow the Quick-Scalp tranche quantity or vice versa?
- **Where to Inspect:** `predator_daemon.py` (`L655–745` and `L790–845`).
- **Auditor Verification Check:**
  1. Verify that `tranche_locked_sz` sums both active `TP_PLACED` tranche orders and `PENDING_TP` tranche sizes, subtracting them from `cash_token_qty` before computing `legacy_free_qty`.
  2. Verify that Quick-Scalp `repeg_sz` is strictly bounded by `min(cash_token_qty, tr_buy_sz * 0.999)`.
  3. Inspect live OKX open orders on `SUI-USDC` and `RENDER-USDC` to confirm independent concurrent `SELL` orders exist on the book without cancellation churn.

### Question C2 — Free Historical Cost-Basis Averaging & Automatic Floor Pull-Down
- **What to Investigate:** How does the system recover underwater legacy positions even when the broader market trades sideways?
- **Where to Inspect:** `predator_daemon.py` (`legacy_averaging_bonus` at `L530` and `AUDIT SAFEGUARD 3` at `L730–745`).
- **Auditor Verification Check:**
  1. Verify that profitable Quick-Scalps on discounted legacy pairs lower OKX's weighted `openAvgPx`.
  2. Verify that `AUDIT SAFEGUARD 3` (`-1500.0 <= unrealized_bps < 0.0`) automatically cancels the old high legacy `SELL` order and re-pegs it down to the new `openAvgPx * 1.0025` (as proven empirically on `SUI` `$1.0241 -> $0.9758`, `LINK` `$13.040 -> $12.301`, `SOL` `$107.15 -> $105.84`, and `RENDER` `$1.834 -> $1.793`).

---

## 🎄 SECTION D: UNIVERSAL CONFIGURABLE EXPIRATION, 6-DAY CASHOUT & BLACK-SWAN SURVIVAL

### Question D1 — Universal Configurable Run Expiration & 4-Stage Intelligent Cashout (`evaluate_run_lifecycle`)
- **What to Investigate:** Is the expiration and cashout mechanism hardcoded as a one-off hack, or is it a universal, parameterizable subsystem (`RUN_EXPIRY_ISO` / `--expiry-iso` and `CASHOUT_TAPER_DAYS` / `--cashout-days`) usable by any GitHub operator?
- **Where to Inspect:** `predator_daemon.py` (`evaluate_run_lifecycle`, `L75–165`, `L850–995`, `L1185–1215`).
- **Auditor Verification Check:**
  1. Run unit tests across all 4 stages (`ACTIVE_COMPOUNDING`, `CASHOUT_STAGE_1_VAULT_50`, `CASHOUT_STAGE_2_REDUCE_ONLY`, `CASHOUT_STAGE_3_FINAL_SETTLEMENT`) and `RUN_EXPIRY_ISO=NONE`.
  2. Verify that for the current official run (`DEFAULT_EXPIRY_ISO = "2026-12-31T21:00:00Z"`, `DEFAULT_CASHOUT_DAYS = 6.0`), the 6-day orderly cashout begins automatically on **December 25, 2026 at 21:00 UTC**, locking 50% of USDC in Stage 1 (`Dec 25–28`), switching to 100% Reduce-Only in Stage 2 (`Dec 28–31`), and executing 100% Post-Only Maker Best-Ask settlement in Stage 3 (`final 6h on Dec 31`) to guarantee **100% USDC and 0% Crypto at expiration**.

### Question D2 — Survival Under a `-70%` Bitcoin Bubble Burst (`Cannibal Ratchet` Micro-Slice Unlock)
- **What to Investigate:** What happens if a historical `-55% BTC / -70% Altcoin` crash starts today and never rebounds before the expiration date? How does the system avoid holding frozen legacy bags until the final day?
- **Where to Inspect:** `predator_daemon.py` (`CANNIBAL_RATCHET_SLICE_UNLOCK`, `L858–878`).
- **Auditor Verification Check:**
  1. Verify that whenever a legacy bag drops below `-15%` (`unrealized_bps <= -1500.0`) and accumulated realized Quick-Scalp profits in `ratchet_pool_usd` reach `>= $0.45 USDC`, the engine carves out a **`$5.20 USDC` micro-slice** (`cannibal_sz`) and subsidizes its exit price by `ratchet_pool_usd * 0.85`.
  2. Confirm that this converts deeply underwater crypto slices into live rotating USDC ammunition during the crash while keeping net realized PnL `>= $0.00`.

### Question D3 — Speculative Bubble Upside Capture vs Blow-Off Top Protection
- **What to Investigate:** How does the system avoid both *myopia* (selling too early at `+28 bps` during a `+1.5%` bull candle) and *presbyopia/FOMO* (buying the exact top of a parabolic blow-off spike)?
- **Where to Inspect:** `predator_daemon.py` (`is_bubble_top` and `is_upside_runner`, `L512–530`, `L685–702`, `L810–825`).
- **Auditor Verification Check:**
  1. Confirm `is_bubble_top` blocks new buys when `bounce_from_low_bps >= 180.0` and `drop_from_high_bps < 8.0` (unless all 3 Kronos horizons align).
  2. Confirm `is_upside_runner` expands Quick-Scalp TP caps up to **`+135.0 bps`**, delays Profit-Lock to `+55.0 bps`, and locks in **`78%` of peak unrealized gains (`Trailing 78% Profit-Lock`)**.

### Question D4 — Deterministic Accounting Separation & Credential Security
- **What to Investigate:** Can any LLM or AI model hallucinate financial numbers in reports, or are all NAV, PnL, and fill metrics computed deterministically? Are any API keys or secrets exposed in git history?
- **Where to Inspect:** `core/predator_auditor.py`, `scripts/accounting_engine.py`, `dashboard/app.py`, and `.gitignore`.
- **Auditor Verification Check:**
  1. Verify `git status` and `git log -p` contain zero API keys, tokens, or `.env` files.
  2. Verify that all financial figures in `predator_audit_report.json` and `/api/state` come strictly from OKX REST balances and SQLite ledger queries.

---

## 🔬 SECTION E: KRONOS TENSOR INTEGRITY (`ISSUES #415 / #407 / #375`) & ORTHOGONAL DERIVATIVES RADAR (`v8.4`)

### Question E1 — PyTorch `.eval()` Enforcement & Cross-Attention Causal Flag Integrity (`shiyu-coder/Kronos` Issues `#415` & `#407`)
- **What to Investigate:** Upstream `KronosPredictor.__init__` (`model/kronos.py` `L484–507`) does not invoke `.eval()` on `model` or `tokenizer`. Furthermore, `MultiHeadCrossAttentionWithRoPE.forward` (`model/module.py` `L387`) sets `is_causal_flag = self.training` during `decode_s2`, and `FEBlock` (`L278`) / `TransformerBlock` (`L328`, `L348`) apply `nn.Dropout(p)` when `self.training == True`. How does TRE OS v8.4 guarantee deterministic inference?
- **Where to Inspect:** `scripts/kronos_oracle_server.py` (`_predict_paths_pre_mean` `L100–102` and `main()` `L330–332`).
- **Auditor Verification Check:**
  1. Confirm that both `tokenizer.eval()` and `model.eval()` are explicitly invoked at startup and inside `_predict_paths_pre_mean()`, guaranteeing `self.training == False`, `dropout_p == 0.0`, and `is_causal == False` in `decode_s2`.

### Question E2 — Pre-Mean Trajectory Tensor Extraction vs `np.mean(preds, axis=1)` Envelope Collapse (`Issue #375`)
- **What to Investigate:** In upstream `auto_regressive_inference()` (`model/kronos.py` `L467`), `preds = np.mean(preds, axis=1)` averages the $N$ Monte Carlo paths into a single flat trajectory *before* returning the DataFrame, crushing asynchronously timed High/Low peaks and realized volatility by 40–50%. How does TRE OS v8.4 avoid this?
- **Where to Inspect:** `scripts/kronos_oracle_server.py` (`_predict_paths_pre_mean` and `forecast_pair`, `L92–265`).
- **Auditor Verification Check:**
  1. Confirm that `_predict_paths_pre_mean()` extracts the raw `(sample_count, pred_len, 6)` tensor `raw_paths_5m` *before* averaging across `axis=0`.
  2. Confirm that `upside_high_bps`, `downside_low_bps`, `pred_volatility_1h_bps` (Eq. 12), `tp_touch_prob_1h` (probability that $\max(\text{High}) \ge +26\text{ bps}$), `kronos_zscore_1h` (cross-sectional volatility-normalized return from `qlib_test.py`), and `pred_volume_surge_ratio` are computed directly from the pre-mean trajectories.

### Question E3 — Orthogonal OKX Perpetual Swap Basis Radar (`Short Squeeze` vs `Long Squeeze` Detection)
- **What to Investigate:** How does the Spot engine detect leveraged derivatives positioning (Short Squeezes vs Long Squeezes) without adding latency or hitting per-pair rate limits?
- **Where to Inspect:** `execution/okx_hybrid_executor.py` (`get_perp_radar_snapshot`, `L205–232`) and `predator_daemon.py` (`perp_squeeze_bonus`, `L645–660`).
- **Auditor Verification Check:**
  1. Confirm that `get_perp_radar_snapshot()` fetches all 524 OKX Perpetual Swap tickers in **1 single HTTP request (`GET /api/v5/market/tickers?instType=SWAP`)** cached for `120 seconds` (`0.00 ms` loop overhead).
  2. Confirm that `perp_basis_bps <= -6.0` (deep perp discount) combined with positive Spot `OFI >= +0.15` triggers a `+4.5 pt` **Short Squeeze Boost**, whereas `perp_basis_bps >= +15.0` (overheated perp premium) combined with `VPIN >= 0.65` triggers a `-6.0 pt` **Long-Squeeze Penalty**.

