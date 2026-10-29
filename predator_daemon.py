#!/usr/bin/env python3
"""
TRE OS v6.0 (Predator Edition) — Main Autonomous Orchestrator (`predator_daemon.py`)
Combines:
1. Real-Time OKX v5 Market Microstructure Scanner (Cont-Stoikov OFI, VPIN Toxicity Shield, Hawkes Process, Stoikov Micro-Price)
2. Online Streaming RLS + Kalman Velocity Predictor (updates weights live every tick)
3. NeoQuasar/Kronos Foundation Model Oracle (`Kronos-mini` 4.1M / `Kronos-small` 24.7M on `100.125.189.103:8090` or `localhost:8090`)
4. Multi-Agent Adversarial LLM Debate Council (Bull vs Bear vs Judge on OpenRouter Free)
5. 100% Post-Only Maker Execution Engine with Zero-Loss Audit Safeguards:
   - Cost-Basis Floor Protection (`max(openAvgPx, accAvgPx) * 1.0022` minimum SELL price — zero loss sells)
   - Dynamic Profit-Lock Re-Pegging (tightens SELL TP to Best Ask when unrealized gain >= +180 bps)
   - 20% NAV Hard Inventory Cap per asset + Automated Cash Sweeper
   - Full integration with `config/okx_trader.db` (100% Active Spot Allocation)
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import Any, Dict, List, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from agents.llm_council import AdversarialLLMCouncil
from core.kronos_oracle import KronosOracleClient
from core.microstructure import MicrostructureEngine
from core.predator_auditor import PredatorAuditor
from core.predictor import PredatorPredictiveEngine
from core.universe_scanner import PredatorUniverseScanner
from execution.okx_hybrid_executor import OKXNativeClient


# Official 12-Pair Dynamic Liquidity Universe on OKX EEA Spot (v7.0 Sovereign Edition)
# - Core & Ultra-Liquid Expansion: HYPE, ZEC, SOL, SUI, NEAR, UNI, XRP, LINK, RENDER, AVAX
# - Harvest & Retire Mode (`harvest_only=True`): FET, SEI (sells existing inventory in profit above Cost-Basis Floor, then retires from new buys)
DEFAULT_UNIVERSE: Dict[str, Dict[str, Any]] = {
    "HYPE-USDC":   {"coin": "HYPE",   "dec_px": 3, "dec_sz": 3, "harvest_only": False, "liq_bonus": 8.0},
    "ZEC-USDC":    {"coin": "ZEC",    "dec_px": 2, "dec_sz": 4, "harvest_only": False, "liq_bonus": 7.5},
    "SOL-USDC":    {"coin": "SOL",    "dec_px": 2, "dec_sz": 3, "harvest_only": False, "liq_bonus": 5.0},
    "SUI-USDC":    {"coin": "SUI",    "dec_px": 4, "dec_sz": 2, "harvest_only": True,  "liq_bonus": -10.0, "modo3_rally_px": 0.9320},
    "NEAR-USDC":   {"coin": "NEAR",   "dec_px": 3, "dec_sz": 2, "harvest_only": True,  "liq_bonus": -10.0, "modo3_rally_px": 4.620},
    "UNI-USDC":    {"coin": "UNI",    "dec_px": 3, "dec_sz": 2, "harvest_only": False, "liq_bonus": 5.0},
    "XRP-USDC":    {"coin": "XRP",    "dec_px": 4, "dec_sz": 2, "harvest_only": False, "liq_bonus": 4.5},
    "LINK-USDC":   {"coin": "LINK",   "dec_px": 3, "dec_sz": 2, "harvest_only": False, "liq_bonus": 3.0},
    "RENDER-USDC": {"coin": "RENDER", "dec_px": 3, "dec_sz": 2, "harvest_only": True,  "liq_bonus": -5.0, "modo3_rally_px": 1.7250},
    "AVAX-USDC":   {"coin": "AVAX",   "dec_px": 3, "dec_sz": 2, "harvest_only": True,  "liq_bonus": -10.0, "modo3_rally_px": 9.020},
    "FET-USDC":    {"coin": "FET",    "dec_px": 4, "dec_sz": 1, "harvest_only": True,  "liq_bonus": -10.0, "modo3_rally_px": 0.1775},
    "SEI-USDC":    {"coin": "SEI",    "dec_px": 5, "dec_sz": 1, "harvest_only": True,  "liq_bonus": -15.0, "modo3_rally_px": 0.05330},
}

MODO3_24H_DEADLINE_ISO = "2026-10-28T07:05:00Z"  # 24h Modo 3 Purified Run Unwind Deadline

BASELINE_NAV_USDC = float(os.environ.get("BASELINE_NAV_USDC") or 298.89)  # Configurable Starting Capital X USDC (or via config/purified_run_config.json)
RUN_START_ISO = os.environ.get("RUN_START_ISO") or "2026-10-22T19:00:00Z"
RUN_START_TS_MS = int(os.environ.get("RUN_START_TS_MS") or 1792695600000)
GOLDEN_RULE_DAILY_MIN_PCT = 0.70
GOLDEN_RULE_DAILY_MAX_PCT = 5.00


def load_purified_run_config_dict(base_dir: str) -> Dict[str, Any]:
    """
    Loads full user-calibrated run parameters from config/purified_run_config.json (or env vars).
    Supports custom starting capital (or AUTO detection), custom expiry date (or NONE),
    custom Two-Chamber split, and custom Hard Max-Loss / Fast-Shield thresholds.
    """
    cfg_path = os.path.join(base_dir, "config", "purified_run_config.json")
    default_cfg: Dict[str, Any] = {
        "baseline_nav_usdc": BASELINE_NAV_USDC,
        "auto_detect_baseline_on_start": False,
        "run_start_iso": RUN_START_ISO,
        "run_start_ts_ms": RUN_START_TS_MS,
        "purified_two_chamber_mode": False,
        "expiry_iso": os.environ.get("RUN_EXPIRY_ISO") or DEFAULT_EXPIRY_ISO,
        "cashout_taper_days": float(os.environ.get("CASHOUT_TAPER_DAYS") or DEFAULT_CASHOUT_DAYS),
        "chamber1_assault_pct": 0.63,
        "chamber2_shield_pct": 0.37,
        "max_loss_cap_bps": -400.0,
        "fast_shield_trigger_bps": 38.0,
        "daily_min_pct": GOLDEN_RULE_DAILY_MIN_PCT,
        "daily_max_pct": GOLDEN_RULE_DAILY_MAX_PCT,
    }
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                c = json.load(f)
            for k, v in c.items():
                default_cfg[k] = v
        except Exception:
            pass
    return default_cfg


def load_purified_run_config(base_dir: str) -> Tuple[float, str, int, bool]:
    c = load_purified_run_config_dict(base_dir)
    raw_b = c.get("baseline_nav_usdc")
    b_val = float(raw_b) if isinstance(raw_b, (int, float)) and float(raw_b) > 0 else BASELINE_NAV_USDC
    return (
        b_val,
        str(c.get("run_start_iso") or RUN_START_ISO),
        int(c.get("run_start_ts_ms") or RUN_START_TS_MS),
        bool(c.get("purified_two_chamber_mode", False)),
    )

# Universal Configurable Run Expiration & Intelligent Cashout Engine (Default for Active Production Run: 2026-12-31T21:00:00Z, 6.0-day Taper)
DEFAULT_EXPIRY_ISO = "2026-12-31T21:00:00Z"
DEFAULT_CASHOUT_DAYS = 6.0


def evaluate_run_lifecycle(
    expiry_iso: str = "",
    cashout_days: float = DEFAULT_CASHOUT_DAYS,
    now_utc: Optional[datetime.datetime] = None,
) -> Dict[str, Any]:
    """
    Universal Run Expiration & 4-Stage Intelligent Cashout Engine.
    Allows any GitHub operator to configure a target expiration date (`RUN_EXPIRY_ISO` / `--expiry-iso`)
    and preparation window (`CASHOUT_TAPER_DAYS` / `--cashout-days`, default: 6.0 days).
    Stages:
      - Stage 0 (`ACTIVE_COMPOUNDING`, > cashout_days left): 100% reinvestment + Cannibal Ratchet anti-bubble shield.
      - Stage 1 (`CASHOUT_STAGE_1_VAULT_50`, 3.0d .. cashout_days left): 50% of USDC locked in Vault, 50% only on V-rebounds.
      - Stage 2 (`CASHOUT_STAGE_2_REDUCE_ONLY`, 0.25d .. 3.0d left): 0 new buys (100% USDC locked), 100% Ratchet subsidy, Fee-Safe +24bps TP.
      - Stage 3 (`CASHOUT_STAGE_3_FINAL_SETTLEMENT`, <= 0.25d [6h] left): 100% Post-Only Maker Best-Ask settlement -> 100% USDC, 0% Crypto!
    """
    eff_expiry = (expiry_iso or os.environ.get("RUN_EXPIRY_ISO") or DEFAULT_EXPIRY_ISO).strip()
    try:
        eff_taper_days = float(os.environ.get("CASHOUT_TAPER_DAYS") or cashout_days or DEFAULT_CASHOUT_DAYS)
    except Exception:
        eff_taper_days = DEFAULT_CASHOUT_DAYS

    if not eff_expiry or eff_expiry.upper() in ("NONE", "NEVER", "0"):
        return {
            "expiry_iso": "NONE",
            "cashout_days": eff_taper_days,
            "days_remaining": 9999.0,
            "hours_remaining": 239976.0,
            "stage": "ACTIVE_COMPOUNDING",
            "vault_lock_ratio": 0.0,
            "reduce_only": False,
            "final_settlement": False,
            "ratchet_pool_share": 0.20,
        }

    now_dt = now_utc or datetime.datetime.now(datetime.timezone.utc)
    try:
        exp_dt = datetime.datetime.fromisoformat(eff_expiry.replace("Z", "+00:00"))
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        exp_dt = datetime.datetime(2026, 12, 31, 21, 0, 0, tzinfo=datetime.timezone.utc)

    rem_sec = (exp_dt - now_dt).total_seconds()
    rem_hours = round(rem_sec / 3600.0, 2)
    rem_days = round(rem_sec / 86400.0, 3)

    if rem_hours <= 6.0:
        return {
            "expiry_iso": eff_expiry,
            "cashout_days": eff_taper_days,
            "days_remaining": rem_days,
            "hours_remaining": rem_hours,
            "stage": "CASHOUT_STAGE_3_FINAL_SETTLEMENT",
            "vault_lock_ratio": 1.0,
            "reduce_only": True,
            "final_settlement": True,
            "ratchet_pool_share": 1.0,
        }
    if rem_days <= 3.0:
        return {
            "expiry_iso": eff_expiry,
            "cashout_days": eff_taper_days,
            "days_remaining": rem_days,
            "hours_remaining": rem_hours,
            "stage": "CASHOUT_STAGE_2_REDUCE_ONLY",
            "vault_lock_ratio": 1.0,
            "reduce_only": True,
            "final_settlement": False,
            "ratchet_pool_share": 1.0,
        }
    if rem_days <= eff_taper_days:
        return {
            "expiry_iso": eff_expiry,
            "cashout_days": eff_taper_days,
            "days_remaining": rem_days,
            "hours_remaining": rem_hours,
            "stage": "CASHOUT_STAGE_1_VAULT_50",
            "vault_lock_ratio": 0.50,
            "reduce_only": False,
            "final_settlement": False,
            "ratchet_pool_share": 0.50,
        }
    return {
        "expiry_iso": eff_expiry,
        "cashout_days": eff_taper_days,
        "days_remaining": rem_days,
        "hours_remaining": rem_hours,
        "stage": "ACTIVE_COMPOUNDING",
        "vault_lock_ratio": 0.0,
        "reduce_only": False,
        "final_settlement": False,
        "ratchet_pool_share": 0.20,
    }


def load_dotenv(env_path: str) -> Dict[str, str]:
    env_vars: Dict[str, str] = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip('"').strip("'")
                    os.environ.setdefault(k.strip(), env_vars[k.strip()])
    return env_vars


def init_predator_db(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scalp_runs (
            inst_id TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            size REAL NOT NULL,
            price REAL NOT NULL,
            cl_ord_id TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS microstructure_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            inst_id TEXT,
            mid_price REAL,
            micro_price REAL,
            spread_bps REAL,
            obi_top5 REAL,
            ofi_norm REAL,
            vpin_toxicity REAL,
            hawkes_net_burst REAL,
            composite_alpha REAL,
            predicted_return_bps REAL,
            kalman_velocity_bps REAL,
            confidence REAL,
            regime TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS predator_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            inst_id TEXT,
            side TEXT,
            execution_style TEXT,
            size REAL,
            price REAL,
            predicted_bps REAL,
            regime TEXT,
            ord_id TEXT,
            mode TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS predator_fills_ledger (
            trade_id TEXT,
            ord_id TEXT,
            inst_id TEXT,
            side TEXT,
            fill_px REAL,
            fill_sz REAL,
            notional_usd REAL,
            fee_usd REAL,
            exec_type TEXT,
            wacb_px REAL,
            realized_pnl_usd REAL,
            fill_time TEXT,
            PRIMARY KEY (inst_id, trade_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fresh_scalp_tranches (
            trade_id TEXT PRIMARY KEY,
            inst_id TEXT,
            buy_px REAL,
            buy_sz REAL,
            tp_ord_id TEXT,
            tp_px REAL,
            status TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_micro_inst_ts ON microstructure_telemetry(inst_id, timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_micro_ts ON microstructure_telemetry(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fills_time_side ON predator_fills_ledger(fill_time, side)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tranches_status_created ON fresh_scalp_tranches(status, created_at)")
    conn.commit()
    return conn


def _ceil_px(raw_px: float, dec_px: int) -> float:
    """Rounds a price strictly UP (`math.ceil`) to `dec_px` decimals so Fee-Safe Floors never truncate below cost."""
    if raw_px <= 0:
        return 0.0
    factor = float(10 ** dec_px)
    return round(math.ceil((raw_px * factor) - 1e-9) / factor, dec_px)


def _cancel_ok(res: Dict[str, Any]) -> bool:
    """Verifies that OKX `cancel_order` actually succeeded (`code == '0'`)."""
    if not isinstance(res, dict):
        return False
    if str(res.get("code", "")) == "0":
        data = res.get("data")
        if isinstance(data, list) and data:
            s_code = str(data[0].get("sCode", "0"))
            return s_code == "0"
        return True
    return False


_GLOBAL_IO_POOL = ThreadPoolExecutor(max_workers=8)
_UNIVERSE_SCANNER = PredatorUniverseScanner(ttl_sec=600.0, max_dynamic_explorers=6)


def run_predator_cycle(
    client: OKXNativeClient,
    micro_engine: MicrostructureEngine,
    pred_engine: PredatorPredictiveEngine,
    kronos_client: KronosOracleClient,
    council: AdversarialLLMCouncil,
    auditor: PredatorAuditor,
    conn: sqlite3.Connection,
    run_llm_debate: bool = False,
    run_audit: bool = False,
    dry_run: bool = False,
    expiry_iso: str = "",
    cashout_days: float = DEFAULT_CASHOUT_DAYS,
) -> Dict[str, Any]:
    t_cycle_start = time.perf_counter()
    user_run_cfg = load_purified_run_config_dict(BASE_DIR)
    eff_expiry_arg = expiry_iso or str(user_run_cfg.get("expiry_iso") or "")
    eff_cashout_arg = float(user_run_cfg.get("cashout_taper_days") or cashout_days)
    lifecycle = evaluate_run_lifecycle(expiry_iso=eff_expiry_arg, cashout_days=eff_cashout_arg)
    if client.is_authenticated:
        fut_bal = _GLOBAL_IO_POOL.submit(client.get_account_balances)
        fut_ord = _GLOBAL_IO_POOL.submit(client.get_open_orders)
        fut_fil = _GLOBAL_IO_POOL.submit(client.get_recent_fills, "SPOT", 50)
        fut_kro = _GLOBAL_IO_POOL.submit(kronos_client.fetch_forecasts, list(DEFAULT_UNIVERSE.keys()))
        balances = fut_bal.result()
        open_orders = fut_ord.result()
        prefetched_raw_fills = fut_fil.result()
        kronos_forecasts = fut_kro.result()
    else:
        balances = []
        open_orders = []
        prefetched_raw_fills = []
        kronos_forecasts = kronos_client.fetch_forecasts(list(DEFAULT_UNIVERSE.keys()))

    if client.is_authenticated and not balances:
        return {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "error_empty_balances",
            "nav_usdc": 0.0,
            "spot_equity_usd": 0.0,
            "free_usdc": 0.0,
            "frozen_usdc": 0.0,
            "total_usdc_cash": 0.0,
            "active_orders_count": len(open_orders),
            "authenticated": True,
            "simulated_demo": client.simulated_demo,
            "cost_basis_fixes": 0,
            "profit_lock_repegs": 0,
            "telemetry": [],
            "actions": [],
            "llm_debate": None,
            "audit_report": None,
        }

    spot_equity_usd = sum(float(b.get("eqUsd") or 0.0) for b in balances) if balances else 300.36
    nav_usdc = spot_equity_usd
    free_usdc = (
        sum(float(b.get("availBal") or 0.0) for b in balances if b.get("ccy") == "USDC")
        if balances
        else 5.98
    )
    total_usdc = (
        sum(float(b.get("cashBal") or 0.0) for b in balances if b.get("ccy") == "USDC")
        if balances
        else free_usdc
    )

    held_ccys_set = {str(b.get("ccy") or "") for b in balances if float(b.get("eqUsd") or 0.0) >= 0.50}
    active_universe, alpha_radar_top = _UNIVERSE_SCANNER.scan_okx_usdc_universe(
        client=client,
        base_universe=DEFAULT_UNIVERSE,
        held_coins=held_ccys_set,
    )
    extra_explorer_pairs = [p for p in active_universe.keys() if p not in kronos_forecasts]
    if extra_explorer_pairs:
        try:
            kronos_forecasts.update(kronos_client.fetch_forecasts(extra_explorer_pairs))
        except Exception:
            pass
    tracked_ccys = {m["coin"] for m in active_universe.values()} | {"USDC"}

    # Build strict cost-basis (`max(openAvgPx, accAvgPx)`) and holdings summary from live OKX account
    cost_basis_map: Dict[str, float] = {}
    holdings_summary: List[Dict[str, Any]] = []
    for b in balances:
        ccy = str(b.get("ccy") or "")
        if ccy in tracked_ccys and ccy != "USDC":
            cash_bal = float(b.get("cashBal") or 0.0)
            eq_usd = float(b.get("eqUsd") or 0.0)
            open_avg = float(b.get("openAvgPx") or 0.0)
            acc_avg = float(b.get("accAvgPx") or 0.0)
            effective_cost = open_avg if open_avg > 0 else acc_avg
            upl = float(b.get("spotUpl") or b.get("totalPnl") or 0.0)
            if effective_cost > 0:
                cost_basis_map[ccy] = effective_cost
            if eq_usd > 0.25:
                holdings_summary.append(
                    {
                        "ccy": ccy,
                        "qty": round(cash_bal, 4),
                        "eq_usd": round(eq_usd, 2),
                        "open_avg_px": round(effective_cost, 6),
                        "upl_usd": round(upl, 2),
                    }
                )

    # Sync recent OKX fills into both SQLite tables (`predator_fills_ledger` and `trade_ledger`)
    # and register new BUY fills (>= RUN_START_ISO) in `fresh_scalp_tranches` for independent Quick-Scalp TPs!
    active_tranche_ord_ids: set[str] = set()
    active_tranches_by_inst: Dict[str, List[tuple]] = {}
    recent_sell_cooldown_map: Dict[str, Tuple[float, float]] = {}  # inst_id -> (last_sell_px, minutes_ago)
    if client.is_authenticated:
        try:
            raw_fills = prefetched_raw_fills
            auditor.sync_okx_fills(
                conn=conn,
                raw_fills=raw_fills,
                open_avg_px_map=cost_basis_map,
                allowed_pairs=set(active_universe.keys()),
            )
            cur_tr = conn.cursor()
            # Track recent SELL fills (< 45 mins ago) for Re-Entry Pullback Guard (-25 bps discount required)
            cur_tr.execute(
                """
                SELECT inst_id, fill_px, (julianday('now') - julianday(fill_time)) * 1440.0 AS mins_ago
                FROM predator_fills_ledger
                WHERE side='sell' AND datetime(fill_time) >= datetime('now', '-45 minutes')
                ORDER BY fill_time DESC
                """
            )
            for s_inst, s_px, s_mins in cur_tr.fetchall():
                if str(s_inst) not in recent_sell_cooldown_map:
                    recent_sell_cooldown_map[str(s_inst)] = (float(s_px or 0.0), float(s_mins or 0.0))

            cur_tr.execute(
                """
                SELECT trade_id, inst_id, fill_px, fill_sz, fill_time
                FROM predator_fills_ledger
                WHERE side='buy' AND fill_time >= ?
                ORDER BY fill_time ASC
                """,
                (RUN_START_ISO,),
            )
            for t_id, t_inst, t_px, t_sz, t_time in cur_tr.fetchall():
                cur_tr.execute("SELECT 1 FROM fresh_scalp_tranches WHERE trade_id = ?", (t_id,))
                if not cur_tr.fetchone():
                    cur_tr.execute(
                        """
                        INSERT INTO fresh_scalp_tranches (trade_id, inst_id, buy_px, buy_sz, tp_ord_id, tp_px, status, created_at)
                        VALUES (?, ?, ?, ?, '', 0.0, 'PENDING_TP', ?)
                        """,
                        (t_id, t_inst, float(t_px), float(t_sz), str(t_time)),
                    )
            conn.commit()

            open_ord_id_set = {str(o.get("ordId") or "") for o in open_orders}
            cur_tr.execute(
                """
                SELECT trade_id, inst_id, buy_px, buy_sz, tp_ord_id, tp_px, status,
                       (julianday('now') - julianday(created_at)) * 24.0 AS age_hours
                FROM fresh_scalp_tranches
                WHERE status IN ('PENDING_TP', 'TP_PLACED')
                """
            )
            for tr_row in cur_tr.fetchall():
                tr_id, tr_inst, tr_px, tr_sz, tr_oid, tr_tp_px, tr_st, tr_age_h = tr_row
                age_h = float(tr_age_h or 0.0)
                tr_coin = str(tr_inst).split("-")[0]
                live_avg_cost = cost_basis_map.get(tr_coin, 0.0)
                if live_avg_cost > 0 and live_avg_cost < float(tr_px) * 0.998:
                    # Subsequent profitable Quick-Scalp turns lowered this coin's openAvgPx on OKX!
                    # Sync the tranche's buy_px down to the true lowered cost basis so it unlocks immediately at the lowered Floor!
                    tr_px = live_avg_cost
                    cur_tr.execute("UPDATE fresh_scalp_tranches SET buy_px = ? WHERE trade_id = ?", (float(tr_px), tr_id))
                if tr_st == "TP_PLACED" and tr_oid and tr_oid not in open_ord_id_set:
                    # Quick-Scalp TP order was filled (or partially filled and cancelled)! Check total sold quantity
                    cur_tr.execute("SELECT COALESCE(SUM(fill_sz), 0.0) FROM predator_fills_ledger WHERE ord_id = ? AND side='sell'", (tr_oid,))
                    sold_sz = float((cur_tr.fetchone() or (0.0,))[0] or 0.0)
                    if sold_sz >= float(tr_sz) * 0.985:
                        cur_tr.execute("UPDATE fresh_scalp_tranches SET status='CLOSED_PROFIT' WHERE trade_id = ?", (tr_id,))
                    elif sold_sz > 0.0:
                        rem_sz = max(0.0, float(tr_sz) - sold_sz)
                        cur_tr.execute(
                            "UPDATE fresh_scalp_tranches SET buy_sz = ?, status='PENDING_TP', tp_ord_id='' WHERE trade_id = ?",
                            (rem_sz, tr_id),
                        )
                        active_tranches_by_inst.setdefault(tr_inst, []).append((tr_id, float(tr_px), rem_sz, "", 0.0, "PENDING_TP", age_h))
                    else:
                        # Before resetting to PENDING_TP, check if there is already a live SELL order on OKX matching this tranche's size/price!
                        matched_live_ord = next(
                            (
                                o for o in open_orders
                                if o.get("instId") == tr_inst
                                and str(o.get("side") or "").lower() == "sell"
                                and float(o.get("px") or 0) > float(tr_px)
                                and abs(float(o.get("sz") or 0) - float(tr_sz)) / max(float(tr_sz), 0.0001) <= 0.15
                            ),
                            None,
                        )
                        if matched_live_ord:
                            m_oid = str(matched_live_ord.get("ordId") or "")
                            m_px = float(matched_live_ord.get("px") or tr_tp_px)
                            cur_tr.execute("UPDATE fresh_scalp_tranches SET status='TP_PLACED', tp_ord_id=?, tp_px=? WHERE trade_id = ?", (m_oid, m_px, tr_id))
                            active_tranche_ord_ids.add(m_oid)
                            active_tranches_by_inst.setdefault(tr_inst, []).append((tr_id, float(tr_px), float(tr_sz), m_oid, m_px, "TP_PLACED", age_h))
                        else:
                            cur_tr.execute("UPDATE fresh_scalp_tranches SET status='PENDING_TP', tp_ord_id='' WHERE trade_id = ?", (tr_id,))
                            active_tranches_by_inst.setdefault(tr_inst, []).append((tr_id, float(tr_px), float(tr_sz), "", 0.0, "PENDING_TP", age_h))
                else:
                    if tr_oid:
                        active_tranche_ord_ids.add(str(tr_oid))
                    active_tranches_by_inst.setdefault(tr_inst, []).append((tr_id, float(tr_px), float(tr_sz), str(tr_oid), float(tr_tp_px), tr_st, age_h))
            conn.commit()
        except Exception as e:
            print(f"[!] Fresh tranche sync note: {e}")

    # Load latest LLM council directive if present
    convictions: Dict[str, float] = {}
    agg_mult = 1.10
    if council.directive_out_path and os.path.exists(council.directive_out_path):
        try:
            with open(council.directive_out_path, "r", encoding="utf-8") as f:
                saved_dir = json.load(f)
                convictions = saved_dir.get("token_convictions", {})
                agg_mult = float(saved_dir.get("aggressiveness_multiplier", 1.10))
        except Exception:
            pass

    telemetry_rows: List[Dict[str, Any]] = []
    actions_taken: List[Dict[str, Any]] = []
    cost_basis_fixes = 0
    profit_lock_repegs = 0
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    telemetry_tuples: List[tuple] = []
    order_tuples: List[tuple] = []
    scalp_run_updates: List[tuple] = []
    buy_candidates: List[Dict[str, Any]] = []

    # 0A. Parallel Fetch of Orderbooks & Trade Tape for BTC-USDC + all Active & Dynamic Explorer Pairs
    all_scan_pairs = list(dict.fromkeys(["BTC-USDC"] + list(active_universe.keys())))
    prefetched_market: Dict[str, Tuple[Any, Any, Any]] = {}

    def _fetch_one_pair(p_id: str) -> Tuple[str, Tuple[Any, Any, Any]]:
        try:
            b, a = client.get_orderbook(p_id, sz=5)
            tr = client.get_recent_trades(p_id, limit=25)
            return p_id, (b, a, tr)
        except Exception:
            return p_id, ([], [], [])

    for p_id, mdata in _GLOBAL_IO_POOL.map(_fetch_one_pair, all_scan_pairs):
        prefetched_market[p_id] = mdata

    btc_lead_lag_bps = 0.0
    btc_bids, btc_asks, btc_trades = prefetched_market.get("BTC-USDC", ([], [], []))
    if btc_bids and btc_asks:
        btc_sig = micro_engine.process_snapshot("BTC-USDC", btc_bids, btc_asks, btc_trades)
        btc_lead_lag_bps = round(btc_sig.composite_alpha * 18.0, 2)

    # 0B. Ratchet Capital Recycler Pool, Cannibal Ratchet, Darwinian Velocity Map, Intraday Rebound Catcher & Golden Rule Defender
    ratchet_pool_usd = 0.0
    tot_realized_run = 0.0
    velocity_turns_map: Dict[str, int] = {}
    low_2h_map: Dict[str, float] = {}
    high_2h_map: Dict[str, float] = {}
    golden_harvest_mode = False
    try:
        cur_r = conn.cursor()
        cur_r.execute("SELECT SUM(realized_pnl_usd) FROM predator_fills_ledger WHERE fill_time >= ?", (RUN_START_ISO,))
        tot_realized_run = float((cur_r.fetchone() or (0.0,))[0] or 0.0)
        if tot_realized_run >= 0.25:
            ratchet_pool_usd = round(tot_realized_run * float(lifecycle["ratchet_pool_share"]), 4)

        # Darwinian Velocity Bonus: count closed profitable Quick-Scalps per instrument in the last 24h
        cur_r.execute(
            """
            SELECT inst_id, COUNT(*)
            FROM fresh_scalp_tranches
            WHERE status='CLOSED_PROFIT' AND datetime(created_at) >= datetime('now', '-24 hours')
            GROUP BY inst_id
            """
        )
        for v_inst, v_cnt in cur_r.fetchall():
            velocity_turns_map[str(v_inst)] = int(v_cnt or 0)

        # Intraday Rebound Catcher: compute 2h rolling low/high per instrument from SQLite telemetry
        cur_r.execute(
            """
            SELECT inst_id, MIN(mid_price), MAX(mid_price)
            FROM microstructure_telemetry
            WHERE datetime(timestamp) >= datetime('now', '-2 hours') AND mid_price > 0
            GROUP BY inst_id
            """
        )
        for r_inst, r_min, r_max in cur_r.fetchall():
            low_2h_map[str(r_inst)] = float(r_min or 0.0)
            high_2h_map[str(r_inst)] = float(r_max or 0.0)

        # Golden Rule Intraday Profit Defender: check if NAV rose >= +2.00% over 24h ago (or baseline)
        cur_r.execute(
            "SELECT current_nav_usd FROM predator_audit_history WHERE datetime(timestamp) <= datetime('now', '-20 hours') ORDER BY id DESC LIMIT 1"
        )
        row_nav_24h = cur_r.fetchone()
        ref_nav_24h = float(row_nav_24h[0]) if row_nav_24h and float(row_nav_24h[0] or 0) > 0 else BASELINE_NAV_USDC
        if nav_usdc >= ref_nav_24h * 1.020:
            golden_harvest_mode = True
    except Exception:
        ratchet_pool_usd = 0.0

    eff_baseline_nav, eff_run_start_iso, _, is_purified_mode = load_purified_run_config(BASE_DIR)
    # Dynamic Compounding Cap (10.5% of current NAV = ~$30.00 Heavy Bullets in Purified 2-Chamber Mode, 8.5% during Modo 3 transition)
    dynamic_qs_cap_usd = round(max(28.00 if is_purified_mode else 24.50, nav_usdc * (0.105 if is_purified_mode else 0.085)), 2)
    quick_lock_trigger_bps = 24.0 if golden_harvest_mode else 28.0
    quick_lock_floor_mult = 1.0024 if golden_harvest_mode else 1.0026  # Strictly >= +24..+26 bps to cover 20 bps round-trip OKX Maker fee + guaranteed net profit!

    # Session & Global Regime Awareness (Asia 00-07 UTC, Europe 07-13 UTC, US 13-21 UTC, Weekend Liquidity Guard)
    now_utc_dt = datetime.datetime.now(datetime.timezone.utc)
    is_weekend = now_utc_dt.weekday() in (5, 6)
    utc_hour = now_utc_dt.hour
    session_tp_mult = 1.15 if (13 <= utc_hour <= 21 and not is_weekend) else (0.95 if is_weekend else 1.05)

    # Orthogonal OKX Perpetual Swap Basis Radar (cached 120s -> 0.00ms loop cost, 0 MB RAM!)
    perp_swap_px_map, _ = client.get_perp_radar_snapshot([m["coin"] for m in active_universe.values()])

    # 0C. TRE OS v9.0 — Macro Portfolio Equilibrium Engine (3 Universal Homeostatic Pillars):
    # Pillar 1: Working Capital Ratio = (total_usdc + fresh_tranches_under_6h_usd + recent_hype_scalps) / nav_usdc (Target >= 35.0% NAV)
    fresh_qs_under_6h_usd = sum(
        float(tr[1]) * float(tr[2])
        for tr_list in active_tranches_by_inst.values()
        for tr in tr_list
        if float(tr[6] or 0.0) <= 6.0
    )
    working_capital_usd = round(total_usdc + fresh_qs_under_6h_usd, 2)
    working_capital_ratio = round(working_capital_usd / max(1.0, nav_usdc), 4)
    macro_liquidity_rebalance_active = bool(working_capital_ratio < 0.35)

    # Pillar 2: Universal Dynamic Single-Asset Concentration Cap (12.5% when Working Capital < 35%, 15.0% when >= 35%)
    universal_max_inv_weight = 0.125 if macro_liquidity_rebalance_active else 0.150

    # Pillar 3: Macro Market Regime Classifier & Adaptive Bullet Sizing (`MACRO_BULL_EXPANSION`, `MACRO_RANGE_ROTATION`, `MACRO_BEAR_DEFENSIVE`)
    k2h_vals = [fc.macro_return_2h_bps for fc in kronos_forecasts.values()] if kronos_forecasts else [0.0]
    avg_k2h_bps = round(sum(k2h_vals) / max(1, len(k2h_vals)), 2)
    if avg_k2h_bps >= 10.0 and btc_lead_lag_bps >= -3.0:
        macro_portfolio_regime = "MACRO_BULL_EXPANSION"
        macro_bullet_cap_usd = dynamic_qs_cap_usd
    elif avg_k2h_bps <= -15.0 or btc_lead_lag_bps <= -10.0:
        macro_portfolio_regime = "MACRO_BEAR_DEFENSIVE"
        macro_bullet_cap_usd = round(max(16.50, nav_usdc * 0.058), 2)
    else:
        macro_portfolio_regime = "MACRO_RANGE_ROTATION"
        macro_bullet_cap_usd = round(max(22.50, nav_usdc * 0.080), 2)

    macro_equilibrium_summary = {
        "working_capital_usd": working_capital_usd,
        "working_capital_ratio_pct": round(working_capital_ratio * 100.0, 2),
        "target_working_capital_pct": 35.0,
        "liquidity_rebalance_active": macro_liquidity_rebalance_active,
        "universal_max_inv_weight_pct": round(universal_max_inv_weight * 100.0, 2),
        "macro_portfolio_regime": macro_portfolio_regime,
        "avg_kronos_2h_bps": avg_k2h_bps,
        "macro_bullet_cap_usd": macro_bullet_cap_usd,
    }

    macro_equilibrium_summary["dynamic_explorers_active"] = [
        k for k, v in active_universe.items() if v.get("is_dynamic_explorer")
    ]
    macro_equilibrium_summary["alpha_radar_top5"] = [
        {"inst_id": x["inst_id"], "range_24h_pct": x["range_24h_pct"], "chg_24h_pct": x["chg_24h_pct"], "pred_rank": x["pred_rank"]}
        for x in alpha_radar_top[:5]
    ]

    # 1. Scan all instruments in active_universe (Core + Dynamic Predator Explorers) using prefetched parallel market snapshots
    for inst_id, meta in active_universe.items():
        bids, asks, trades = prefetched_market.get(inst_id, ([], [], []))
        if not bids or not asks:
            continue

        sig = micro_engine.process_snapshot(inst_id, bids, asks, trades)

        coin = meta["coin"]
        dec_px = meta["dec_px"]
        dec_sz = meta["dec_sz"]

        token_bal_obj = next((b for b in balances if b.get("ccy") == coin), {})
        token_eq = float(token_bal_obj.get("eqUsd") or 0.0)
        cash_token_qty = float(token_bal_obj.get("cashBal") or 0.0)
        avail_token_qty = float(token_bal_obj.get("availBal") or 0.0)
        open_avg_px = cost_basis_map.get(coin, 0.0)

        inv_weight = (token_eq / nav_usdc) if nav_usdc > 0 else 0.0
        llm_bias = float(convictions.get(inst_id, 0.0))

        k_fc = kronos_forecasts.get(inst_id)
        k_ret_bps = k_fc.expected_return_1h_bps if k_fc else 0.0
        k_up_bps = k_fc.upside_high_bps if k_fc else 0.0
        k_down_bps = k_fc.downside_low_bps if k_fc else 0.0
        k_macro_2h_bps = k_fc.macro_return_2h_bps if k_fc else 0.0
        k_6h_bps = k_fc.horizon_6h_bps if k_fc else 0.0
        k_swing_12h_bps = k_fc.swing_return_12h_bps if k_fc else 0.0
        k_24h_bps = k_fc.daily_return_24h_bps if k_fc else 0.0
        k_vol_1h_bps = k_fc.pred_volatility_1h_bps if k_fc else 25.0
        k_tp_prob = k_fc.tp_touch_prob_1h if k_fc else 0.50
        k_zscore = k_fc.kronos_zscore_1h if k_fc else 0.0
        k_vol_surge = k_fc.pred_volume_surge_ratio if k_fc else 1.0
        k_aligned = k_fc.horizon_aligned if k_fc else False
        harvest_only = bool(meta.get("harvest_only", False))
        liq_bonus = float(meta.get("liq_bonus", 0.0))

        pred = pred_engine.evaluate(
            sig,
            inventory_weight_nav=inv_weight,
            llm_conviction_bias=llm_bias,
            kronos_return_1h_bps=k_ret_bps,
            kronos_upside_bps=k_up_bps,
            kronos_downside_bps=k_down_bps,
            kronos_macro_2h_bps=k_macro_2h_bps,
            kronos_6h_bps=k_6h_bps,
            kronos_swing_12h_bps=k_swing_12h_bps,
            kronos_24h_bps=k_24h_bps,
            kronos_horizon_aligned=k_aligned,
            btc_lead_lag_bps=btc_lead_lag_bps,
        )

        # Enforce 100% Post-Only Maker in Production Live (0.00% Taker Fee Drag)
        allow_ioc = False

        # Calculate Cost-Basis Floor (+25 bps minimum gross over openAvgPx = 20 bps round-trip Maker fee + net profit, with Micro-Slice Ratchet discount!)
        raw_floor_mult = 1.0025
        unrealized_bps = ((sig.mid_price - open_avg_px) / open_avg_px * 10000.0) if open_avg_px > 0 else 0.0
        ratchet_sub_applied = 0.0
        if ratchet_pool_usd > 0.05 and -450.0 <= unrealized_bps < 0.0 and token_eq > 5.0:
            # Micro-Slice Ratchet Unlock: calculate bps relief over a $10.00 slice, but NEVER drop below 1.0021 (round-trip Maker fee breakeven + 1bp)!
            effective_slice_usd = min(token_eq, 10.0)
            ratchet_bps_relief = min(4.0, (ratchet_pool_usd / effective_slice_usd) * 10000.0)
            raw_floor_mult = max(1.0021, 1.0025 - (ratchet_bps_relief / 10000.0))
            ratchet_sub_applied = round(ratchet_pool_usd, 4)
        cost_floor_px = _ceil_px(open_avg_px * raw_floor_mult, dec_px) if open_avg_px > 0 else 0.0
        # TRE OS v9.0 — Universal Macro Liquidity Rebalance & Overweight De-Concentration Rule:
        # Instead of hardcoding specific coins, applies universally to ANY asset in the portfolio when Working Capital Ratio < 35% NAV:
        # - Case A (Overweight Asset > 12.5% NAV, e.g. SUI 18.3%): when price rallies within -320 bps (-3.2%) of openAvgPx AND net exit cost
        #   is within the authorized $1.75 calibration budget, unlock at best_ask to restore portfolio equilibrium!
        # - Case B (Standard Legacy Block >= 6% NAV, e.g. SOL, RENDER, LINK): when price rallies within -140 bps (-1.4%) of openAvgPx AND net exit
        #   cost is <= $0.45 USDC, unlock at best_ask to rebuild Working Capital toward the 35% target!
        est_net_exit_loss_usd = max(0.0, (open_avg_px - (sig.mid_price * 0.999)) * cash_token_qty) if open_avg_px > 0 else 0.0
        is_macro_overweight_deconcentrate = bool(
            macro_liquidity_rebalance_active
            and inv_weight > universal_max_inv_weight
            and -325.0 <= unrealized_bps < 0.0
            and est_net_exit_loss_usd <= 1.75
        )
        is_macro_liquidity_unlock = False  # Strict Zero-Loss Floor on all active positions; only explicit Modo 3 legacy blocks unwind on rally!
        # Modo 3 (24h Purified Run Unwind): unwind the 5 legacy blocks (SUI, NEAR, AVAX, FET, SEI) on intraday US/EU rally targets
        # (or automatically in the final 4h of the 24h window) while locking freed USDC in the Purified Run Vault!
        modo3_rally_px = float(meta.get("modo3_rally_px") or 0.0)
        rem_modo3_hours = (
            datetime.datetime.fromisoformat(MODO3_24H_DEADLINE_ISO.replace("Z", "+00:00")) - now_utc_dt
        ).total_seconds() / 3600.0
        is_modo3_legacy_unwind = bool(
            modo3_rally_px > 0.0
            and token_eq >= 3.0
            and (sig.mid_price >= modo3_rally_px or rem_modo3_hours <= 4.0)
        )
        if (is_macro_overweight_deconcentrate or is_macro_liquidity_unlock or is_modo3_legacy_unwind) and cost_floor_px > 0:
            cost_floor_px = min(cost_floor_px, round(asks[0][0], dec_px))

        active_qs_usd = sum(tr[1] * tr[2] for tr in active_tranches_by_inst.get(inst_id, []))
        vel_turns = velocity_turns_map.get(inst_id, 0)
        vel_bonus = min(10.0, vel_turns * 2.5)

        # Intraday Rebound Catcher: detect V-reversal bounce off 2h low (+15..+120 bps from 2h low while still discounted from 2h high)
        low_2h = low_2h_map.get(inst_id, sig.mid_price)
        high_2h = high_2h_map.get(inst_id, sig.mid_price)
        bounce_from_low_bps = ((sig.mid_price - low_2h) / low_2h * 10000.0) if low_2h > 0 else 0.0
        drop_from_high_bps = ((high_2h - sig.mid_price) / high_2h * 10000.0) if high_2h > 0 else 0.0
        is_rebound_leader = bool(
            not harvest_only
            and 12.0 <= bounce_from_low_bps <= 130.0
            and drop_from_high_bps >= 25.0
            and sig.ofi_norm >= 0.15
            and sig.vpin_toxicity < 0.65
            and (k_ret_bps > -15.0 or pred.kalman_velocity_bps > 0.0)
        )
        rebound_bonus = round(min(18.0, (bounce_from_low_bps * 0.22) + (sig.ofi_norm * 10.0)), 2) if is_rebound_leader else 0.0
        # TRE OS v10.3 — Adaptive Trailing Maker Dip-Sniper (Post-Audit Council Upgrade: Qwen2.5-Coder + Nemotron-3.5-Lightning):
        # When pullback >= 32 bps from 2h high AND Kronos TP Touch Prob >= 0.67 + OFI >= +0.40, tighten passive Maker BUY trap
        # to join Best Bid (~6-10 bps) so we capture V-reversals immediately as 100% Maker without missing the bounce!
        if (drop_from_high_bps >= 32.0 or is_rebound_leader) and k_tp_prob >= 0.67 and sig.ofi_norm >= 0.40:
            raw_offset = round(max(6.0, min(12.0, sig.spread_bps * 0.8 + 4.0)), 1)
        elif is_rebound_leader:
            raw_offset = round(max(10.0, pred.recommended_buy_offset_bps * 0.65), 1)
        else:
            raw_offset = max(18.0, pred.recommended_buy_offset_bps)
        eff_buy_offset_bps = raw_offset

        # 5-Horizon Perspective Score (2h + 6h + 12h + 24h) + Cross-Sectional Relative Strength vs BTC:
        btc_fc = kronos_forecasts.get("BTC-USDC")
        btc_k1h = btc_fc.expected_return_1h_bps if btc_fc else 0.0
        btc_k6h = btc_fc.horizon_6h_bps if btc_fc else 0.0
        rel_strength_bonus = 4.0 if (k_ret_bps > btc_k1h + 8.0 and k_6h_bps > btc_k6h and k_6h_bps >= -10.0) else 0.0
        macro_swing_bonus = round(
            max(-15.0, min(18.0, (k_macro_2h_bps * 0.06) + (k_6h_bps * 0.04) + (k_swing_12h_bps * 0.03) + (k_24h_bps * 0.02) + rel_strength_bonus)),
            2,
        )

        # Speculative Bubble / Parabolic Blow-Off Guard: if token is already at the very top of its 2h range (< 8 bps from 2h high)
        # AND has surged > +180 bps from 2h low, block chasing the top unless all 3 Kronos horizons are aligned!
        is_bubble_top = bool(bounce_from_low_bps >= 180.0 and drop_from_high_bps < 8.0 and not k_aligned)

        # Adaptive Upside Runner Multiplier: when 1h/2h/12h horizons and L2 OFI all point strongly up,
        # let winners run up to +85..+140 bps (and up to +160 bps in speculative bubble rallies)!
        is_upside_runner = bool(
            pred.predicted_return_bps >= 8.0
            and sig.ofi_norm >= 0.25
            and (k_macro_2h_bps >= 15.0 or k_swing_12h_bps >= 60.0)
        )

        # Legacy Cost-Basis Averaging Bonus: when a legacy block (e.g. SOL, UNI, SUI, LINK, RENDER) is discounted (-150..-900 bps)
        # AND has positive Kronos 1h or positive OFI, award a bonus (+6.5 pts) so Quick-Scalps also pull down its openAvgPx for free!
        legacy_averaging_bonus = 6.5 if (not harvest_only and -950.0 <= unrealized_bps <= -150.0 and (k_ret_bps > 0.0 or sig.ofi_norm > 0.15)) else 0.0

        # Kronos Paper Eq. 12 Realized Volatility Bonus & Pre-Mean Trajectory Orthogonal Signals (`tp_touch_prob`, `zscore`, `vol_surge`):
        vol_scalp_bonus = round(min(6.0, max(0.0, (k_vol_1h_bps - 25.0) * 0.10)), 2) if k_ret_bps >= -5.0 else 0.0
        tp_prob_bonus = round((k_tp_prob - 0.50) * 10.0, 2)  # -5.0 to +5.0 pts based on pre-mean trajectory probability of touching >= +26 bps
        zscore_bonus = round(max(-8.0, min(8.0, k_zscore * 4.5)), 2)  # Cross-sectional volatility-normalized return rank (qlib_test.py)
        vol_surge_bonus = round(min(3.5, max(-1.5, (k_vol_surge - 1.0) * 3.0)), 2)

        # Orthogonal OKX Perpetual Swap Basis Radar (`perp_basis_bps`):
        # When Perp trades at a deep discount (< -6 bps below Spot) while Spot OFI >= +0.15 and Kronos >= 0 -> Short Squeeze Boost (+4.5 pts)!
        # When Perp trades at an overheated premium (> +15 bps above Spot) while VPIN >= 0.65 -> Long-Squeeze Danger Penalty (-6.0 pts)!
        swap_px = perp_swap_px_map.get(coin, sig.mid_price)
        perp_basis_bps = round(((swap_px - sig.mid_price) / sig.mid_price) * 10000.0, 2) if (sig.mid_price > 0 and swap_px > 0) else 0.0
        perp_squeeze_bonus = 4.5 if (perp_basis_bps <= -6.0 and sig.ofi_norm >= 0.15 and k_ret_bps >= -2.0) else (
            -6.0 if (perp_basis_bps >= 15.0 and sig.vpin_toxicity >= 0.65) else 0.0
        )

        calc_opp_score = round(
            pred.predicted_return_bps
            + (sig.composite_alpha * 15.0)
            + liq_bonus
            + vel_bonus
            + rebound_bonus
            + macro_swing_bonus
            + legacy_averaging_bonus
            + vol_scalp_bonus
            + tp_prob_bonus
            + zscore_bonus
            + vol_surge_bonus
            + perp_squeeze_bonus
            + (4.0 if k_aligned and k_ret_bps > 0 else 0.0)
            - (sig.vpin_toxicity * 20.0)
            - (inv_weight * 50.0),
            2,
        )

        row_dict = {
            "inst_id": inst_id,
            "symbol": coin,
            "universe_mode": "HARVEST_RETIRE" if harvest_only else "ACTIVE_ULTRA_LIQUID",
            "mid_price": round(sig.mid_price, dec_px),
            "micro_price": round(sig.micro_price, dec_px),
            "open_avg_px": round(open_avg_px, dec_px) if open_avg_px > 0 else 0.0,
            "cost_basis_floor_px": cost_floor_px,
            "holding_size": round(cash_token_qty, dec_sz),
            "holding_eq_usd": round(token_eq, 2),
            "inv_weight_pct": round(inv_weight * 100.0, 2),
            "unrealized_bps": round(unrealized_bps, 1),
            "unrealized_usd": round((sig.mid_price - open_avg_px) * cash_token_qty, 2) if open_avg_px > 0 else 0.0,
            "spread_bps": round(sig.spread_bps, 2),
            "obi_top5": round(sig.obi_top5, 3),
            "ofi_norm": round(sig.ofi_norm, 3),
            "vpin_toxicity": round(sig.vpin_toxicity, 3),
            "hawkes_intensity": round(sig.hawkes_net_burst, 3),
            "hawkes_net_burst": round(sig.hawkes_net_burst, 3),
            "composite_alpha": round(sig.composite_alpha, 3),
            "kronos_1h_bps": round(k_ret_bps, 2),
            "kronos_2h_bps": round(k_macro_2h_bps, 2),
            "kronos_2h_macro_bps": round(k_macro_2h_bps, 2),
            "kronos_6h_bps": round(k_6h_bps, 2),
            "kronos_12h_bps": round(k_swing_12h_bps, 2),
            "kronos_24h_bps": round(k_24h_bps, 2),
            "kronos_aligned": k_aligned,
            "horizon_aligned": k_aligned,
            "kronos_high_bps": round(k_up_bps, 2),
            "kronos_low_bps": round(k_down_bps, 2),
            "tp_touch_prob_1h": round(k_tp_prob, 3),
            "kronos_zscore_1h": round(k_zscore, 3),
            "pred_volume_surge_ratio": round(k_vol_surge, 2),
            "perp_basis_bps": perp_basis_bps,
            "rls_kalman_bps": round(pred.kalman_velocity_bps, 2),
            "kronos_blend_bps": round(0.75 * k_ret_bps + 0.25 * k_macro_2h_bps, 2),
            "llm_council_bps": round(llm_bias * 12.0, 2),
            "btc_lead_lag_contrib_bps": round(btc_lead_lag_bps, 2),
            "predicted_return_bps": pred.predicted_return_bps,
            "kalman_velocity_bps": pred.kalman_velocity_bps,
            "rebound_from_low_bps": round(bounce_from_low_bps, 1),
            "rebound_bonus": rebound_bonus,
            "is_rebound_leader": is_rebound_leader,
            "opp_score": calc_opp_score,
            "anti_stacking_locked": bool(active_qs_usd >= dynamic_qs_cap_usd * 0.92 or inv_weight >= 0.20),
            "confidence": pred.confidence,
            "regime": "REBOUND_CATCHER" if is_rebound_leader else pred.regime,
            "buy_offset_bps": eff_buy_offset_bps,
            "sell_tp_bps": pred.recommended_sell_tp_bps,
            "active_buy_px": None,
            "active_sell_px": None,
            "ratchet_subsidy_applied_usd": ratchet_sub_applied,
            "allow_sniper_IOC": allow_ioc,
            "updated_at": now_iso,
        }
        telemetry_rows.append(row_dict)

        telemetry_tuples.append(
            (
                now_iso,
                inst_id,
                sig.mid_price,
                sig.micro_price,
                sig.spread_bps,
                sig.obi_top5,
                sig.ofi_norm,
                sig.vpin_toxicity,
                sig.hawkes_net_burst,
                sig.composite_alpha,
                pred.predicted_return_bps,
                pred.kalman_velocity_bps,
                pred.confidence,
                pred.regime,
            )
        )

        # 2. Audit & Self-Heal Active Orders (Stale BUY Chaser + Cost-Basis Floor Rescue + Profit-Lock Re-Peg)
        inst_orders = [o for o in open_orders if o.get("instId") == inst_id]
        has_buy_order = False
        has_sell_order = False
        active_ord_id = ""
        active_ord_px = 0.0
        active_ord_sz = 0.0
        active_state = "CLOSED"

        for ord_obj in inst_orders:
            try:
                ord_px = float(ord_obj.get("px") or 0.0)
                ord_sz = float(ord_obj.get("sz") or 0.0)
                ord_side = str(ord_obj.get("side") or "").lower()
                ord_id = str(ord_obj.get("ordId") or "")
                if ord_px <= 0 or sig.mid_price <= 0:
                    continue
                drift_bps = abs(ord_px - sig.mid_price) / sig.mid_price * 10000.0

                if ord_side == "buy":
                    has_buy_order = True
                    active_state = "BUY_SUBMITTED"
                    active_ord_id = ord_id
                    active_ord_px = ord_px
                    active_ord_sz = ord_sz
                    # Fast-Cycle Stale BUY Re-Pegging + Cashout Stage 2/3 Buy Purge:
                    # Cancel BUY order if drifted > 22 bps away (or > 95 bps in TOXIC_DIP_DEFENSE), if inventory >= 22% NAV, or if in Cashout Stage 2/3!
                    max_buy_drift_bps = 95.0 if pred.regime == "TOXIC_DIP_DEFENSE" else 22.0
                    if drift_bps > max_buy_drift_bps or inv_weight >= 0.22 or lifecycle["reduce_only"] or lifecycle["final_settlement"]:
                        if dry_run:
                            has_buy_order = False
                            actions_taken.append({"action": "DRY_RUN_CANCEL_BUY", "inst_id": inst_id, "ord_id": ord_id, "drift_bps": round(drift_bps, 1)})
                        else:
                            res_c = client.cancel_order(inst_id, ord_id)
                            if _cancel_ok(res_c):
                                has_buy_order = False
                                actions_taken.append({"action": "CANCEL_STALE_OR_CAPPED_BUY", "inst_id": inst_id, "ord_id": ord_id, "drift_bps": round(drift_bps, 1)})

                elif ord_side == "sell":
                    has_sell_order = True
                    active_state = "SELL_SUBMITTED"
                    active_ord_id = ord_id
                    active_ord_px = ord_px
                    active_ord_sz = ord_sz
                    # Stage 3 Final Cashout Settlement Override: if we are in the final 6h before expiry and a legacy/tranche SELL is parked > 15 bps above Best Ask,
                    # re-peg it immediately to Best Ask (`Post-Only Maker`) so 100% of inventory converts to USDC before deadline!
                    if lifecycle["final_settlement"] and ord_px > round(asks[0][0], dec_px) * 1.0015:
                        if not dry_run:
                            res_cs3 = client.cancel_order(inst_id, ord_id)
                            if _cancel_ok(res_cs3):
                                has_sell_order = False
                                avail_token_qty = cash_token_qty
                                actions_taken.append({
                                    "action": "CASHOUT_STAGE_3_REPEG_TO_BEST_ASK",
                                    "inst_id": inst_id,
                                    "old_px": ord_px,
                                    "new_best_ask_px": round(asks[0][0], dec_px),
                                })
                        else:
                            has_sell_order = False
                            avail_token_qty = cash_token_qty
                        continue

                    # Handle independent Fresh Tranche Quick-Scalp TP orders (Dynamic Profit-Lock + Time-Decay Fast-Exit Ratchet!)
                    if ord_id in active_tranche_ord_ids:
                        for tr_id, tr_buy_px, tr_buy_sz, tr_oid, tr_tp_px, tr_st, tr_age_h in active_tranches_by_inst.get(inst_id, []):
                            if tr_oid == ord_id and tr_buy_px > 0:
                                tr_unr_bps = ((sig.mid_price - tr_buy_px) / tr_buy_px) * 10000.0
                                # Fee-Aware Fast-Exit Floor: +24 bps gross = +4 bps guaranteed net profit after 10 bps BUY + 10 bps SELL OKX Maker fees!
                                fast_exit_px = max(_ceil_px(tr_buy_px * 1.0024, dec_px), round(asks[0][0], dec_px))
                                # TRE OS v12.0 — User-Calibrated Kronos + AI Cognitive Risk Engine (Default Hard Cap: -400 bps = -4.00%):
                                cfg_max_loss_bps = -abs(float(user_run_cfg.get("max_loss_cap_bps") or -400.0))
                                is_hard_4pct_stop = bool(tr_unr_bps <= cfg_max_loss_bps and tr_age_h <= 10.0)
                                is_cognitive_early_stop = bool(
                                    -400.0 < tr_unr_bps <= -180.0
                                    and tr_age_h <= 10.0
                                    and k_macro_2h_bps <= -25.0
                                    and (k_6h_bps <= -25.0 or k_swing_12h_bps <= -30.0 or k_24h_bps <= -40.0)
                                    and k_ret_bps <= -10.0
                                    and llm_bias <= -0.25
                                    and sig.ofi_norm < -0.10
                                )
                                if is_hard_4pct_stop or is_cognitive_early_stop:
                                    sl_ask_px = round(asks[0][0], dec_px)
                                    if abs(ord_px - sl_ask_px) / max(sl_ask_px, 1e-9) * 10000.0 > 4.0:
                                        if not dry_run:
                                            res_c = client.cancel_order(inst_id, ord_id)
                                            if not _cancel_ok(res_c):
                                                continue
                                        repeg_sz = math.floor(min(cash_token_qty, tr_buy_sz * 0.999) * (10 ** dec_sz)) / (10 ** dec_sz)
                                        res_sl = {"data": []} if dry_run else client.place_spot_order(inst_id, "sell", repeg_sz, sl_ask_px, "PASSIVE_MAKER")
                                        new_sl_id = ""
                                        if isinstance(res_sl.get("data"), list) and res_sl["data"]:
                                            new_sl_id = str(res_sl["data"][0].get("ordId", ""))
                                        if new_sl_id:
                                            active_tranche_ord_ids.add(new_sl_id)
                                            conn.execute(
                                                "UPDATE fresh_scalp_tranches SET tp_ord_id = ?, tp_px = ? WHERE trade_id = ?",
                                                (new_sl_id, sl_ask_px, tr_id),
                                            )
                                            conn.commit()
                                            actions_taken.append({
                                                "action": "HARD_STOP_MAX_4PCT_CAP" if is_hard_4pct_stop else "COGNITIVE_KRONOS_OPENROUTER_EARLY_STOP",
                                                "inst_id": inst_id,
                                                "tranche_unr_bps": round(tr_unr_bps, 1),
                                                "old_px": ord_px,
                                                "sl_maker_px": sl_ask_px,
                                            })
                                    continue

                                # Otherwise, if a tranche TP order was ever placed below the 24 bps Fee-Safe Floor, lift it back to +24 bps!
                                if ord_px < tr_buy_px * 1.0023:
                                    if not dry_run:
                                        res_c = client.cancel_order(inst_id, ord_id)
                                        if not _cancel_ok(res_c):
                                            continue
                                    profit_lock_repegs += 1
                                    repeg_sz = math.floor(min(cash_token_qty, tr_buy_sz * 0.999) * (10 ** dec_sz)) / (10 ** dec_sz)
                                    res_rp = {"data": []} if dry_run else client.place_spot_order(inst_id, "sell", repeg_sz, fast_exit_px, "PASSIVE_MAKER")
                                    new_rp_id = ""
                                    if isinstance(res_rp.get("data"), list) and res_rp["data"]:
                                        new_rp_id = str(res_rp["data"][0].get("ordId", ""))
                                    if new_rp_id:
                                        active_tranche_ord_ids.add(new_rp_id)
                                        conn.execute(
                                            "UPDATE fresh_scalp_tranches SET tp_ord_id = ?, tp_px = ? WHERE trade_id = ?",
                                            (new_rp_id, fast_exit_px, tr_id),
                                        )
                                        conn.commit()
                                        actions_taken.append({
                                            "action": "FEE_SAFE_FLOOR_LIFT_24BPS",
                                            "inst_id": inst_id,
                                            "old_px": ord_px,
                                            "new_px": fast_exit_px,
                                        })
                                    continue

                                eff_lock_trigger = float(user_run_cfg.get("fast_shield_trigger_bps") or 38.0)
                                fast_decay_hours = 2.0 if is_purified_mode else 2.5
                                # Mechanism 3 (12h Daily Profit Stop-Stagnation Sweeper): ONLY if today's realized profits (ratchet_pool_usd)
                                # genuinely cover 100% of the spread to best_ask (never out of pocket!), exit at best_ask:
                                est_tr_loss_usd = max(0.0, (tr_buy_px - (sig.mid_price * 0.999)) * tr_buy_sz)
                                if is_purified_mode and tr_age_h >= 12.0 and ratchet_pool_usd >= 0.15 and est_tr_loss_usd <= ratchet_pool_usd * 0.85:
                                    fast_exit_px = round(asks[0][0], dec_px)
                                if tr_age_h >= fast_decay_hours and ord_px > fast_exit_px * 1.0006 and not is_upside_runner:
                                    if not dry_run:
                                        res_c = client.cancel_order(inst_id, ord_id)
                                        if not _cancel_ok(res_c):
                                            continue
                                    profit_lock_repegs += 1
                                    repeg_sz = math.floor(min(cash_token_qty, tr_buy_sz * 0.999) * (10 ** dec_sz)) / (10 ** dec_sz)
                                    res_rp = {"data": []} if dry_run else client.place_spot_order(inst_id, "sell", repeg_sz, fast_exit_px, "PASSIVE_MAKER")
                                    new_rp_id = ""
                                    if isinstance(res_rp.get("data"), list) and res_rp["data"]:
                                        new_rp_id = str(res_rp["data"][0].get("ordId", ""))
                                    if new_rp_id:
                                        active_tranche_ord_ids.add(new_rp_id)
                                        conn.execute(
                                            "UPDATE fresh_scalp_tranches SET tp_ord_id = ?, tp_px = ? WHERE trade_id = ?",
                                            (new_rp_id, fast_exit_px, tr_id),
                                        )
                                        conn.commit()
                                        actions_taken.append({
                                            "action": "TIME_DECAY_FAST_UNLOCK_REPEG",
                                            "inst_id": inst_id,
                                            "age_hours": round(tr_age_h, 1),
                                            "old_px": ord_px,
                                            "new_px": fast_exit_px,
                                        })
                                elif tr_unr_bps >= eff_lock_trigger and drift_bps > 5.0 and (pred.predicted_return_bps < 4.0 or sig.ofi_norm < -0.15):
                                    if not dry_run:
                                        res_c = client.cancel_order(inst_id, ord_id)
                                        if not _cancel_ok(res_c):
                                            continue
                                    profit_lock_repegs += 1
                                    # Stadio 1 (+38 bps Fast Shield -> locks >= +26 bps gross / +6 bps net) + Stadio 2 (Elastic 76%-88% Trailing Micro-Runner):
                                    lock_frac = 0.88 if sig.ofi_norm < -0.10 else (0.76 if sig.ofi_norm >= 0.30 else 0.82)
                                    trail_mult = max(1.0026, 1.0 + (tr_unr_bps * lock_frac) / 10000.0)
                                    repeg_px = max(_ceil_px(tr_buy_px * trail_mult, dec_px), round(asks[0][0], dec_px))
                                    repeg_sz = math.floor(min(cash_token_qty, tr_buy_sz * 0.999) * (10 ** dec_sz)) / (10 ** dec_sz)
                                    res_rp = {"data": []} if dry_run else client.place_spot_order(inst_id, "sell", repeg_sz, repeg_px, "PASSIVE_MAKER")
                                    new_rp_id = ""
                                    if isinstance(res_rp.get("data"), list) and res_rp["data"]:
                                        new_rp_id = str(res_rp["data"][0].get("ordId", ""))
                                    if new_rp_id:
                                        active_tranche_ord_ids.add(new_rp_id)
                                        conn.execute(
                                            "UPDATE fresh_scalp_tranches SET tp_ord_id = ?, tp_px = ? WHERE trade_id = ?",
                                            (new_rp_id, repeg_px, tr_id),
                                        )
                                        conn.commit()
                                        actions_taken.append({
                                            "action": "FRESH_TRANCHE_PROFIT_LOCK_REPEG",
                                            "inst_id": inst_id,
                                            "tranche_unr_bps": round(tr_unr_bps, 1),
                                            "old_px": ord_px,
                                            "new_px": repeg_px,
                                        })
                        continue
                    # AUDIT SAFEGUARD 1: Never allow a legacy SELL order below openAvgPx * 1.0022 (Cost-Basis Floor Rescue!)
                    tranche_locked_sz = sum(
                        float(o.get("sz") or 0.0)
                        for o in inst_orders
                        if str(o.get("side") or "").lower() == "sell" and str(o.get("ordId") or "") in active_tranche_ord_ids
                    ) + sum(
                        float(tr[2] or 0.0)
                        for tr in active_tranches_by_inst.get(inst_id, [])
                        if tr[5] == "PENDING_TP"
                    )
                    legacy_free_qty = max(0.0, cash_token_qty - tranche_locked_sz)
                    if cost_floor_px > 0 and ord_px < cost_floor_px:
                        if not dry_run:
                            res_c = client.cancel_order(inst_id, ord_id)
                            if not _cancel_ok(res_c):
                                continue
                        has_sell_order = False
                        avail_token_qty = legacy_free_qty
                        cost_basis_fixes += 1
                        actions_taken.append({
                            "action": "RESCUE_BELOW_COST_SELL",
                            "inst_id": inst_id,
                            "old_px": ord_px,
                            "new_floor_px": cost_floor_px,
                        })
                    # AUDIT SAFEGUARD 2: 100% Inventory Coverage Consolidation (absorb idle 20% Moonbag availBal into protected SELL order!)
                    elif avail_token_qty * sig.mid_price >= 3.50 and not active_tranches_by_inst.get(inst_id):
                        if not dry_run:
                            res_c = client.cancel_order(inst_id, ord_id)
                            if not _cancel_ok(res_c):
                                continue
                        has_sell_order = False
                        avail_token_qty = legacy_free_qty
                        actions_taken.append({
                            "action": "CONSOLIDATE_IDLE_MOONBAG_INTO_SELL",
                            "inst_id": inst_id,
                            "added_avail_usd": round(avail_token_qty * sig.mid_price, 2),
                        })
                    # AUDIT SAFEGUARD 3: Dynamic Profit-Lock, Ratchet & Cost-Basis Refresh Re-Pegging
                    # Whenever Quick-Scalps lower a token's openAvgPx (e.g. SUI $1.0219 -> $0.9935, LINK $12.738 -> $12.270),
                    # automatically pull down the legacy SELL order to the new lower `cost_floor_px` (`openAvgPx * 1.0022`)!
                    elif (
                        (unrealized_bps >= 180.0 and drift_bps > 8.0)
                        or (unrealized_bps >= 85.0 and drift_bps > 12.0 and pred.predicted_return_bps < 6.0)
                        or (cost_floor_px > 0 and ord_px > cost_floor_px * 1.0005 and -1500.0 <= unrealized_bps < 0.0)
                    ):
                        if not dry_run:
                            res_c = client.cancel_order(inst_id, ord_id)
                            if not _cancel_ok(res_c):
                                continue
                        has_sell_order = False
                        # Reserve any PENDING_TP tranche qty so step 2B places the Quick-Scalp TP first!
                        avail_token_qty = cash_token_qty - sum(
                            float(o.get("sz") or 0.0)
                            for o in inst_orders
                            if str(o.get("side") or "").lower() == "sell" and str(o.get("ordId") or "") in active_tranche_ord_ids
                        )
                        profit_lock_repegs += 1
                        actions_taken.append({
                            "action": "PROFIT_LOCK_OR_RATCHET_REPEG",
                            "inst_id": inst_id,
                            "unrealized_bps": round(unrealized_bps, 1),
                            "old_px": ord_px,
                            "new_floor_px": cost_floor_px,
                        })
            except Exception:
                pass

        # 2B. Independent Fresh Tranche Quick-Scalp TP Placement + Auto-Dust Sweeper!
        # Sweeps any fractional base-currency fee dust (< $3.50) into the newly placed Quick-Scalp TP order so zero dust is stranded!
        for tr_id, tr_buy_px, tr_buy_sz, tr_oid, tr_tp_px, tr_st, tr_age_h in active_tranches_by_inst.get(inst_id, []):
            if tr_st == "PENDING_TP" and avail_token_qty > 0:
                extra_dust_qty = avail_token_qty - tr_buy_sz
                if 0.0 < extra_dust_qty * sig.mid_price <= 3.50:
                    target_tr_qty = avail_token_qty
                else:
                    target_tr_qty = min(avail_token_qty, tr_buy_sz * 0.999)
                scalp_sz = math.floor(target_tr_qty * (10 ** dec_sz)) / (10 ** dec_sz)
                # TRE OS v11.2 — Kronos Eq.12/13 Calibrated Micro-Profit (+42 bps to +115 bps gross = +22 to +95 bps net):
                # Achievable high-velocity altcoin targets guided by Kronos upside_high_bps & pred_volatility_1h_bps,
                # paired with +38 bps Fast Shield and -4.00% Hard Max-Loss Cap!
                max_tp_cap = 125.0 if is_upside_runner else 85.0
                vol_adj_tp = max(pred.recommended_sell_tp_bps, min(85.0, k_vol_1h_bps * 0.90, k_up_bps * 0.85))
                base_rec_tp = vol_adj_tp * session_tp_mult * (1.25 if is_upside_runner else 1.0)
                quick_tp_bps = 24.0 if tr_age_h >= 2.0 else max(42.0, min(max_tp_cap, base_rec_tp))
                quick_tp_px = round(asks[0][0], dec_px) if lifecycle["final_settlement"] else max(
                    _ceil_px(tr_buy_px * (1.0 + quick_tp_bps / 10000.0), dec_px),
                    round(asks[0][0], dec_px),
                )
                # Use target order notional (`scalp_sz * quick_tp_px >= 4.50`) so price dips never block a valid $5.00 TP order!
                if scalp_sz * quick_tp_px >= 4.50:
                    res_qtp = {"data": []} if dry_run else client.place_spot_order(
                        inst_id=inst_id,
                        side="sell",
                        sz=scalp_sz,
                        px=quick_tp_px,
                        execution_style="PASSIVE_MAKER",
                    )
                    qtp_ord_id = ""
                    if isinstance(res_qtp.get("data"), list) and res_qtp["data"]:
                        qtp_ord_id = str(res_qtp["data"][0].get("ordId", ""))
                    if qtp_ord_id:
                        avail_token_qty = max(0.0, avail_token_qty - scalp_sz)
                        active_tranche_ord_ids.add(qtp_ord_id)
                        conn.execute(
                            "UPDATE fresh_scalp_tranches SET tp_ord_id = ?, tp_px = ?, status = 'TP_PLACED' WHERE trade_id = ?",
                            (qtp_ord_id, quick_tp_px, tr_id),
                        )
                        conn.commit()
                        actions_taken.append({
                            "inst_id": inst_id,
                            "side": "sell",
                            "style": "FRESH_TRANCHE_QUICK_SCALP_TP",
                            "sz": scalp_sz,
                            "buy_px": tr_buy_px,
                            "px": quick_tp_px,
                            "ord_id": qtp_ord_id,
                        })

        # Check if there is a legacy SELL order (distinct from Quick-Scalp tranche orders)
        has_legacy_sell_order = any(
            str(o.get("side") or "").lower() == "sell" and str(o.get("ordId") or "") not in active_tranche_ord_ids
            for o in inst_orders
        ) and has_sell_order

        # 3A. Place Take-Profit SELL orders enforcing Cost-Basis Floor (with Bull-Wave Legacy Runner, Cannibal Ratchet & Final Cashout Settlement!)
        if not has_legacy_sell_order and avail_token_qty * sig.mid_price >= 5.0:
            sell_sz = math.floor(avail_token_qty * (10 ** dec_sz)) / (10 ** dec_sz)
            if lifecycle["final_settlement"]:
                # Stage 3 Final Cashout Settlement (<= 6h to Run Expiry): convert 100% of remaining inventory into USDC via Post-Only Maker at Best Ask!
                target_sell_px = round(asks[0][0], dec_px)
                tp_style_tag = "CASHOUT_STAGE_3_BEST_ASK_MAKER"
            elif (
                ratchet_pool_usd >= 0.45
                and unrealized_bps <= -1500.0
                and sell_sz * sig.mid_price >= 11.0
            ):
                # Cannibal Ratchet Anti-Bubble Shield: when a legacy position is deeply underwater (<= -15%) AND we have positive
                # realized Quick-Scalp profits in the Ratchet Pool (>= $0.45), carve out a $5.20 micro-slice and sell it at a
                # profit-subsidized floor so total realized PnL never goes negative while freeing $5.20 of live USDC ammunition!
                cannibal_slice_usd = 5.20
                cannibal_sz = math.floor((cannibal_slice_usd / sig.mid_price) * (10 ** dec_sz)) / (10 ** dec_sz)
                if cannibal_sz * sig.mid_price >= 5.01:
                    sell_sz = cannibal_sz
                    max_subsidy_px_drop = (ratchet_pool_usd * 0.85) / cannibal_sz
                    subsidized_floor = max(asks[0][0], (open_avg_px * 1.0021) - max_subsidy_px_drop)
                    target_sell_px = round(subsidized_floor, dec_px)
                    tp_style_tag = "CANNIBAL_RATCHET_SLICE_UNLOCK"
                else:
                    target_sell_px = round(max(cost_floor_px, asks[0][0]), dec_px)
                    tp_style_tag = "PASSIVE_MAKER_TP"
            else:
                if lifecycle["reduce_only"] or is_macro_overweight_deconcentrate or is_macro_liquidity_unlock:
                    raw_tp_px = cost_floor_px
                    tp_style_tag = (
                        "MACRO_OVERWEIGHT_DECONCENTRATE"
                        if is_macro_overweight_deconcentrate
                        else ("MACRO_LIQUIDITY_REBALANCE_UNLOCK" if is_macro_liquidity_unlock else "CASHOUT_STAGE_2_REDUCE_ONLY_TP")
                    )
                elif unrealized_bps >= 180.0 and (pred.predicted_return_bps < 4.0 or sig.ofi_norm < 0.0):
                    raw_tp_px = asks[0][0]
                    tp_style_tag = "PROFIT_LOCK_ASK_JOIN"
                elif unrealized_bps >= 85.0 and pred.predicted_return_bps < 6.0:
                    raw_tp_px = sig.mid_price * 1.0005
                    tp_style_tag = "PROFIT_LOCK_TP"
                else:
                    raw_tp_px = sig.mid_price * (1.0 + pred.recommended_sell_tp_bps / 10000.0)
                    tp_style_tag = "PASSIVE_MAKER_TP"

                # Bull-Wave Legacy Runner: if price is recovering near breakeven (> -120 bps) AND 3-horizon Kronos + OFI signal a strong rally,
                # expand the legacy target above openAvgPx by +45..+85 bps instead of selling flat at +22 bps!
                effective_floor_px = cost_floor_px
                if is_upside_runner and not lifecycle["reduce_only"] and unrealized_bps >= -120.0 and open_avg_px > 0:
                    runner_tp_bps = max(45.0, min(95.0, pred.recommended_sell_tp_bps * 1.25))
                    effective_floor_px = max(cost_floor_px, _ceil_px(open_avg_px * (1.0 + runner_tp_bps / 10000.0), dec_px))
                    tp_style_tag = "BULL_WAVE_LEGACY_RUNNER_TP"

                target_sell_px = max(_ceil_px(raw_tp_px, dec_px), effective_floor_px, round(asks[0][0], dec_px))
            if sell_sz > 0 and target_sell_px > 0:
                res_sell = {"data": []} if dry_run else client.place_spot_order(
                    inst_id=inst_id,
                    side="sell",
                    sz=sell_sz,
                    px=target_sell_px,
                    execution_style="PASSIVE_MAKER",
                )
                ord_id_sell = ""
                if isinstance(res_sell.get("data"), list) and res_sell["data"]:
                    ord_id_sell = str(res_sell["data"][0].get("ordId", ""))
                if ord_id_sell:
                    active_state = "SELL_SUBMITTED"
                    active_ord_id = ord_id_sell
                    active_ord_px = target_sell_px
                    active_ord_sz = sell_sz
                actions_taken.append({
                    "inst_id": inst_id,
                    "side": "sell",
                    "style": tp_style_tag,
                    "sz": sell_sz,
                    "px": target_sell_px,
                    "cost_floor_px": cost_floor_px,
                    "pred_bps": pred.predicted_return_bps,
                    "regime": pred.regime,
                    "ord_id": ord_id_sell,
                })

        # 3B. Collect candidate for Opportunity-Ranked Cash Sweeper (evaluated after scanning all 12 pairs!)
        # Skip `harvest_only` pairs (SEI, FET), enforce Dynamic % NAV Anti-Stacking Cap & Re-Entry Pullback Guard (45m / -25 bps)!
        max_vpin_allowed = 0.55 if golden_harvest_mode else 0.99
        cooldown_info = recent_sell_cooldown_map.get(inst_id)
        reentry_blocked = False
        if cooldown_info:
            last_s_px, _ = cooldown_info
            # Require at least -25 bps pullback below the recent SELL price within 45 minutes
            if last_s_px > 0 and sig.mid_price > last_s_px * 0.9975:
                reentry_blocked = True

        # Deep-Dip Sniper Reserve: allow deployment when Rebound Catcher, positive Kronos 1h (>= +5 bps), OppScore >= 0, or >= 25 bps discount from 2h high!
        last_bullet_ready = True
        if free_usdc <= 10.50 and not (is_rebound_leader or k_ret_bps >= 5.0 or calc_opp_score >= 0.0 or drop_from_high_bps >= 25.0):
            last_bullet_ready = False

        # Cashout Lifecycle Gate:
        # - In Stage 2 (`reduce_only=True`) or Stage 3 (`final_settlement=True`), block ALL new BUY orders (100% USDC preservation)!
        # - In Stage 1 (`CASHOUT_STAGE_1_VAULT_50`), allow new BUY orders ONLY on confirmed V-Rebounds (`is_rebound_leader`) or strong Kronos alignment!
        cashout_buy_allowed = True
        if lifecycle["reduce_only"] or lifecycle["final_settlement"]:
            cashout_buy_allowed = False
        elif lifecycle["stage"] == "CASHOUT_STAGE_1_VAULT_50" and not (is_rebound_leader or (k_aligned and k_ret_bps >= 15.0)):
            cashout_buy_allowed = False

        # TRE OS v11.2 — Kronos 3-Horizon + OpenRouter Cognitive Entry Gate:
        # 1) Pullback >= -32 bps from 2h high (or V-Rebound);
        # 2) Kronos 1h >= +8.0 bps, TP probability >= 0.58, AND Kronos 2h Macro NOT crashing (>= -12.0 bps);
        # 3) OpenRouter Chief Quant Judge Veto: llm_bias >= -0.05 (blocks entry if OpenRouter flags negative conviction);
        # 4) Positive L2 Order Flow Imbalance (OFI >= +0.18) and non-toxic VPIN (<= 0.65).
        # 5-Horizon Crash Shield: block new BUY entries if 6h (<-22 bps), 12h (<-35 bps), or 24h (<-50 bps) forecast a structural dump!
        has_5h_perspective_safety = bool(
            k_macro_2h_bps >= -12.0
            and k_6h_bps >= -22.0
            and k_swing_12h_bps >= -35.0
            and k_24h_bps >= -50.0
        )
        has_positive_edge = bool(
            (drop_from_high_bps >= 32.0 or is_rebound_leader)
            and k_ret_bps >= 8.0
            and has_5h_perspective_safety
            and k_tp_prob >= 0.58
            and pred.predicted_return_bps >= 3.5
            and llm_bias >= -0.05
            and sig.ofi_norm >= 0.18
            and sig.vpin_toxicity <= 0.65
        )
        # Universal Macro Concentration Cap (Pillar 2): no single coin may exceed `universal_max_inv_weight` (12.5% when Working Capital < 35%, 15.0% otherwise)!
        eff_max_inv_weight = universal_max_inv_weight
        max_headroom_usd = max(0.0, (eff_max_inv_weight - inv_weight) * nav_usdc)

        if (
            not harvest_only
            and not has_buy_order
            and not reentry_blocked
            and not is_bubble_top
            and cashout_buy_allowed
            and last_bullet_ready
            and has_positive_edge
            and inv_weight < eff_max_inv_weight
            and max_headroom_usd >= 5.01
            and active_qs_usd < 1.0  # Strict 1-Tranche-Per-Coin Rule: never stack a 2nd Quick-Scalp on a coin that already has an open tranche!
            and btc_lead_lag_bps > -14.0
            and sig.vpin_toxicity <= max_vpin_allowed
        ):
            opp_score = calc_opp_score
            buy_candidates.append({
                "inst_id": inst_id,
                "opp_score": round(opp_score, 3),
                "mid_price": sig.mid_price,
                "best_bid": bids[0][0],
                "best_ask": asks[0][0],
                "dec_px": dec_px,
                "dec_sz": dec_sz,
                "llm_bias": llm_bias,
                "pred_bps": pred.predicted_return_bps,
                "buy_offset_bps": eff_buy_offset_bps,
                "regime": "REBOUND_CATCHER" if is_rebound_leader else pred.regime,
                "has_sell_order": has_sell_order,
                "max_headroom_usd": round(max_headroom_usd, 2),
            })

        scalp_run_updates.append((inst_id, active_state, active_ord_sz, active_ord_px, active_ord_id, now_iso))
        # Update active buy/sell order prices in row_dict for the Institutional Dashboard
        buy_ords = [float(o.get("px") or 0) for o in inst_orders if str(o.get("side") or "").lower() == "buy" and float(o.get("px") or 0) > 0]
        sell_ords = [float(o.get("px") or 0) for o in inst_orders if str(o.get("side") or "").lower() == "sell" and float(o.get("px") or 0) > 0]
        if buy_ords:
            row_dict["active_buy_px"] = max(buy_ords)
        if sell_ords:
            row_dict["active_sell_px"] = min(sell_ords)
        elif active_state == "SELL_SUBMITTED" and active_ord_px > 0:
            row_dict["active_sell_px"] = active_ord_px

    # 3C. Opportunity-Ranked Cash Sweeper + Two-Chamber Purified Architecture (Camera 1: 63% Assault Sniper + Camera 2: 37% Depth-Bomb Shield):
    # - During Modo 3 Transition (is_purified_mode=False), cap active parallel Quick-Scalp at $95.00 USDC and lock all freed legacy cash in Vault.
    # - In Full Purified Mode (is_purified_mode=True, starting from X USDC), Camera 1 deploys up to 63% of NAV in Heavy Sniper Bullets (~$30 each),
    #   while Camera 2 keeps 37% of NAV in 100% pure USDC Cash Shield (deployable ONLY on deep flash-crashes <= -180 bps)!
    has_deep_flash_crash = any(float(t.get("unrealized_bps") or 0.0) <= -180.0 and float(t.get("ofi_norm") or 0.0) >= 0.20 for t in telemetry_rows)
    c1_pct_cfg = float(user_run_cfg.get("chamber1_assault_pct") or 0.63)
    if is_purified_mode:
        chamber1_cap_usd = round(nav_usdc * (min(0.90, c1_pct_cfg + 0.22) if has_deep_flash_crash else c1_pct_cfg), 2)
        parallel_scalp_cap_usd = max(0.0, chamber1_cap_usd - fresh_qs_under_6h_usd)
    else:
        parallel_scalp_cap_usd = max(0.0, 95.0 - fresh_qs_under_6h_usd)
    deployable_usdc = round(min(free_usdc * (1.0 - float(lifecycle["vault_lock_ratio"])), parallel_scalp_cap_usd), 2)
    macro_equilibrium_summary["purified_two_chamber_mode"] = is_purified_mode
    macro_equilibrium_summary["chamber1_assault_cap_usd"] = round(nav_usdc * 0.63, 2)
    macro_equilibrium_summary["chamber2_shield_vault_usd"] = round(nav_usdc * 0.37, 2)

    # Check if Modo 3 24h Legacy Unwind Goal is reached (all 5 legacy blocks SUI, NEAR, AVAX, FET, SEI < $5.00 or free_usdc >= $165.00)
    legacy_5_remaining_usd = round(
        sum(
            float(t.get("holding_eq_usd") or 0.0)
            for t in telemetry_rows
            if t.get("inst_id") in ("SUI-USDC", "NEAR-USDC", "AVAX-USDC", "FET-USDC", "SEI-USDC", "RENDER-USDC")
        ),
        2,
    )
    macro_equilibrium_summary["modo3_legacy_5_remaining_usd"] = legacy_5_remaining_usd
    macro_equilibrium_summary["modo3_deadline_iso"] = MODO3_24H_DEADLINE_ISO
    notify_flag_path = os.path.join(BASE_DIR, "config", "purified_run_ready_notified.json")
    if legacy_5_remaining_usd <= 5.0 and not os.path.exists(notify_flag_path) and not dry_run:
        try:
            import urllib.parse
            import urllib.request
            tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
            tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "6554816075").strip()
            if tg_token and tg_chat:
                msg = (
                    f"🚨🎯 *OBIETTIVO LIQUIDITÀ MODO 3 RAGGIUNTO!*\n\n"
                    f"Tutti i 5 vecchi blocchi storici (SUI, NEAR, AVAX, FET, SEI) sono stati smobilizzati in USDC!\n"
                    f"• *NAV Purificato Totale:* ${nav_usdc:.2f} USDC\n"
                    f"• *Cassa Liquida Pronta:* ${free_usdc:.2f} USDC\n"
                    f"• *Residuo Vecchi Blocchi:* ${legacy_5_remaining_usd:.2f} USDC\n\n"
                    f"Il sistema è pronto al tuo comando per inaugurare insieme la *Nuova Run Purificata da Zero*!"
                )
                tg_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
                data_bytes = urllib.parse.urlencode({"chat_id": tg_chat, "text": msg, "parse_mode": "Markdown"}).encode("utf-8")
                urllib.request.urlopen(urllib.request.Request(tg_url, data=data_bytes), timeout=8)
            with open(notify_flag_path, "w", encoding="utf-8") as nf:
                json.dump({"notified_at": now_iso, "nav_usdc": nav_usdc, "free_usdc": free_usdc}, nf)
        except Exception as e_tg:
            print(f"[!] Modo 3 Telegram alert note: {e_tg}")
    if deployable_usdc >= 5.01 and buy_candidates and not lifecycle["reduce_only"]:
        buy_candidates.sort(key=lambda x: x["opp_score"], reverse=True)
        for cand in buy_candidates:
            if deployable_usdc < 5.01:
                break
            c_inst = cand["inst_id"]
            c_dec_px = cand["dec_px"]
            c_dec_sz = cand["dec_sz"]
            base_lot_usd = max(22.0, (spot_equity_usd * 0.85) / 10.0)
            conv_boost = 1.0 + max(-0.25, min(0.45, cand["llm_bias"] * 0.4))
            alpha_boost = 1.0 + max(-0.15, min(0.15, cand["pred_bps"] / 100.0))
            # Pillar 3 Heavy Bullet Sizing ($22.00 - $24.50 USDC): eliminate micro-splits under $42 so each Quick-Scalp fires a full heavy bullet!
            slot_cap_usd = (
                min(macro_bullet_cap_usd, round(deployable_usdc * 0.50, 2))
                if (42.0 <= deployable_usdc <= 52.0 and len(buy_candidates) >= 2)
                else min(dynamic_qs_cap_usd, macro_bullet_cap_usd)
            )
            headroom_cap_usd = float(cand.get("max_headroom_usd", slot_cap_usd))
            lot_usd = min(
                deployable_usdc * 0.998,
                slot_cap_usd,
                headroom_cap_usd,
                max(5.01, round(base_lot_usd * agg_mult * conv_boost * alpha_boost, 2)),
            )

            target_buy_px = round(cand["mid_price"] * (1.0 - cand["buy_offset_bps"] / 10000.0), c_dec_px)
            if target_buy_px >= cand["best_ask"]:
                target_buy_px = round(cand["best_bid"], c_dec_px)

            buy_sz = math.floor((lot_usd / target_buy_px) * (10 ** c_dec_sz)) / (10 ** c_dec_sz) if target_buy_px > 0 else 0.0
            if buy_sz * target_buy_px < 5.0:
                continue

            res_place = {"data": []} if dry_run else client.place_spot_order(
                inst_id=c_inst,
                side="buy",
                sz=buy_sz,
                px=target_buy_px,
                execution_style="PASSIVE_MAKER",
            )
            mode_str = "DEMO_LIVE" if (client.is_authenticated and client.simulated_demo) else (
                "PROD_LIVE" if client.is_authenticated else "DRY_RUN_SIM"
            )
            ord_id_placed = ""
            if isinstance(res_place.get("data"), list) and res_place["data"]:
                ord_id_placed = str(res_place["data"][0].get("ordId", ""))

            if ord_id_placed:
                free_usdc = max(0.0, free_usdc - (buy_sz * target_buy_px))
                deployable_usdc = max(0.0, deployable_usdc - (buy_sz * target_buy_px))
                order_tuples.append(
                    (
                        now_iso,
                        c_inst,
                        "buy",
                        "PASSIVE_MAKER",
                        buy_sz,
                        target_buy_px,
                        cand["pred_bps"],
                        cand["regime"],
                        ord_id_placed,
                        mode_str,
                    )
                )
                actions_taken.append(
                    {
                        "inst_id": c_inst,
                        "side": "buy",
                        "style": "RANKED_ALPHA_BUY_TRAP",
                        "opp_score": cand["opp_score"],
                        "sz": buy_sz,
                        "px": target_buy_px,
                        "pred_bps": cand["pred_bps"],
                        "regime": cand["regime"],
                        "ord_id": ord_id_placed,
                    }
                )

    # Commit all telemetry, order rows, and dashboard `scalp_runs` state in one atomic transaction
    try:
        if telemetry_tuples:
            conn.executemany(
                """
                INSERT INTO microstructure_telemetry (
                    timestamp, inst_id, mid_price, micro_price, spread_bps,
                    obi_top5, ofi_norm, vpin_toxicity, hawkes_net_burst, composite_alpha,
                    predicted_return_bps, kalman_velocity_bps, confidence, regime
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                telemetry_tuples,
            )
        if order_tuples:
            conn.executemany(
                """
                INSERT INTO predator_orders (
                    timestamp, inst_id, side, execution_style, size, price,
                    predicted_bps, regime, ord_id, mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                order_tuples,
            )
        if scalp_run_updates:
            conn.executemany(
                """
                INSERT OR REPLACE INTO scalp_runs (inst_id, state, size, price, cl_ord_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                scalp_run_updates,
            )
        # Auto-Prune microstructure_telemetry, predator_audit_history & predator_orders to prevent SQLite disk bloat through Dec 31!
        conn.execute(
            "DELETE FROM microstructure_telemetry WHERE id < (SELECT COALESCE(MAX(id), 0) - 10000 FROM microstructure_telemetry)"
        )
        conn.execute(
            "DELETE FROM predator_audit_history WHERE id < (SELECT COALESCE(MAX(id), 0) - 5000 FROM predator_audit_history)"
        )
        conn.execute(
            "DELETE FROM predator_orders WHERE id < (SELECT COALESCE(MAX(id), 0) - 5000 FROM predator_orders)"
        )
        conn.commit()
    except Exception as e:
        print(f"[!] SQLite commit warning: {e}")

    cycle_latency_ms = int(round((time.perf_counter() - t_cycle_start) * 1000.0))

    pred_engine.save_state()

    debate_res = None
    if run_llm_debate and telemetry_rows:
        debate_res = council.run_council_debate(
            telemetry=telemetry_rows,
            nav_usdc=nav_usdc,
            free_usdc=free_usdc,
            trigger_reason="predator_cycle_synthesis",
        )

    audit_res = None
    if run_audit:
        audit_res = auditor.run_full_audit(
            conn=conn,
            current_nav_usd=nav_usdc,
            holdings_summary=holdings_summary,
            cost_basis_fixes=cost_basis_fixes,
            profit_lock_repegs=profit_lock_repegs,
            query_ai=False,
        )

    result_payload = {
        "timestamp": now_iso,
        "latency_scan_ms": cycle_latency_ms,
        "nav_usdc": round(nav_usdc, 2),
        "spot_equity_usd": round(spot_equity_usd, 2),
        "free_usdc": round(free_usdc, 2),
        "frozen_usdc": round(max(0.0, total_usdc - free_usdc), 2),
        "total_usdc_cash": round(total_usdc, 2),
        "active_orders_count": len(open_orders),
        "btc_mid_px": round(btc_bids[0][0], 2) if btc_bids else 68420.0,
        "ofi_btc": round(btc_sig.ofi_norm, 3) if btc_bids and btc_asks else 0.0,
        "btc_lead_lag_bps": btc_lead_lag_bps,
        "ratchet_pool_usd": ratchet_pool_usd,
        "dynamic_qs_cap_usd": dynamic_qs_cap_usd,
        "macro_equilibrium": macro_equilibrium_summary,
        "run_lifecycle": lifecycle,
        "authenticated": client.is_authenticated,
        "simulated_demo": client.simulated_demo,
        "cost_basis_fixes": cost_basis_fixes,
        "profit_lock_repegs": profit_lock_repegs,
        "telemetry": telemetry_rows,
        "actions": actions_taken,
        "llm_debate": asdict(debate_res) if debate_res else None,
        "audit_report": asdict(audit_res) if audit_res else None,
    }
    try:
        live_snap_path = os.path.join(BASE_DIR, "config", "predator_live_snapshot.json")
        tmp_snap_path = live_snap_path + ".tmp"
        with open(tmp_snap_path, "w", encoding="utf-8") as f:
            json.dump(result_payload, f, indent=2)
        os.replace(tmp_snap_path, live_snap_path)
    except Exception:
        pass
    return result_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="TRE OS v7.0 (Sovereign Predator Edition) — Predictive Microstructure & Local Kronos-mini Quant OS")
    parser.add_argument("--once", action="store_true", help="Run a single predictive scan cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="Pre-live test mode: reads live books/balances/Kronos without placing or cancelling orders")
    parser.add_argument("--debate", action="store_true", help="Run the 3-Agent LLM Adversarial Council debate")
    parser.add_argument("--audit", action="store_true", help="Run the Deterministic + OpenRouter AI Ledger Audit")
    parser.add_argument("--interval", type=float, default=15.0, help="Loop interval in seconds (default: 15s)")
    parser.add_argument("--expiry-iso", type=str, default="", help="Configurable Run Expiration ISO-8601 timestamp (default: 2026-12-31T21:00:00Z, or NONE for perpetual)")
    parser.add_argument("--cashout-days", type=float, default=DEFAULT_CASHOUT_DAYS, help="Days before expiry to begin intelligent 100%% USDC cashout tapering (default: 6.0)")
    parser.add_argument("--init-purified-run", action="store_true", help="Initialize a fresh X-USDC Purified Two-Chamber Run using current live NAV as baseline_nav_usdc")
    parser.add_argument("--demo", action="store_true", help="Enable x-simulated-trading: 1 flag (OKX Demo account)")
    parser.add_argument("--live", action="store_true", help="Force Production Live Spot account (default)")
    args = parser.parse_args()

    load_dotenv(os.path.join(BASE_DIR, ".env"))

    simulated_demo = bool(args.demo)
    if os.environ.get("OKX_SIMULATED_DEMO", "0") == "1" and not args.live:
        simulated_demo = True

    db_path = os.path.join(BASE_DIR, "config", "okx_trader.db")
    client = OKXNativeClient(simulated_demo=simulated_demo)
    micro_engine = MicrostructureEngine(bucket_volume_usd=2500.0)
    pred_engine = PredatorPredictiveEngine(state_path=os.path.join(BASE_DIR, "config", "rls_model_state.json"))
    kronos_client = KronosOracleClient()
    council = AdversarialLLMCouncil(
        directive_out_path=os.path.join(BASE_DIR, "config", "predator_llm_directive.json")
    )
    eff_base_nav, eff_start_iso, eff_start_ms, _ = load_purified_run_config(BASE_DIR)
    if args.init_purified_run and client.is_authenticated:
        bals = client.get_account_balances()
        live_x_usdc = round(sum(float(b.get("eqUsd") or 0.0) for b in bals), 2) if bals else eff_base_nav
        now_dt_init = datetime.datetime.now(datetime.timezone.utc)
        eff_start_iso = now_dt_init.strftime("%Y-%m-%dT%H:%M:%SZ")
        eff_start_ms = int(now_dt_init.timestamp() * 1000)
        eff_base_nav = live_x_usdc
        with open(os.path.join(BASE_DIR, "config", "purified_run_config.json"), "w", encoding="utf-8") as pf:
            json.dump({
                "baseline_nav_usdc": eff_base_nav,
                "run_start_iso": eff_start_iso,
                "run_start_ts_ms": eff_start_ms,
                "purified_two_chamber_mode": True,
            }, pf, indent=2)
        print(f"[TRE OS v10.0 PURIFIED RUN INITIALIZED] Starting Capital X = {eff_base_nav:.2f} USDC at {eff_start_iso}!")

    auditor = PredatorAuditor(
        db_path=db_path,
        report_out_path=os.path.join(BASE_DIR, "config", "predator_audit_report.json"),
        baseline_nav=eff_base_nav,
    )
    conn = init_predator_db(db_path)

    if args.once:
        summary = run_predator_cycle(
            client=client,
            micro_engine=micro_engine,
            pred_engine=pred_engine,
            kronos_client=kronos_client,
            council=council,
            auditor=auditor,
            conn=conn,
            run_llm_debate=args.debate,
            run_audit=args.audit,
            dry_run=args.dry_run,
            expiry_iso=args.expiry_iso,
            cashout_days=args.cashout_days,
        )
        lc = summary.get("run_lifecycle", {})
        print("=== TRE OS v8.3 SOVEREIGN PREDATOR (12-PAIR UNIVERSE + KRONOS PAPER v8.1 + CONFIGURABLE CASHOUT ENGINE) ===")
        print(
            f"Timestamp: {summary['timestamp']} | Mode: {'DRY_RUN_TEST' if args.dry_run else ('DEMO' if summary['simulated_demo'] else 'PRODUCTION_LIVE')} | "
            f"Total NAV: ${summary['nav_usdc']:.2f} USDC | Free Cash: ${summary['free_usdc']:.2f} | "
            f"BTC Lead-Lag: {summary['btc_lead_lag_bps']:+.2f}bps | Lifecycle: {lc.get('stage')} (Exp: {lc.get('expiry_iso')}, {lc.get('days_remaining')}d left)"
        )
        print("-" * 124)
        print(
            f"{'INST_ID':<12} {'MID_PX':<9} {'AVG_COST':<9} {'UNR_BPS':<9} "
            f"{'OFI':<6} {'VPIN':<5} {'KRONOS_1H':<10} {'PRED_BPS':<10} {'REGIME':<21} {'BUY_BPS':<8} {'TP_BPS'}"
        )
        print("-" * 124)
        for t in summary["telemetry"]:
            print(
                f"{t['inst_id']:<12} ${t['mid_price']:<8} ${t['open_avg_px']:<8} {t['unrealized_bps']:>+7.1f}  "
                f"{t['ofi_norm']:>+5.2f} {t['vpin_toxicity']:<5.2f} {t['kronos_1h_bps']:>+7.2f}bps "
                f"{t['predicted_return_bps']:>+7.2f}bps {t['regime']:<21} -{t['buy_offset_bps']:<6.1f} +{t['sell_tp_bps']:.1f}"
            )
        if summary["actions"]:
            print("\n=== SELF-HEALING & EXECUTION ACTIONS TAKEN ===")
            for act in summary["actions"]:
                print(" ", act)
        if summary["audit_report"]:
            ar = summary["audit_report"]
            print("\n=== SCIENTIFIC & ACCOUNTING AUDIT REPORT ===")
            print(
                f"Score: {ar['audit_score_100']}/100 | Auditor: {ar['auditor_model']} | "
                f"Baseline: ${ar['baseline_nav_usd']:.2f} -> Live NAV: ${ar['current_nav_usd']:.2f} "
                f"(+${ar['net_pnl_usd']:.2f} / +{ar['net_pnl_pct']:.2f}%)"
            )
            print(
                f"Ledger Fills: {ar['total_fills_count']} (Buy: {ar['buy_fills_count']}, Sell: {ar['sell_fills_count']}, "
                f"Maker Ratio: {ar['maker_ratio_pct']}%) | Realized PnL: +${ar['realized_pnl_usd']:.4f} USDC | "
                f"Unrealized MTM: ${ar['unrealized_mtm_usd']:+.2f} USDC"
            )
            print(f"Verdict: {ar['executive_verdict']}")
        conn.close()
        return

    print(f"[⚡ TRE OS v6.0 PREDATOR] Starting continuous production loop (interval={args.interval}s)...")
    cycle_num = 0
    try:
        while True:
            cycle_num += 1
            # 120 cycles * 15s = 30m (48 calls/day -> stays strictly within OpenRouter's 50 free-models-per-day quota!)
            do_debate = (cycle_num % 120 == 1) or args.debate
            do_audit = (cycle_num % 40 == 1) or args.audit
            summary = run_predator_cycle(
                client=client,
                micro_engine=micro_engine,
                pred_engine=pred_engine,
                kronos_client=kronos_client,
                council=council,
                auditor=auditor,
                conn=conn,
                run_llm_debate=do_debate,
                run_audit=do_audit,
                dry_run=args.dry_run,
                expiry_iso=args.expiry_iso,
                cashout_days=args.cashout_days,
            )
            print(
                f"[{summary['timestamp']}] Cycle #{cycle_num} | NAV: ${summary['nav_usdc']:.2f} USDC | "
                f"Free: ${summary['free_usdc']:.2f} | Actions: {len(summary['actions'])} | "
                f"Fixes: {summary['cost_basis_fixes']}/{summary['profit_lock_repegs']}"
            )
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[!] Shutting down TRE OS v6.0 Predator cleanly.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
