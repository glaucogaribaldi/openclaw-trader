#!/usr/bin/env python3
"""
TRE OS v13.0 — Parallel Sovereign Perpetual Futures Demo Engine (predator_futures_demo.py)
Runs in parallel with predator_daemon.py on brody, sharing the local 7-Horizon Kronos-mini (4.1M)
RAM Oracle (127.0.0.1:8090, 0 MB extra PyTorch RAM) and Gemini Free Ordinary Internal Auditor.
"""
from __future__ import annotations
import argparse, datetime, json, math, os, sqlite3, ssl, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from core.kronos_oracle import KronosOracleClient
from core.microstructure import MicrostructureEngine
from execution.okx_hybrid_executor import OKXNativeClient
from predator_daemon import evaluate_run_lifecycle, load_dotenv
_OKX_PUBLIC_CLIENT = OKXNativeClient(simulated_demo=False)

FUTURES_UNIVERSE: Dict[str, Dict[str, Any]] = {
    "BTC-USDT-SWAP":  {"spot_id": "BTC-USDC",  "coin": "BTC",  "dec_px": 1, "dec_sz": 4},
    "SOL-USDT-SWAP":  {"spot_id": "SOL-USDC",  "coin": "SOL",  "dec_px": 2, "dec_sz": 2},
    "HYPE-USDT-SWAP": {"spot_id": "HYPE-USDC", "coin": "HYPE", "dec_px": 3, "dec_sz": 2},
    "LINK-USDT-SWAP": {"spot_id": "LINK-USDC", "coin": "LINK", "dec_px": 3, "dec_sz": 1},
    "SUI-USDT-SWAP":  {"spot_id": "SUI-USDC",  "coin": "SUI",  "dec_px": 4, "dec_sz": 1},
    "UNI-USDT-SWAP":  {"spot_id": "UNI-USDC",  "coin": "UNI",  "dec_px": 3, "dec_sz": 1},
    "TAO-USDT-SWAP":  {"spot_id": "TAO-USDC",  "coin": "TAO",  "dec_px": 2, "dec_sz": 3},
    "WLD-USDT-SWAP":  {"spot_id": "WLD-USDC",  "coin": "WLD",  "dec_px": 4, "dec_sz": 1},
    "ENA-USDT-SWAP":  {"spot_id": "ENA-USDC",  "coin": "ENA",  "dec_px": 4, "dec_sz": 0},
    "ARB-USDT-SWAP":  {"spot_id": "ARB-USDC",  "coin": "ARB",  "dec_px": 4, "dec_sz": 0},
    "AVAX-USDT-SWAP": {"spot_id": "AVAX-USDC", "coin": "AVAX", "dec_px": 3, "dec_sz": 1},
    "NEAR-USDT-SWAP": {"spot_id": "NEAR-USDC", "coin": "NEAR", "dec_px": 3, "dec_sz": 1},
}

STARTING_DEMO_NAV_USDC = 275.01
HISTORICAL_22OCT_SIM_NAV_USDC = 311.71
LEVERAGE = 2.5
MAKER_FEE_RATE = 0.0002  # 2 bps entry + 2 bps exit = 4 bps round-trip on notional
MAX_SLOTS = 4
SLOT_NAV_PCT = 0.125     # 12.5% of live NAV per slot (continuous compounding)
_IO_POOL = ThreadPoolExecutor(max_workers=6)

def _ssl_ctx() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()

def init_futures_db(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""CREATE TABLE IF NOT EXISTS futures_demo_account (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        baseline_nav_usd REAL NOT NULL, current_nav_usd REAL NOT NULL, free_margin_usd REAL NOT NULL,
        realized_pnl_usd REAL NOT NULL, total_fees_usd REAL NOT NULL, wins_count INTEGER NOT NULL,
        stops_count INTEGER NOT NULL, shield_locks_count INTEGER NOT NULL, started_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS futures_demo_positions (
        pos_id TEXT PRIMARY KEY, inst_id TEXT NOT NULL, direction TEXT NOT NULL, leverage REAL NOT NULL,
        margin_usd REAL NOT NULL, notional_usd REAL NOT NULL, entry_px REAL NOT NULL, current_px REAL NOT NULL,
        tp_px REAL NOT NULL, sl_px REAL NOT NULL, peak_move_bps REAL NOT NULL, shield_armed INTEGER NOT NULL,
        entry_fee_usd REAL NOT NULL, status TEXT NOT NULL, opened_at TEXT NOT NULL, closed_at TEXT,
        exit_px REAL, realized_pnl_usd REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS futures_demo_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, model_used TEXT NOT NULL,
        fee_drag_ratio_pct REAL NOT NULL, min_kronos_10m_bps REAL NOT NULL, fast_shield_bps REAL NOT NULL, verdict TEXT NOT NULL
    )""")
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM futures_demo_account WHERE id = 1")
    if not cur.fetchone():
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cur.execute("INSERT INTO futures_demo_account VALUES (1, ?, ?, ?, 0.0, 0.0, 0, 0, 0, ?, ?)",
                    (STARTING_DEMO_NAV_USDC, STARTING_DEMO_NAV_USDC, STARTING_DEMO_NAV_USDC, now_iso, now_iso))
    conn.commit()
    return conn

def _fetch_swap_book_and_trades(inst_id: str):
    ctx = _ssl_ctx()
    bids, asks, trades = [], [], []
    high_2h, low_2h = 0.0, 0.0
    try:
        bids, asks = _OKX_PUBLIC_CLIENT.get_orderbook(inst_id, sz=5)
        trades = _OKX_PUBLIC_CLIENT.get_recent_trades(inst_id, limit=25)
        u_c = f"https://eea.okx.com/api/v5/market/candles?instId={inst_id}&bar=15m&limit=8"
        with urllib.request.urlopen(urllib.request.Request(u_c, headers={"User-Agent": "TRE-OS-Fut/13.1"}), timeout=5, context=ctx) as r:
            c_rows = json.loads(r.read().decode("utf-8")).get("data", [])
            if c_rows:
                high_2h = max(float(x[2]) for x in c_rows)
                low_2h = min(float(x[3]) for x in c_rows)
    except Exception:
        pass
    funding_bps = 0.0
    try:
        u_f = f"https://eea.okx.com/api/v5/public/funding-rate?instId={inst_id}"
        with urllib.request.urlopen(urllib.request.Request(u_f, headers={"User-Agent": "TRE-OS-Fut/13.1"}), timeout=4, context=ctx) as rf:
            f_rows = json.loads(rf.read().decode("utf-8")).get("data", [])
            if f_rows:
                funding_bps = float(f_rows[0].get("fundingRate") or 0.0) * 10000.0
    except Exception:
        pass
    return inst_id, bids, asks, trades, high_2h, low_2h, funding_bps

def run_gemini_ordinary_futures_audit(conn: sqlite3.Connection, nav_usd: float, telemetry: List[Dict[str, Any]]) -> Dict[str, Any]:
    default_audit = {
        "model_used": "deterministic-7h-auditor",
        "fee_drag_ratio_pct": 0.0, "min_kronos_10m_bps": 8.0, "fast_shield_bps": 32.0,
        "verdict": "Fee-Drag 0.0% (4 bps Maker). Piramide Kronos a 7 Orizzonti (5m/10m + 1h..24h) e 3 Regole Auree attive.",
    }
    cur = conn.cursor()
    cur.execute("SELECT realized_pnl_usd, total_fees_usd, wins_count, stops_count, shield_locks_count FROM futures_demo_account WHERE id=1")
    row = cur.fetchone() or (0.0, 0.0, 0, 0, 0)
    realized_pnl, tot_fees, wins, stops, shields = float(row[0]), float(row[1]), int(row[2]), int(row[3]), int(row[4])
    gross_profit = max(0.01, realized_pnl + tot_fees) if realized_pnl > 0 else 1.0
    fee_drag_pct = round((tot_fees / gross_profit) * 100.0, 2) if tot_fees > 0 else 0.0
    default_audit["fee_drag_ratio_pct"] = fee_drag_pct
    gemini_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    if not gemini_key:
        return default_audit
    compact_t = [{"id": t["inst_id"], "dir": t["allowed_direction"], "ofi": t["ofi_norm"], "k5m": t["kronos_5m_bps"], "k10m": t["kronos_10m_bps"], "k1h": t["kronos_1h_bps"], "k6h": t["kronos_6h_bps"], "k24h": t["kronos_24h_bps"]} for t in telemetry[:10]]
    prompt = (
        "Sei l'Auditor Ordinario Interno di TRE OS v13.0 Futures Demo (2.5x Isolated LONG+SHORT, OKX Maker Fee 4 bps round-trip). "
        f"NAV={nav_usd:.2f} USDC (Start=$275.01), RealizedPnL={realized_pnl:+.2f}, Fees={tot_fees:.3f} (FeeDrag={fee_drag_pct:.1f}%), Wins={wins}, ShieldLocks={shields}, Stops={stops}. "
        f"Telemetry 7-Horizons: {json.dumps(compact_t)}. "
        "Verifica che le commissioni non superino il 12% dei profitti, calibra min_kronos_10m_bps [6.0..18.0] e fast_shield_bps [28.0..48.0], ed emetti verdict (1 frase in italiano). Rispondi SOLO JSON: {min_kronos_10m_bps, fast_shield_bps, verdict}."
    )
    for g_mod in ("gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"):
        try:
            u = f"https://generativelanguage.googleapis.com/v1beta/models/{g_mod}:generateContent"
            payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.15, "responseMimeType": "application/json"}}
            req = urllib.request.Request(u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", ("x-goog-" + "api-key"): gemini_key})
            with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx()) as resp:
                d = json.loads(resp.read().decode("utf-8"))
                txt = (d.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")).strip()
                if txt and "{" in txt:
                    p = json.loads(txt)
                    res = {
                        "model_used": f"google-free:{g_mod}", "fee_drag_ratio_pct": fee_drag_pct,
                        "min_kronos_10m_bps": round(max(6.0, min(18.0, float(p.get("min_kronos_10m_bps") or 8.0))), 1),
                        "fast_shield_bps": round(max(24.0, min(32.0, float(p.get("fast_shield_bps") or 28.0))), 1),
                        "verdict": str(p.get("verdict") or default_audit["verdict"])[:260],
                    }
                    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    cur.execute("INSERT INTO futures_demo_audit_log (timestamp, model_used, fee_drag_ratio_pct, min_kronos_10m_bps, fast_shield_bps, verdict) VALUES (?, ?, ?, ?, ?, ?)",
                                (now_iso, res["model_used"], fee_drag_pct, res["min_kronos_10m_bps"], res["fast_shield_bps"], res["verdict"]))
                    conn.commit()
                    return res
        except Exception:
            continue
    return default_audit

def run_futures_demo_cycle(conn: sqlite3.Connection, micro_engine: MicrostructureEngine, kronos_client: KronosOracleClient, run_audit: bool = False) -> Dict[str, Any]:
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    lifecycle = evaluate_run_lifecycle()
    spot_ids = [m["spot_id"] for m in FUTURES_UNIVERSE.values()]
    kronos_map = kronos_client.fetch_forecasts(spot_ids)
    cur = conn.cursor()
    cur.execute("SELECT baseline_nav_usd, current_nav_usd, free_margin_usd, realized_pnl_usd, total_fees_usd, wins_count, stops_count, shield_locks_count, started_at FROM futures_demo_account WHERE id=1")
    acct = cur.fetchone()
    base_nav, curr_nav, free_mgn, realized_pnl, tot_fees, wins_cnt, stops_cnt, shields_cnt, started_at = float(acct[0]), float(acct[1]), float(acct[2]), float(acct[3]), float(acct[4]), int(acct[5]), int(acct[6]), int(acct[7]), str(acct[8])
    cur.execute("SELECT min_kronos_10m_bps, fast_shield_bps, model_used, verdict, fee_drag_ratio_pct FROM futures_demo_audit_log ORDER BY id DESC LIMIT 1")
    last_aud = cur.fetchone()
    min_k10m_gate = float(last_aud[0]) if last_aud else 8.0
    fast_shield_gate_bps = float(last_aud[1]) if last_aud else 32.0
    aud_model = str(last_aud[2]) if last_aud else "baseline-7h-auditor"
    aud_verdict = str(last_aud[3]) if last_aud else "7-Horizon Kronos + 4bps Maker Fee Guard active."
    fee_drag_pct = float(last_aud[4]) if last_aud else 0.0
    cur.execute("SELECT pos_id, inst_id, direction, leverage, margin_usd, notional_usd, entry_px, tp_px, sl_px, peak_move_bps, shield_armed, entry_fee_usd, opened_at FROM futures_demo_positions WHERE status='OPEN'")
    open_positions = {r[1]: r for r in cur.fetchall()}
    # Audit Fix 1: Post-Exit Cooldown Map (30m cooldown after profit/shield exit, 120m cooldown after stoploss exit!)
    cur.execute("SELECT inst_id, status, (julianday('now') - julianday(closed_at)) * 1440.0 FROM futures_demo_positions WHERE status != 'OPEN' AND closed_at IS NOT NULL ORDER BY closed_at DESC LIMIT 40")
    cooldown_blocked_insts = set()
    for c_inst, c_st, mins_ago in cur.fetchall():
        req_cd = 120.0 if c_st == "CLOSED_STOPLOSS" else 30.0
        if float(mins_ago or 0.0) < req_cd:
            cooldown_blocked_insts.add(str(c_inst))
    market_snaps = list(_IO_POOL.map(_fetch_swap_book_and_trades, list(FUTURES_UNIVERSE.keys())))
    # Audit Fix 2: BTC-USDT-SWAP Macro Correlation Veto
    btc_fc = kronos_map.get("BTC-USDC")
    btc_k5m = btc_fc.kronos_5m_bps if btc_fc else 0.0
    btc_k1h = btc_fc.expected_return_1h_bps if btc_fc else 0.0
    telemetry_rows, actions_taken, candidates = [], [], []
    unrealized_total_usd, locked_margin_total_usd = 0.0, 0.0
    for inst_id, bids, asks, trades, high_2h, low_2h, funding_bps in market_snaps:
        if not bids or not asks:
            continue
        meta = FUTURES_UNIVERSE[inst_id]
        sig = micro_engine.process_snapshot(inst_id, bids, asks, trades)
        mid = sig.mid_price
        if mid <= 0:
            continue
        k_fc = kronos_map.get(meta["spot_id"])
        k5m = k_fc.kronos_5m_bps if k_fc else 0.0
        k10m = k_fc.kronos_10m_bps if k_fc else 0.0
        k1h = k_fc.expected_return_1h_bps if k_fc else 0.0
        k2h = k_fc.macro_return_2h_bps if k_fc else 0.0
        k6h = k_fc.horizon_6h_bps if k_fc else 0.0
        k12h = k_fc.swing_return_12h_bps if k_fc else 0.0
        k24h = k_fc.daily_return_24h_bps if k_fc else 0.0
        # Strict 7-Horizon Alignment (5m + 10m + 1h + 2h + 6h/12h/24h must agree on direction — never short a 1h/2h rebound!)
        macro_bull = bool(k6h >= 10.0 and (k12h >= 10.0 or k24h >= 10.0) and k2h >= 0.0 and k1h >= 6.0)
        macro_bear = bool(k6h <= -10.0 and (k12h <= -10.0 or k24h <= -10.0) and k2h <= 0.0 and k1h <= -6.0)
        allowed_dir = "LONG" if macro_bull else ("SHORT" if macro_bear else "NEUTRAL")
        drop_2h_bps = ((high_2h - mid) / high_2h * 10000.0) if high_2h > 0 else 0.0
        bounce_2h_bps = ((mid - low_2h) / low_2h * 10000.0) if low_2h > 0 else 0.0
        if inst_id in open_positions:
            p_id, _, p_dir, p_lev, p_mgn, p_notional, p_entry, p_tp, p_sl, p_peak_bps, p_shield, p_efee, p_open_ts = open_positions[inst_id]
            move_bps = ((mid - p_entry) / p_entry * 10000.0) if p_dir == "LONG" else ((p_entry - mid) / p_entry * 10000.0)
            new_peak = max(float(p_peak_bps), move_bps)
            eff_shield_gate = min(30.0, fast_shield_gate_bps)
            new_shield = 1 if (int(p_shield) == 1 or new_peak >= eff_shield_gate) else 0
            exit_reason, exit_exec_px = None, mid
            if (p_dir == "LONG" and bids[0][0] >= p_tp) or (p_dir == "SHORT" and asks[0][0] <= p_tp):
                exit_reason, exit_exec_px = "CLOSED_PROFIT", p_tp
            elif new_shield == 1:
                locked_move_bps = max(18.0, new_peak * 0.82)
                ideal_lock_px = round(p_entry * (1.0 + locked_move_bps / 10000.0), meta["dec_px"]) if p_dir == "LONG" else round(p_entry * (1.0 - locked_move_bps / 10000.0), meta["dec_px"])
                if move_bps <= locked_move_bps:
                    exit_reason = "CLOSED_SHIELD"
                    exit_exec_px = ideal_lock_px
            if not exit_reason and move_bps <= -110.0:
                broken = bool((p_dir == "LONG" and k5m < -5.0 and k6h < -15.0) or (p_dir == "SHORT" and k5m > 5.0 and k6h > 15.0))
                if broken or move_bps <= -156.0:
                    exit_reason = "CLOSED_STOPLOSS"
                    exit_exec_px = asks[0][0] if p_dir == "LONG" else bids[0][0]
            if exit_reason:
                realized_move_bps = max(-156.0, ((exit_exec_px - p_entry) / p_entry * 10000.0) if p_dir == "LONG" else ((p_entry - exit_exec_px) / p_entry * 10000.0))
                exit_fee_usd = round(p_notional * MAKER_FEE_RATE, 4)
                net_pnl_usd = round((p_notional * (realized_move_bps / 10000.0)) - p_efee - exit_fee_usd, 4)
                free_mgn = round(free_mgn + p_mgn + net_pnl_usd, 4)
                realized_pnl = round(realized_pnl + net_pnl_usd, 4)
                tot_fees = round(tot_fees + p_efee + exit_fee_usd, 4)
                if exit_reason == "CLOSED_PROFIT": wins_cnt += 1
                elif exit_reason == "CLOSED_SHIELD": shields_cnt += 1
                else: stops_cnt += 1
                cur.execute("UPDATE futures_demo_positions SET status=?, closed_at=?, exit_px=?, realized_pnl_usd=?, current_px=?, peak_move_bps=?, shield_armed=? WHERE pos_id=?",
                            (exit_reason, now_iso, exit_exec_px, net_pnl_usd, exit_exec_px, new_peak, new_shield, p_id))
                del open_positions[inst_id]
                actions_taken.append({"action": exit_reason, "inst_id": inst_id, "dir": p_dir, "entry_px": p_entry, "exit_px": exit_exec_px, "net_pnl_usd": net_pnl_usd})
            else:
                unr_usd = round((p_notional * (move_bps / 10000.0)) - p_efee - (p_notional * MAKER_FEE_RATE), 3)
                unrealized_total_usd += unr_usd
                locked_margin_total_usd += p_mgn
                cur.execute("UPDATE futures_demo_positions SET current_px=?, peak_move_bps=?, shield_armed=? WHERE pos_id=?", (mid, new_peak, new_shield, p_id))
        # Audit Fix 1 + 2 + 3: Enforce Post-Exit Cooldown, BTC Correlation Veto, and Funding Rate Guard (<= 4.5 bps adverse funding)
        btc_veto_long = bool(btc_k5m <= -12.0 or btc_k1h <= -25.0)
        btc_veto_short = bool(btc_k5m >= 12.0 or btc_k1h >= 25.0)
        if inst_id not in open_positions and inst_id not in cooldown_blocked_insts and not lifecycle["reduce_only"]:
            if allowed_dir == "LONG" and not btc_veto_long and funding_bps <= 4.5 and k5m >= 4.0 and k10m >= 6.0 and sig.ofi_norm >= 0.18 and sig.vpin_toxicity <= 0.68:
                score = round((k5m * 0.8) + (k10m * 1.1) + (k1h * 0.4) + (k6h * 0.15) + (sig.ofi_norm * 18.0) - (funding_bps * 1.5), 2)
                candidates.append({"inst_id": inst_id, "dir": "LONG", "score": score, "px": bids[0][0], "dec_px": meta["dec_px"]})
            elif allowed_dir == "SHORT" and not btc_veto_short and funding_bps >= -4.5 and k5m <= -4.0 and k10m <= -6.0 and sig.ofi_norm <= -0.18 and sig.vpin_toxicity <= 0.68:
                score = round((abs(k5m) * 0.8) + (abs(k10m) * 1.1) + (abs(k1h) * 0.4) + (abs(k6h) * 0.15) + (abs(sig.ofi_norm) * 18.0) + (funding_bps * 1.5), 2)
                candidates.append({"inst_id": inst_id, "dir": "SHORT", "score": score, "px": asks[0][0], "dec_px": meta["dec_px"]})
        telemetry_rows.append({
            "inst_id": inst_id, "mid_price": mid, "ofi_norm": round(sig.ofi_norm, 2), "vpin_toxicity": round(sig.vpin_toxicity, 2),
            "kronos_5m_bps": round(k5m, 1), "kronos_10m_bps": round(k10m, 1), "kronos_1h_bps": round(k1h, 1),
            "kronos_2h_bps": round(k2h, 1), "kronos_6h_bps": round(k6h, 1), "kronos_12h_bps": round(k12h, 1), "kronos_24h_bps": round(k24h, 1),
            "allowed_direction": allowed_dir,
        })
    live_nav_est = round(base_nav + realized_pnl + unrealized_total_usd, 2)
    slot_margin_usd = round(live_nav_est * SLOT_NAV_PCT, 2)
    if len(open_positions) < MAX_SLOTS and free_mgn >= slot_margin_usd and candidates:
        candidates.sort(key=lambda x: x["score"], reverse=True)
        for cand in candidates:
            if len(open_positions) >= MAX_SLOTS or free_mgn < slot_margin_usd: break
            c_id, c_dir, c_px, c_dec = cand["inst_id"], cand["dir"], cand["px"], cand["dec_px"]
            notional_usd = round(slot_margin_usd * LEVERAGE, 2)
            entry_fee_usd = round(notional_usd * MAKER_FEE_RATE, 4)
            tp_px = round(c_px * 1.0110, c_dec) if c_dir == "LONG" else round(c_px * 0.9890, c_dec)
            sl_px = round(c_px * 0.9844, c_dec) if c_dir == "LONG" else round(c_px * 1.0156, c_dec)
            pos_id = f"FUT_{c_id.split('-')[0]}_{int(time.time()*1000)}"
            cur.execute("INSERT INTO futures_demo_positions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0, ?, 'OPEN', ?, NULL, NULL, NULL)",
                        (pos_id, c_id, c_dir, LEVERAGE, slot_margin_usd, notional_usd, c_px, c_px, tp_px, sl_px, entry_fee_usd, now_iso))
            free_mgn = round(free_mgn - slot_margin_usd, 4)
            locked_margin_total_usd += slot_margin_usd
            open_positions[c_id] = (pos_id, c_id, c_dir, LEVERAGE, slot_margin_usd, notional_usd, c_px, tp_px, sl_px, 0.0, 0, entry_fee_usd, now_iso)
            actions_taken.append({"action": f"OPEN_{c_dir}_2.5X", "inst_id": c_id, "px": c_px, "margin_usd": slot_margin_usd, "notional_usd": notional_usd})
    curr_nav = round(base_nav + realized_pnl + unrealized_total_usd, 2)
    cur.execute("UPDATE futures_demo_account SET current_nav_usd=?, free_margin_usd=?, realized_pnl_usd=?, total_fees_usd=?, wins_count=?, stops_count=?, shield_locks_count=?, updated_at=? WHERE id=1",
                (curr_nav, round(free_mgn, 2), round(realized_pnl, 4), round(tot_fees, 4), wins_cnt, stops_cnt, shields_cnt, now_iso))
    conn.commit()
    if run_audit:
        aud_res = run_gemini_ordinary_futures_audit(conn, curr_nav, telemetry_rows)
        aud_model, aud_verdict, fee_drag_pct = aud_res["model_used"], aud_res["verdict"], aud_res["fee_drag_ratio_pct"]
    cur.execute("SELECT pos_id, inst_id, direction, margin_usd, notional_usd, entry_px, current_px, tp_px, sl_px, peak_move_bps, shield_armed, opened_at FROM futures_demo_positions WHERE status='OPEN'")
    active_pos_list = [{"pos_id": r[0], "inst_id": r[1], "direction": r[2], "margin_usd": r[3], "notional_usd": r[4], "entry_px": r[5], "current_px": r[6], "tp_px": r[7], "sl_px": r[8], "peak_move_bps": round(float(r[9]), 1), "shield_armed": bool(r[10]), "opened_at": r[11]} for r in cur.fetchall()]
    snap = {
        "timestamp": now_iso, "baseline_nav_usd": base_nav,
        "historical_22oct_sim_nav_usd": round(HISTORICAL_22OCT_SIM_NAV_USDC + (curr_nav - base_nav), 2),
        "current_nav_usd": curr_nav, "free_margin_usd": round(free_mgn, 2), "locked_margin_usd": round(locked_margin_total_usd, 2),
        "realized_pnl_usd": round(realized_pnl, 4), "unrealized_pnl_usd": round(unrealized_total_usd, 3),
        "total_fees_usd": round(tot_fees, 4), "fee_drag_ratio_pct": fee_drag_pct,
        "wins_count": wins_cnt, "shield_locks_count": shields_cnt, "stops_count": stops_cnt,
        "auditor_model": aud_model, "auditor_verdict": aud_verdict,
        "open_positions": active_pos_list, "telemetry": telemetry_rows, "actions": actions_taken,
    }
    snap_path = os.path.join(BASE_DIR, "config", "futures_demo_snapshot.json")
    with open(snap_path + ".tmp", "w", encoding="utf-8") as f: json.dump(snap, f, indent=2)
    os.replace(snap_path + ".tmp", snap_path)
    return snap

def main() -> None:
    parser = argparse.ArgumentParser(description="TRE OS v13.0 — Parallel Perpetual Futures 2.5x Demo Engine")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=15.0)
    args = parser.parse_args()
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    conn = init_futures_db(os.path.join(BASE_DIR, "config", "okx_futures_demo.db"))
    micro = MicrostructureEngine(bucket_volume_usd=2500.0)
    kronos = KronosOracleClient()
    if args.once:
        s = run_futures_demo_cycle(conn, micro, kronos, run_audit=True)
        print(f"[FUTURES DEMO 2.5X] NAV={s['current_nav_usd']:.2f} | Free={s['free_margin_usd']:.2f} | OpenPos={len(s['open_positions'])} | Auditor={s['auditor_model']}")
        return
    cyc = 0
    while True:
        cyc += 1
        try: run_futures_demo_cycle(conn, micro, kronos, run_audit=(cyc % 80 == 1))
        except Exception as e: print(f"[!] Futures Demo cycle error: {e}")
        time.sleep(max(5.0, args.interval))

if __name__ == "__main__":
    main()