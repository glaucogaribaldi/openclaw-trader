# TRE OS v13.1 — MASTER MEMORY & 6-BLOCK ARCHITECTURAL INDEX (INSTANT RECALL)

> Purpose: Single source of truth for Lehman Brody (Aragorn / OpenClaw) to recall the entire architecture, file/line map, fee structure, and invariants of TRE OS v13.1 (Spot Live + Parallel Futures Demo 2.5x) in 1 read call.

## 0. SUPREME DIRECTIVES & GOLDEN RULES
1. Brutal Honesty Always: Never celebrate micro-wins if total net capital is down. Always report exact net cashflow (NAV, Free USDC, realized PnL, fees paid).
2. Golden Rule 1 (Daily Compounding Channel): Target +0.70% <-> +5.00% / day organic compounding.
3. Golden Rule 2 (Inviolable -4.00% Max Loss Cap):
   - Spot (1x): -400 bps (-4.00%) hard Post-Only Maker stop at best_ask (active 24/7, never expires after 10h).
   - Futures (2.5x Isolated): -156 bps price move + 4 bps Maker fee = -400 bps (-4.00%) hard margin loss cap.
4. Golden Rule 3 (Continuous Compounding until Expiration):
   - Slot sizing scales dynamically as a % of live NAV (10.5% in Spot Camera 1, 12.5% per slot in Futures Demo) until expiry_iso (2026-12-31T21:00:00Z with 6-day taper, or user-configured date).
5. 100% Sovereign & Free AI Stack (Zero totallyinnovationsrl dependency):
   - VPS brody (34.28.19.242 / 100.106.15.28, zavatoni.giacomo@gmail.com) uses:
     1) Local 7-Horizon Tsinghua Kronos-mini (4.1M) on 127.0.0.1:8090 (kronos-oracle.service);
     2) Google AI Studio Free Tier (GEMINI_API_KEY stored ONLY in brody:.env, gemini-3.5-flash-lite / gemini-3.5-flash / gemini-3.8-flash);
     3) OpenRouter Free Tier (OPENROUTER_API_KEY, 1-call native fallback nemotron-3-ultra-550b:free -> gemma-4-31b:free -> openrouter/free).

## 1. CERTIFIED OKX FEE STRUCTURE (Account uid: 885203458402552862, Lv1, acctLv: 2)
- OKX Spot (USDC pairs): Maker 0.08% (8 bps) / Taker 0.10% (10 bps) -> 16-20 bps round-trip.
- OKX Perpetual Swap (SWAP) & Futures (FUTURES): Maker 0.02% (2 bps) / Taker 0.05% (5 bps) -> 0.04% (4 bps) round-trip on notional (10 bps on 2.5x margin = $0.035 total fee on a $35 margin slot, less than half of Spot!).

## 2. THE 6 SYSTEM BLOCKS & EXACT FILE MAP (/home/zavattoni_giacomo/openclaw-trader)
- Block 1 (7-Horizon Kronos Oracle): scripts/kronos_oracle_server.py + core/kronos_oracle.py (kronos-oracle.service :8090). Single-worker PRIORITY_QUEUE (zero thread-leak, 380 MB RAM). Extracts 7 horizons: 5m (step 0), 10m (step 1), 1h (12x5m), 2h (8x15m), 6h (6x1H), 12h (12x1H), 24h (24x1H) + Eq.12 Volatility & tp_touch_prob_1h.
- Block 2 (L2 Microstructure & RLS): core/microstructure.py + core/predictor.py. Cont-Stoikov 5-level OFI, VPIN toxicity, Hawkes intensity, 2-state Kalman Velocity filter, Online RLS (6x6 P_t persisted), and 5-Horizon Crash Veto.
- Block 3 (AI Council & Self-Improver): agents/llm_council.py + core/gemini_self_improver.py. Gemini Free + OpenRouter Free Council (70% authority + negative veto) & Ordinary Internal Fee-Drag Auditor (monitors Fee / Gross Profit <= 12% and updates config/self_improvement_state.json).
- Block 4 (Spot Live Engine): predator_daemon.py (openclaw-predator.service). Two-Chamber Spot (63% Assault / 37% Pure USDC Shield), Anti-FOMO +10% 24h guard, +38 bps Fast Shield, -4.00% 24/7 Hard Stop, CLOSED_PROFIT vs CLOSED_STOPLOSS Darwinian scoring.
- Block 5 (Parallel Futures Demo 2.5x): predator_futures_demo.py (openclaw-futures-demo.service). 2.5x Isolated LONG + SHORT on 12 OKX Perpetual Swaps. Macro Compass (6h/12h/24h) + Micro Trigger (5m/10m + OFI), BTC Correlation Veto, Funding Rate Guard, 30m/120m Post-Exit Cooldown, Real Book Exit Price, -4.00% Margin Hard Cap.
- Block 6 (Execution & Instant Diagnostics): execution/okx_hybrid_executor.py + scripts/brody_fast_status.py. 16-connection Keep-Alive TLS pool, 100% Post-Only Maker, side-by-side Spot Live + Futures Demo reporting.