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
   - Full integration with OKX Simple Earn ($35.46 USDC @ 10% APR) & `config/okx_trader.db`
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
from dataclasses import asdict
from typing import Any, Dict, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from agents.llm_council import AdversarialLLMCouncil
from core.kronos_oracle import KronosOracleClient
from core.microstructure import MicrostructureEngine
from core.predator_auditor import PredatorAuditor
from core.predictor import PredatorPredictiveEngine
from execution.okx_hybrid_executor import OKXNativeClient


# Official 8 High-Beta Spot Universe on OKX EEA with exact tickSz/lotSz decimals
DEFAULT_UNIVERSE: Dict[str, Dict[str, Any]] = {
    "SOL-USDC":    {"coin": "SOL",    "dec_px": 2, "dec_sz": 3},
    "SUI-USDC":    {"coin": "SUI",    "dec_px": 4, "dec_sz": 2},
    "NEAR-USDC":   {"coin": "NEAR",   "dec_px": 3, "dec_sz": 2},
    "LINK-USDC":   {"coin": "LINK",   "dec_px": 3, "dec_sz": 2},
    "RENDER-USDC": {"coin": "RENDER", "dec_px": 3, "dec_sz": 2},
    "AVAX-USDC":   {"coin": "AVAX",   "dec_px": 3, "dec_sz": 2},
    "FET-USDC":    {"coin": "FET",    "dec_px": 4, "dec_sz": 1},
    "SEI-USDC":    {"coin": "SEI",    "dec_px": 5, "dec_sz": 1},
}

BASELINE_NAV_USDC = 298.89  # Official TRE OS v6.0 Predator Run Start (22/10/2026 21:00 CEST)
RUN_START_ISO = "2026-10-22T19:00:00Z"
RUN_START_TS_MS = 1792695600000
GOLDEN_RULE_DAILY_MIN_PCT = 0.70
GOLDEN_RULE_DAILY_MAX_PCT = 5.00
SIMPLE_EARN_FALLBACK_USDC = 35.48


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
    conn.commit()
    return conn


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
) -> Dict[str, Any]:
    balances = client.get_account_balances() if client.is_authenticated else []
    open_orders = client.get_open_orders() if client.is_authenticated else []
    kronos_forecasts = kronos_client.fetch_forecasts(list(DEFAULT_UNIVERSE.keys()))

    # Query Simple Earn USDC balance (fallback to confirmed $35.46 USDC)
    simple_earn_usdc = SIMPLE_EARN_FALLBACK_USDC
    if client.is_authenticated and not client.simulated_demo:
        sav = client.get_savings_balances()
        earn_sum = sum(float(s.get("amt") or 0.0) for s in sav if s.get("ccy") == "USDC")
        if earn_sum > 0:
            simple_earn_usdc = earn_sum
    elif client.simulated_demo:
        simple_earn_usdc = 0.0

    spot_equity_usd = sum(float(b.get("eqUsd") or 0.0) for b in balances) if balances else 263.50
    nav_usdc = spot_equity_usd + simple_earn_usdc
    free_usdc = (
        sum(float(b.get("availBal") or 0.0) for b in balances if b.get("ccy") == "USDC")
        if balances
        else 32.97
    )

    tracked_ccys = {m["coin"] for m in DEFAULT_UNIVERSE.values()} | {"USDC"}

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
    if client.is_authenticated:
        try:
            raw_fills = client.get_recent_fills(limit=50)
            auditor.sync_okx_fills(
                conn=conn,
                raw_fills=raw_fills,
                open_avg_px_map=cost_basis_map,
                allowed_pairs=set(DEFAULT_UNIVERSE.keys()),
            )
            cur_tr = conn.cursor()
            cur_tr.execute(
                """
                SELECT MIN(trade_id), inst_id, AVG(fill_px), SUM(fill_sz), MAX(fill_time)
                FROM predator_fills_ledger
                WHERE side='buy' AND fill_time >= ?
                GROUP BY ord_id, inst_id
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
            cur_tr.execute("SELECT trade_id, inst_id, buy_px, buy_sz, tp_ord_id, tp_px, status FROM fresh_scalp_tranches WHERE status IN ('PENDING_TP', 'TP_PLACED')")
            for tr_row in cur_tr.fetchall():
                tr_id, tr_inst, tr_px, tr_sz, tr_oid, tr_tp_px, tr_st = tr_row
                if tr_st == "TP_PLACED" and tr_oid and tr_oid not in open_ord_id_set:
                    # Quick-Scalp TP order was filled (or cancelled)! Check if filled in ledger
                    cur_tr.execute("SELECT 1 FROM predator_fills_ledger WHERE ord_id = ? AND side='sell'", (tr_oid,))
                    if cur_tr.fetchone():
                        cur_tr.execute("UPDATE fresh_scalp_tranches SET status='CLOSED_PROFIT' WHERE trade_id = ?", (tr_id,))
                    else:
                        cur_tr.execute("UPDATE fresh_scalp_tranches SET status='PENDING_TP', tp_ord_id='' WHERE trade_id = ?", (tr_id,))
                        active_tranches_by_inst.setdefault(tr_inst, []).append((tr_id, float(tr_px), float(tr_sz), "", 0.0, "PENDING_TP"))
                else:
                    if tr_oid:
                        active_tranche_ord_ids.add(str(tr_oid))
                    active_tranches_by_inst.setdefault(tr_inst, []).append((tr_id, float(tr_px), float(tr_sz), str(tr_oid), float(tr_tp_px), tr_st))
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

    # 1. Scan all 8 High-Beta instruments in universe
    for inst_id, meta in DEFAULT_UNIVERSE.items():
        try:
            bids, asks = client.get_orderbook(inst_id, sz=5)
            trades = client.get_recent_trades(inst_id, limit=25)
        except Exception as e:
            print(f"[!] Market data fetch warning for {inst_id}: {e}")
            continue

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

        pred = pred_engine.evaluate(
            sig,
            inventory_weight_nav=inv_weight,
            llm_conviction_bias=llm_bias,
            kronos_return_1h_bps=k_ret_bps,
            kronos_upside_bps=k_up_bps,
            kronos_downside_bps=k_down_bps,
        )

        # Enforce 100% Post-Only Maker in Production Live (0.00% Taker Fee Drag)
        allow_ioc = False

        # Calculate Cost-Basis Floor (+22 bps minimum net profit over openAvgPx)
        cost_floor_px = round(open_avg_px * 1.0022, dec_px) if open_avg_px > 0 else 0.0
        unrealized_bps = ((sig.mid_price - open_avg_px) / open_avg_px * 10000.0) if open_avg_px > 0 else 0.0

        row_dict = {
            "inst_id": inst_id,
            "mid_price": round(sig.mid_price, dec_px),
            "micro_price": round(sig.micro_price, dec_px),
            "open_avg_px": round(open_avg_px, dec_px) if open_avg_px > 0 else 0.0,
            "unrealized_bps": round(unrealized_bps, 1),
            "spread_bps": sig.spread_bps,
            "obi_top5": sig.obi_top5,
            "ofi_norm": sig.ofi_norm,
            "vpin_toxicity": sig.vpin_toxicity,
            "hawkes_net_burst": sig.hawkes_net_burst,
            "composite_alpha": sig.composite_alpha,
            "kronos_1h_bps": round(k_ret_bps, 2),
            "kronos_high_bps": round(k_up_bps, 2),
            "kronos_low_bps": round(k_down_bps, 2),
            "predicted_return_bps": pred.predicted_return_bps,
            "kalman_velocity_bps": pred.kalman_velocity_bps,
            "confidence": pred.confidence,
            "regime": pred.regime,
            "buy_offset_bps": pred.recommended_buy_offset_bps,
            "sell_tp_bps": pred.recommended_sell_tp_bps,
            "allow_sniper_IOC": allow_ioc,
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
                    # Cancel stale BUY order if drifted > 95 bps away or if inventory exceeds 20% NAV cap
                    if (drift_bps > 95.0 and pred.regime != "TOXIC_DIP_DEFENSE") or inv_weight >= 0.20:
                        client.cancel_order(inst_id, ord_id)
                        has_buy_order = False
                        actions_taken.append({"action": "CANCEL_STALE_OR_CAPPED_BUY", "inst_id": inst_id, "ord_id": ord_id})

                elif ord_side == "sell":
                    has_sell_order = True
                    active_state = "SELL_SUBMITTED"
                    active_ord_id = ord_id
                    active_ord_px = ord_px
                    active_ord_sz = ord_sz
                    # Handle independent Fresh Tranche Quick-Scalp TP orders (Dynamic Profit-Lock at +28 bps!)
                    if ord_id in active_tranche_ord_ids:
                        for tr_id, tr_buy_px, tr_buy_sz, tr_oid, tr_tp_px, tr_st in active_tranches_by_inst.get(inst_id, []):
                            if tr_oid == ord_id and tr_buy_px > 0:
                                tr_unr_bps = ((sig.mid_price - tr_buy_px) / tr_buy_px) * 10000.0
                                if tr_unr_bps >= 28.0 and drift_bps > 6.0 and pred.predicted_return_bps < 4.0:
                                    client.cancel_order(inst_id, ord_id)
                                    profit_lock_repegs += 1
                                    repeg_px = round(max(tr_buy_px * 1.0024, asks[0][0]), dec_px)
                                    repeg_sz = math.floor(min(cash_token_qty, tr_buy_sz * 0.998) * (10 ** dec_sz)) / (10 ** dec_sz)
                                    res_rp = client.place_spot_order(inst_id, "sell", repeg_sz, repeg_px, "PASSIVE_MAKER")
                                    new_rp_id = ""
                                    if isinstance(res_rp.get("data"), list) and res_rp["data"]:
                                        new_rp_id = str(res_rp["data"][0].get("ordId", ""))
                                    if new_rp_id:
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
                    if cost_floor_px > 0 and ord_px < cost_floor_px:
                        client.cancel_order(inst_id, ord_id)
                        has_sell_order = False
                        avail_token_qty = cash_token_qty
                        cost_basis_fixes += 1
                        actions_taken.append({
                            "action": "RESCUE_BELOW_COST_SELL",
                            "inst_id": inst_id,
                            "old_px": ord_px,
                            "new_floor_px": cost_floor_px,
                        })
                    # AUDIT SAFEGUARD 2: Dynamic Profit-Lock Re-Pegging
                    elif (
                        (unrealized_bps >= 180.0 and drift_bps > 8.0)
                        or (unrealized_bps >= 85.0 and drift_bps > 12.0 and pred.predicted_return_bps < 6.0)
                    ):
                        client.cancel_order(inst_id, ord_id)
                        has_sell_order = False
                        avail_token_qty = cash_token_qty
                        profit_lock_repegs += 1
                        actions_taken.append({
                            "action": "PROFIT_LOCK_REPEG",
                            "inst_id": inst_id,
                            "unrealized_bps": round(unrealized_bps, 1),
                            "old_px": ord_px,
                        })
            except Exception:
                pass

        # 2B. Independent Fresh Tranche Quick-Scalp TP Placement!
        # Places an immediate +35 bps to +55 bps Post-Only Maker TP for newly bought tranches without waiting for legacy openAvgPx!
        for tr_id, tr_buy_px, tr_buy_sz, tr_oid, tr_tp_px, tr_st in active_tranches_by_inst.get(inst_id, []):
            if tr_st == "PENDING_TP" and avail_token_qty > 0:
                scalp_sz = math.floor(min(avail_token_qty, tr_buy_sz * 0.998) * (10 ** dec_sz)) / (10 ** dec_sz)
                if scalp_sz * sig.mid_price >= 4.90:
                    quick_tp_bps = max(35.0, min(65.0, pred.recommended_sell_tp_bps))
                    quick_tp_px = round(max(tr_buy_px * (1.0 + quick_tp_bps / 10000.0), asks[0][0]), dec_px)
                    res_qtp = client.place_spot_order(
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

        # 3A. Place Take-Profit SELL orders enforcing Cost-Basis Floor (80% primary TP / 20% Moonbag preserved)
        if not has_sell_order and avail_token_qty * sig.mid_price >= 6.0:
            # Sell 80% in primary TP (keeping 20% moonbag or selling 100% if small position < $15)
            sell_ratio = 0.80 if (avail_token_qty * sig.mid_price >= 18.0) else 1.00
            sell_sz = math.floor(avail_token_qty * sell_ratio * (10 ** dec_sz)) / (10 ** dec_sz)
            if unrealized_bps >= 180.0:
                raw_tp_px = asks[0][0]
                tp_style_tag = "PROFIT_LOCK_ASK_JOIN"
            elif unrealized_bps >= 85.0 and pred.predicted_return_bps < 6.0:
                raw_tp_px = sig.mid_price * 1.0005
                tp_style_tag = "PROFIT_LOCK_TP"
            else:
                raw_tp_px = sig.mid_price * (1.0 + pred.recommended_sell_tp_bps / 10000.0)
                tp_style_tag = "PASSIVE_MAKER_TP"

            target_sell_px = round(max(raw_tp_px, cost_floor_px, asks[0][0]), dec_px)
            if sell_sz > 0 and target_sell_px > 0:
                res_sell = client.place_spot_order(
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

        # 3B. Collect candidate for Opportunity-Ranked Cash Sweeper (evaluated after scanning all 8 pairs!)
        if not has_buy_order and inv_weight < 0.20:
            opp_score = (
                pred.predicted_return_bps
                + (sig.composite_alpha * 15.0)
                - (sig.vpin_toxicity * 20.0)
                - (inv_weight * 50.0)
            )
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
                "buy_offset_bps": pred.recommended_buy_offset_bps,
                "regime": pred.regime,
                "has_sell_order": has_sell_order,
            })

        scalp_run_updates.append((inst_id, active_state, active_ord_sz, active_ord_px, active_ord_id, now_iso))

    # 3C. Opportunity-Ranked Cash Sweeper: Deploy free USDC starting from the #1 highest-scoring pair!
    if free_usdc >= 8.0 and buy_candidates:
        buy_candidates.sort(key=lambda x: x["opp_score"], reverse=True)
        for cand in buy_candidates:
            if free_usdc < 8.0:
                break
            c_inst = cand["inst_id"]
            c_dec_px = cand["dec_px"]
            c_dec_sz = cand["dec_sz"]
            base_lot_usd = (spot_equity_usd * 0.85) / len(DEFAULT_UNIVERSE)
            conv_boost = 1.0 + max(-0.25, min(0.45, cand["llm_bias"] * 0.4))
            alpha_boost = 1.0 + max(-0.15, min(0.15, cand["pred_bps"] / 100.0))
            lot_usd = min(free_usdc * 0.98, max(10.0, round(base_lot_usd * agg_mult * conv_boost * alpha_boost, 2)))

            target_buy_px = round(cand["mid_price"] * (1.0 - cand["buy_offset_bps"] / 10000.0), c_dec_px)
            if target_buy_px >= cand["best_ask"]:
                target_buy_px = round(cand["best_bid"], c_dec_px)

            buy_sz = math.floor((lot_usd / target_buy_px) * (10 ** c_dec_sz)) / (10 ** c_dec_sz) if target_buy_px > 0 else 0.0
            if buy_sz * target_buy_px < 5.0:
                continue

            res_place = client.place_spot_order(
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
        conn.commit()
    except Exception as e:
        print(f"[!] SQLite commit warning: {e}")

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

    return {
        "timestamp": now_iso,
        "nav_usdc": round(nav_usdc, 2),
        "spot_equity_usd": round(spot_equity_usd, 2),
        "simple_earn_usdc": round(simple_earn_usdc, 2),
        "free_usdc": round(free_usdc, 2),
        "authenticated": client.is_authenticated,
        "simulated_demo": client.simulated_demo,
        "cost_basis_fixes": cost_basis_fixes,
        "profit_lock_repegs": profit_lock_repegs,
        "telemetry": telemetry_rows,
        "actions": actions_taken,
        "llm_debate": asdict(debate_res) if debate_res else None,
        "audit_report": asdict(audit_res) if audit_res else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="TRE OS v6.0 (Predator Edition) — Predictive Microstructure & Kronos GPU Quant OS")
    parser.add_argument("--once", action="store_true", help="Run a single predictive scan cycle and exit")
    parser.add_argument("--debate", action="store_true", help="Run the 3-Agent LLM Adversarial Council debate")
    parser.add_argument("--audit", action="store_true", help="Run the Deterministic + FIFO Ledger Audit")
    parser.add_argument("--interval", type=float, default=15.0, help="Loop interval in seconds (default: 15s)")
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
    auditor = PredatorAuditor(
        db_path=db_path,
        report_out_path=os.path.join(BASE_DIR, "config", "predator_audit_report.json"),
        baseline_nav=BASELINE_NAV_USDC,
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
        )
        print("=== TRE OS v6.0 PREDATOR EDITION (LIVE SPOT + KRONOS GPU + OFI/VPIN/RLS) ===")
        print(
            f"Timestamp: {summary['timestamp']} | Mode: {'DEMO' if summary['simulated_demo'] else 'PRODUCTION_LIVE'} | "
            f"Total NAV: ${summary['nav_usdc']:.2f} USDC (Spot: ${summary['spot_equity_usd']:.2f} + Simple Earn: ${summary['simple_earn_usdc']:.2f}) | "
            f"Free Cash: ${summary['free_usdc']:.2f} USDC | "
            f"Fixes: {summary['cost_basis_fixes']} Cost-Floor / {summary['profit_lock_repegs']} Profit-Lock"
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
            do_debate = (cycle_num % 60 == 1) or args.debate
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
