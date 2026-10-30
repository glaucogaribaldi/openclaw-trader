# 🗺️ TRE OS v12.6 — MASTER MEMORY & ARCHITECTURE INDEX (1-SHOT CONSULTATION FILE)

> **Purpose:** Read this single file first (`/Users/zava/.openclaw/workspace/memory/TRE_OS_V12_MASTER_INDEX.md` or `openclaw-trader/ARCHITECTURE_MAP.md`) to recall the entire project architecture, exact file/line map, SQLite schemas, AI keys, and mathematical invariants in **1 tool call**.

---

## 🚨 0. SUPREME DIRECTIVES & STANDING RULES OF GIACOMO ZAVATTONI
1. **Brutale Sincerità & Zero Trionfalismo:** Never claim a system is "working great" or celebrate micro-wins when total net capital (NAV) is down. Always start from real net cashflow (actual USDC in wallet vs baseline, fees paid, and MTM drawdown).
2. **100% Sovereign Infrastructure (Zero `totallyinnovationsrl`):** Never connect to `100.125.189.103` or any `totallyinnovationsrl` host. Operate exclusively on `brody` (`34.28.19.242` / `100.106.15.28`, `zavattoni_giacomo`, `zavatoni.giacomo@gmail.com`).
3. **Key Separation Policy:**
   - The **Google AI Studio Free Tier key (`GEMINI_API_KEY`)** from `chiave brody.txt` is stored **EXCLUSIVELY on `brody`** (`/home/zavattoni_giacomo/openclaw-trader/.env`, `chmod 600`), never in local OpenClaw config.
   - The **OpenRouter Free key (`OPENROUTER_API_KEY`)** is stored in `brody`'s `.env` and local Vault as secondary failover (`1` single HTTP call with `"model": "nvidia/nemotron-3-ultra-550b-a55b:free"`, `"models": ["google/gemma-4-31b-it:free", "openrouter/free"]`, max 48 calls/day).

---

## ⚡ 1. INSTANT 1-SHOT SSH COMMANDS TO `brody` (`34.28.19.242`)
- **Read-Only Fast Status (< 0.4s):**
  `ssh -F /dev/null -o IdentityAgent=none -o IdentitiesOnly=yes -i ~/.ssh/brody_ed25519 -o StrictHostKeyChecking=no zavattoni_giacomo@34.28.19.242 "/home/zavattoni_giacomo/openclaw-trader/venv/bin/python /home/zavattoni_giacomo/openclaw-trader/scripts/brody_fast_status.py"`
- **Run 5-Block Verification & Self-Test Suite:**
  `ssh -F /dev/null -o IdentityAgent=none -o IdentitiesOnly=yes -i ~/.ssh/brody_ed25519 -o StrictHostKeyChecking=no zavattoni_giacomo@34.28.19.242 "/home/zavattoni_giacomo/openclaw-trader/venv/bin/python /home/zavattoni_giacomo/openclaw-trader/scripts/test_all_blocks.py"`

---

## 🧩 2. THE 5 SYSTEM BLOCKS & EXACT FILE MAP (`openclaw-trader`)

| Block | File Path | Key Classes / Functions | Mathematical & Flow Invariants |
| :--- | :--- | :--- | :--- |
| **Block 1: Universe Scanner** | `core/universe_scanner.py` | `PredatorUniverseScanner.scan_okx_usdc_universe` | • Excludes synthetic `X*` equities (`XSOXL`, `XNVDA`).<br>• Never drops held coins (`coin in held_coins`).<br>• Rejects thin/erratic pump-and-dump coins (`vol < $500k`, `spread > 5.8 bps`, or `range_24h > 16.5%`). |
| **Block 2: Microstructure & RLS/Kalman** | `core/microstructure.py`<br>`core/predictor.py` | `MicrostructureEngine`<br>`PredatorPredictiveEngine.evaluate` | • Cont-Stoikov 5-level OFI, VPIN toxicity, Hawkes burst.<br>• 2-State Kalman velocity + Online RLS (`d=6`, `P_t` persisted).<br>• 5-Horizon Macro Veto: discounts 1h bounce by 80% if `2h < -20`, `6h < -25`, `12h < -35`, or `24h < -45 bps`. |
| **Block 3: 5-Horizon Kronos Oracle** | `scripts/kronos_oracle_server.py`<br>`core/kronos_oracle.py` | `forecast_pair`<br>`_background_refresh_loop` | • Runs on `127.0.0.1:8090` (`/home/zavattoni_giacomo/Kronos/kronos_oracle_server.py`).<br>• Single-worker `PRIORITY_QUEUE` (zero thread leak, `~3.5s/pair`, `380 MB` RAM).<br>• Computes 5 horizons: `1h (12×5m)`, `2h (8×15m)`, `6h (6×1H)`, `12h (12×1H)`, `24h (24×1H)` + `BTC-USDC` included. |
| **Block 4: Dual Free AI Council & Self-Improver** | `agents/llm_council.py`<br>`core/gemini_self_improver.py` | `AdversarialLLMCouncil`<br>`GeminiSelfImprover` | • Primary: Google AI Studio Free Tier (`gemini-3.5-flash-lite` ➔ `3.5-flash` ➔ `3.8-flash`) via `x-goog-api-key`.<br>• Secondary: 1-call OpenRouter Free Router.<br>• `GeminiSelfImprover` anchors to baseline (anti-paralysis) and updates `config/self_improvement_state.json`. |
| **Block 5: Execution, Risk & Calibration** | `predator_daemon.py`<br>`scripts/configure_run.py` | `run_predator_cycle`<br>`load_purified_run_config_dict` | • 100% Post-Only Maker (`tdMode: cash`, 0% leverage).<br>• Requires `has_valid_kronos` (all 5 horizons non-zero in RAM) before any `BUY`.<br>• **Night Dead-Zone Guard (`00:00–06:00 CET`):** requires all 5 Kronos horizons `>= +8..+12 bps` and `OFI >= +0.28`.<br>• **Anti-FOMO 24h Guard:** blocks buying coins up `>= +10%` in 24h unless pulled back `>= -350 bps`.<br>• **6h Stop-Loss Quarantine:** blocks re-buying any coin for 6h after a `CLOSED_STOPLOSS`.<br>• **24/7 Hard Stop (`-4.00%` / `-400 bps`) + Anti-Wick Kronos Shield (`-475 bps` when `6h/12h/24h >= +60 bps`) + Fast Shield (`+38 bps`).** |
