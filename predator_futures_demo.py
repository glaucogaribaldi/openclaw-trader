#!/usr/bin/env python3
"""
TRE OS v14.0 — Sovereign Perpetual Futures 2.5x Isolated Engine (LIVE & DEMO)
Operates on OKX Europe Regulated Perpetual Futures (*-USD_UM_XPERP-*, instType=FUTURES, settleCcy=USD 1:1 USDC).
Shares the local 7-Horizon Kronos-mini (4.1M) RAM Oracle (127.0.0.1:8090) and Gemini Free Ordinary Internal Auditor.
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

_OKX_CLIENT = OKXNativeClient(simulated_demo=False)

FUTURES_UNIVERSE: Dict[str, Dict[str, Any]] = {
    "BTC-USD_UM_XPERP-310404":    {"spot_id": "BTC-USDC",    "coin": "BTC",    "ct_val": 0.0001, "dec_px": 1, "dec_sz": 0, "min_sz": 1.0},
    "ETH-USD_UM_XPERP-310404":    {"spot_id": "ETH-USDC",    "coin": "ETH",    "ct_val": 0.001,  "dec_px": 2, "dec_sz": 0, "min_sz": 1.0},
    "SOL-USD_UM_XPERP-310404":    {"spot_id": "SOL-USDC",    "coin": "SOL",    "ct_val": 0.01,   "dec_px": 2, "dec_sz": 0, "min_sz": 1.0},
    "HYPE-USD_UM_XPERP-310523":   {"spot_id": "HYPE-USDC",   "coin": "HYPE",   "ct_val": 0.1,    "dec_px": 3, "dec_sz": 0, "min_sz": 1.0},
    "ZEC-USD_UM_XPERP-310530":    {"spot_id": "ZEC-USDC",    "coin": "ZEC",    "ct_val": 0.01,   "dec_px": 2, "dec_sz": 0, "min_sz": 1.0},
    "XRP-USD_UM_XPERP-310404":    {"spot_id": "XRP-USDC",    "coin": "XRP",    "ct_val": 1.0,    "dec_px": 4, "dec_sz": 0, "min_sz": 1.0},
    "NEAR-USD_UM_XPERP-310613":   {"spot_id": "NEAR-USDC",   "coin": "NEAR",   "ct_val": 1.0,    "dec_px": 3, "dec_sz": 0, "min_sz": 1.0},
    "LINK-USD_UM_XPERP-310523":   {"spot_id": "LINK-USDC",   "coin": "LINK",   "ct_val": 1.0,    "dec_px": 3, "dec_sz": 0, "min_sz": 1.0},
    "SUI-USD_UM_XPERP-310404":    {"spot_id": "SUI-USDC",    "coin": "SUI",    "ct_val": 1.0,    "dec_px": 4, "dec_sz": 0, "min_sz": 1.0},
    "BNB-USD_UM_XPERP-310523":    {"spot_id": "BNB-USDC",    "coin": "BNB",    "ct_val": 0.01,   "dec_px": 1, "dec_sz": 0, "min_sz": 1.0},
    "AVAX-USD_UM_XPERP-310530":   {"spot_id": "AVAX-USDC",   "coin": "AVAX",   "ct_val": 10.0,   "dec_px": 3, "dec_sz": 1, "min_sz": 0.1},
    "UNI-USD_UM_XPERP-310718":    {"spot_id": "UNI-USDC",    "coin": "UNI",    "ct_val": 1.0,    "dec_px": 3, "dec_sz": 0, "min_sz": 1.0},
}

STARTING_DEMO_NAV_USDC = 268.95
HISTORICAL_22OCT_SIM_NAV_USDC = 298.89
LEVERAGE = 4.0
MAKER_FEE_RATE = 0.0002  # 2 bps entry + 2 bps exit = 4 bps round-trip on notional
MAX_SLOTS = 4
SLOT_NAV_PCT = 0.20      # 20.0% of live NAV per slot (4 slots = 80% Chamber 1 Assault at 4.0x + 20% Chamber 2 Reserve)
_IO_POOL = ThreadPoolExecutor(max_workers=6)
_LEVERAGE_INITIALIZED = False

def _ssl_ctx() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()

def ensure_isolated_leverage(live_mode: bool) -> None:
    global _LEVERAGE_INITIALIZED
    if _LEVERAGE_INITIALIZED or not live_mode or not _OKX_CLIENT.is_authenticated:
        return
    for inst_id in FUTURES_UNIVERSE:
        try:
            _OKX_CLIENT._request("POST", "/api/v5/account/set-leverage", body_dict={"instId": inst_id, "lever": "4", "mgnMode": "isolated"}, auth=True)
        except Exception:
            pass
    _LEVERAGE_INITIALIZED = True

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
        bids, asks = _OKX_CLIENT.get_orderbook(inst_id, sz=5)
        trades = _OKX_CLIENT.get_recent_trades(inst_id, limit=25)
        u_c = f"https://eea.okx.com/api/v5/market/candles?instId={inst_id}&bar=15m&limit=8"
        with urllib.request.urlopen(urllib.request.Request(u_c, headers={"User-Agent": "TRE-OS-Fut/14.0"}), timeout=5, context=ctx) as r:
            c_rows = json.loads(r.read().decode("utf-8")).get("data", [])
            if c_rows:
                high_2h = max(float(x[2]) for x in c_rows)
                low_2h = min(float(x[3]) for x in c_rows)
    except Exception:
        pass
    return inst_id, bids, asks, trades, high_2h, low_2h, 0.0
_LAST_GEMINI_AUDIT_TS = 0.0

def load_gemini_brain_skills() -> Dict[str, Any]:
    p = os.path.join(BASE_DIR, "config", "gemini_brain_skills.json")
    default_skills = {
        "min_kronos_10m_bps": 7.5,
        "fast_shield_bps": 20.0,
        "trail_lock_ratio": 0.65,
        "dynamic_slot_leverage": 4.0,
        "force_close_inst_ids": [],
        "priority_boost_inst_ids": [],
        "blacklist_inst_ids": [],
        "verdict": "TRE OS v14.4 Empowered Gemini Brain active.",
    }
    try:
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            if isinstance(d, dict):
                default_skills.update(d)
    except Exception:
        pass
    return default_skills

def run_gemini_ordinary_futures_audit(conn: sqlite3.Connection, nav_usd: float, telemetry: List[Dict[str, Any]]) -> Dict[str, Any]:
    global _LAST_GEMINI_AUDIT_TS
    default_audit = load_gemini_brain_skills()
    default_audit["model_used"] = "deterministic-7h-auditor"
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
    cur.execute("SELECT inst_id, direction, margin_usd, entry_px, current_px, peak_move_bps, shield_armed, opened_at FROM futures_demo_positions WHERE status='OPEN'")
    open_pos_info = [{"inst_id": r[0], "dir": r[1], "mgn": r[2], "entry": r[3], "now": r[4], "peak_bps": round(float(r[5]), 1), "shield": bool(r[6]), "opened": r[7]} for r in cur.fetchall()]
    cur.execute("SELECT inst_id, direction, realized_pnl_usd, status, closed_at FROM futures_demo_positions WHERE status != 'OPEN' ORDER BY closed_at DESC LIMIT 8")
    recent_closed_info = [{"inst_id": r[0], "dir": r[1], "pnl_usd": r[2], "status": r[3], "closed": r[4]} for r in cur.fetchall()]
    compact_t = [{"id": t["inst_id"], "dir": t["allowed_direction"], "ofi": t["ofi_norm"], "vpin": t["vpin_toxicity"], "k5m": t["kronos_5m_bps"], "k10m": t["kronos_10m_bps"], "k1h": t["kronos_1h_bps"], "k2h": t["kronos_2h_bps"], "k6h": t["kronos_6h_bps"], "k12h": t["kronos_12h_bps"], "k24h": t["kronos_24h_bps"]} for t in telemetry]
    prompt = (
        "Sei il Cervello Quantitativo e Auditor di TRE OS v14.4 Anti-Crash Fortress su OKX EEA Perpetual Futures (*-USD_UM_XPERP-*, leva 4.0x Isolated LONG+SHORT, 4 slot x 20% NAV, Maker fee 2bps). "
        f"NAV={nav_usd:.2f} USDC, RealizedPnL={realized_pnl:+.4f}, Fees={tot_fees:.4f} (FeeDrag={fee_drag_pct:.1f}%), Wins={wins}, Shields={shields}, Stops={stops}. "
        f"OpenPositions={json.dumps(open_pos_info)}. RecentClosed={json.dumps(recent_closed_info)}. "
        f"FullTelemetry12Pairs={json.dumps(compact_t)}. "
        "Hai tutti i 5 poteri operativi (Skills): "
        "1) force_close_inst_ids: lista di inst_id aperti da chiudere subito se la tesi 1h/6h è deteriorata; "
        "2) trail_lock_ratio [0.58..0.85]: 0.60 largo per lasciar correre trend forti, 0.82 stretto in mercato laterale; "
        "3) priority_boost_inst_ids (max 3 inst_id migliori) e blacklist_inst_ids (inst_id tossici da bloccare); "
        "4) dynamic_slot_leverage [2.5..4.0] e min_kronos_10m_bps [6.0..12.0] e fast_shield_bps [18.0..28.0]; "
        "5) verdict (1 frase incisiva in italiano). "
        "Rispondi SOLO JSON: {min_kronos_10m_bps, fast_shield_bps, trail_lock_ratio, dynamic_slot_leverage, force_close_inst_ids, priority_boost_inst_ids, blacklist_inst_ids, verdict}."
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
                        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "model_used": f"google-free:{g_mod}", "fee_drag_ratio_pct": fee_drag_pct,
                        "min_kronos_10m_bps": round(max(6.0, min(12.0, float(p.get("min_kronos_10m_bps") or 7.5))), 1),
                        "fast_shield_bps": round(max(18.0, min(28.0, float(p.get("fast_shield_bps") or 20.0))), 1),
                        "trail_lock_ratio": round(max(0.58, min(0.85, float(p.get("trail_lock_ratio") or 0.65))), 2),
                        "dynamic_slot_leverage": round(max(2.5, min(4.0, float(p.get("dynamic_slot_leverage") or 4.0))), 1),
                        "force_close_inst_ids": [str(x) for x in (p.get("force_close_inst_ids") or []) if isinstance(x, str)],
                        "priority_boost_inst_ids": [str(x) for x in (p.get("priority_boost_inst_ids") or []) if isinstance(x, str)][:3],
                        "blacklist_inst_ids": [str(x) for x in (p.get("blacklist_inst_ids") or []) if isinstance(x, str)],
                        "verdict": str(p.get("verdict") or default_audit["verdict"])[:280],
                    }
                    _LAST_GEMINI_AUDIT_TS = time.time()
                    sp = os.path.join(BASE_DIR, "config", "gemini_brain_skills.json")
                    with open(sp + ".tmp", "w", encoding="utf-8") as sf: json.dump(res, sf, indent=2)
                    os.replace(sp + ".tmp", sp)
                    cur.execute("INSERT INTO futures_demo_audit_log (timestamp, model_used, fee_drag_ratio_pct, min_kronos_10m_bps, fast_shield_bps, verdict) VALUES (?, ?, ?, ?, ?, ?)",
                                (res["updated_at"], res["model_used"], fee_drag_pct, res["min_kronos_10m_bps"], res["fast_shield_bps"], res["verdict"]))
                    conn.commit()
                    return res
        except Exception:
            continue
    return default_audit

def _calc_contract_sz(inst_id: str, notional_usd: float, px: float) -> Tuple[str, float]:
    meta = FUTURES_UNIVERSE[inst_id]
    ct_val = float(meta.get("ct_val", 1.0))
    dec_sz = int(meta.get("dec_sz", 0))
    min_sz = float(meta.get("min_sz", 1.0))
    raw_cts = notional_usd / max(1e-9, px * ct_val)
    cts = round(raw_cts, dec_sz) if dec_sz > 0 else float(int(round(raw_cts)))
    if cts < min_sz:
        cts = min_sz
    actual_notional = round(cts * px * ct_val, 2)
    sz_str = f"{cts:.{dec_sz}f}" if dec_sz > 0 else str(int(cts))
    return sz_str, actual_notional

def _sync_live_okx_account_and_cancel_stale(live_mode: bool) -> Tuple[float, float, Dict[str, Dict[str, Any]], set]:
    if not live_mode or not _OKX_CLIENT.is_authenticated:
        return 0.0, 0.0, {}, set()
    real_nav, real_free = 0.0, 0.0
    live_pos_map: Dict[str, Dict[str, Any]] = {}
    live_pend_set: set = set()
    try:
        b_res = _OKX_CLIENT._request("GET", "/api/v5/account/balance", auth=True).get("data", [])
        if b_res:
            real_nav = float(b_res[0].get("totalEq") or 0.0)
            for d in b_res[0].get("details", []):
                if d.get("ccy") == "USDC":
                    real_free = float(d.get("availBal") or d.get("availEq") or 0.0)
                    if real_nav <= 0.0:
                        real_nav = float(d.get("eqUsd") or real_free)
    except Exception:
        pass
    try:
        pend = _OKX_CLIENT._request("GET", "/api/v5/trade/orders-pending?instType=FUTURES", auth=True).get("data", [])
        now_ms = int(time.time() * 1000)
        for o in pend:
            c_ms = int(o.get("cTime") or now_ms)
            if (now_ms - c_ms) >= 22000:
                _OKX_CLIENT._request("POST", "/api/v5/trade/cancel-order", body_dict={"instId": o["instId"], "ordId": o["ordId"]}, auth=True)
            else:
                live_pend_set.add(str(o.get("instId") or ""))
    except Exception:
        pass
    try:
        p_rows = _OKX_CLIENT._request("GET", "/api/v5/account/positions?instType=FUTURES", auth=True).get("data", [])
        for p in p_rows:
            pos_sz = float(p.get("pos") or 0.0)
            if abs(pos_sz) > 0:
                live_pos_map[p["instId"]] = p
    except Exception:
        pass
    return real_nav, real_free, live_pos_map, live_pend_set

def _execute_live_xperp_order(inst_id: str, side: str, sz_str: str, px: float, dec_px: int, reduce_only: bool = False, urgent_stop: bool = False, tp_px: float = 0.0, sl_px: float = 0.0) -> bool:
    if not _OKX_CLIENT.is_authenticated:
        return False
    px_str = f"{px:.{dec_px}f}"
    body: Dict[str, Any] = {
        "instId": inst_id,
        "tdMode": "isolated",
        "side": side,
        "ordType": "market" if (urgent_stop or reduce_only) else "post_only",
        "sz": sz_str,
    }
    if body["ordType"] != "market":
        body["px"] = px_str
    if reduce_only:
        body["reduceOnly"] = True
    elif tp_px > 0.0 and sl_px > 0.0:
        # Anti-Crash Hardware Shield: attach native TP and SL directly inside OKX Matching Engine!
        body["attachAlgoOrds"] = [{
            "tpTriggerPx": f"{tp_px:.{dec_px}f}",
            "tpOrdPx": "-1",
            "tpTriggerPxType": "last",
            "slTriggerPx": f"{sl_px:.{dec_px}f}",
            "slOrdPx": "-1",
            "slTriggerPxType": "last",
        }]
    try:
        r = _OKX_CLIENT._request("POST", "/api/v5/trade/order", body_dict=body, auth=True)
        d = (r.get("data") or [{}])[0]
        if str(d.get("sCode", "")) == "0":
            return True
    except Exception:
        pass
    return False
def run_futures_demo_cycle(conn: sqlite3.Connection, micro_engine: MicrostructureEngine, kronos_client: KronosOracleClient, run_audit: bool = False, live_mode: bool = True) -> Dict[str, Any]:
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    ensure_isolated_leverage(live_mode)
    lifecycle = evaluate_run_lifecycle()
    spot_ids = [m["spot_id"] for m in FUTURES_UNIVERSE.values()]
    kronos_map = kronos_client.fetch_forecasts(spot_ids)
    cur = conn.cursor()
    cur.execute("SELECT baseline_nav_usd, current_nav_usd, free_margin_usd, realized_pnl_usd, total_fees_usd, wins_count, stops_count, shield_locks_count, started_at FROM futures_demo_account WHERE id=1")
    acct = cur.fetchone()
    base_nav, curr_nav, free_mgn, realized_pnl, tot_fees, wins_cnt, stops_cnt, shields_cnt, started_at = float(acct[0]), float(acct[1]), float(acct[2]), float(acct[3]), float(acct[4]), int(acct[5]), int(acct[6]), int(acct[7]), str(acct[8])
    real_nav, real_free, live_okx_pos, live_okx_pend = _sync_live_okx_account_and_cancel_stale(live_mode)
    if live_mode and real_nav > 10.0:
        free_mgn = real_free
    brain_skills = load_gemini_brain_skills()
    cur.execute("SELECT min_kronos_10m_bps, fast_shield_bps, model_used, verdict, fee_drag_ratio_pct FROM futures_demo_audit_log ORDER BY id DESC LIMIT 1")
    last_aud = cur.fetchone()
    min_k10m_gate = float(brain_skills.get("min_kronos_10m_bps") or (last_aud[0] if last_aud else 7.5))
    fast_shield_gate_bps = float(brain_skills.get("fast_shield_bps") or (last_aud[1] if last_aud else 20.0))
    aud_model = str(last_aud[2]) if last_aud else "baseline-7h-auditor"
    aud_verdict = str(last_aud[3]) if last_aud else "7-Horizon Kronos + 4bps Maker XPERP Guard active."
    fee_drag_pct = float(last_aud[4]) if last_aud else 0.0
    cur.execute("SELECT pos_id, inst_id, direction, leverage, margin_usd, notional_usd, entry_px, tp_px, sl_px, peak_move_bps, shield_armed, entry_fee_usd, opened_at FROM futures_demo_positions WHERE status='OPEN'")
    open_positions = {r[1]: r for r in cur.fetchall()}
    if live_mode:
        for db_inst, db_row in list(open_positions.items()):
            if db_inst not in live_okx_pos and db_inst not in live_okx_pend:
                cur.execute("DELETE FROM futures_demo_positions WHERE pos_id=?", (db_row[0],))
                del open_positions[db_inst]
        for okx_inst, okx_p in live_okx_pos.items():
            if okx_inst in FUTURES_UNIVERSE and okx_inst not in open_positions:
                pos_val = float(okx_p.get("pos") or 0.0)
                avg_px = float(okx_p.get("avgPx") or 0.0)
                mgn_u = round(float(okx_p.get("margin") or 35.0), 2)
                not_u = round(abs(pos_val) * float(FUTURES_UNIVERSE[okx_inst]["ct_val"]) * avg_px, 2)
                p_dir = "LONG" if pos_val > 0 else "SHORT"
                c_dec = int(FUTURES_UNIVERSE[okx_inst]["dec_px"])
                tp_px = round(avg_px * 1.0110, c_dec) if p_dir == "LONG" else round(avg_px * 0.9890, c_dec)
                sl_px = round(avg_px * 0.9844, c_dec) if p_dir == "LONG" else round(avg_px * 1.0156, c_dec)
                efee = round(not_u * MAKER_FEE_RATE, 4)
                pid = f"XPERP_{okx_inst.split('-')[0]}_{int(okx_p.get('cTime') or int(time.time()*1000))}"
                cur.execute("INSERT OR REPLACE INTO futures_demo_positions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0, ?, 'OPEN', ?, NULL, NULL, NULL)",
                            (pid, okx_inst, p_dir, LEVERAGE, mgn_u, not_u, avg_px, avg_px, tp_px, sl_px, efee, now_iso))
                open_positions[okx_inst] = (pid, okx_inst, p_dir, LEVERAGE, mgn_u, not_u, avg_px, tp_px, sl_px, 0.0, 0, efee, now_iso)
        conn.commit()
    cur.execute("SELECT inst_id, status, (julianday('now') - julianday(closed_at)) * 1440.0 FROM futures_demo_positions WHERE status != 'OPEN' AND closed_at IS NOT NULL ORDER BY closed_at DESC LIMIT 40")
    cooldown_blocked_insts = set()
    for c_inst, c_st, mins_ago in cur.fetchall():
        req_cd = 120.0 if c_st == "CLOSED_STOPLOSS" else 30.0
        if float(mins_ago or 0.0) < req_cd:
            cooldown_blocked_insts.add(str(c_inst))
    market_snaps = list(_IO_POOL.map(_fetch_swap_book_and_trades, list(FUTURES_UNIVERSE.keys())))
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
        macro_bull = bool(k6h >= 8.0 and (k12h >= 5.0 or k24h >= 5.0) and k2h >= -8.0 and k1h >= 4.0)
        macro_bear = bool(k6h <= -8.0 and (k12h <= -5.0 or k24h <= -5.0) and k2h <= 8.0 and k1h <= -4.0)
        allowed_dir = "LONG" if macro_bull else ("SHORT" if macro_bear else "NEUTRAL")
        if inst_id in open_positions:
            p_id, _, p_dir, p_lev, p_mgn, p_notional, p_entry, p_tp, p_sl, p_peak_bps, p_shield, p_efee, p_open_ts = open_positions[inst_id]
            move_bps = ((mid - p_entry) / p_entry * 10000.0) if p_dir == "LONG" else ((p_entry - mid) / p_entry * 10000.0)
            new_peak = max(float(p_peak_bps), move_bps)
            try:
                pos_age_mins = (now_dt - datetime.datetime.fromisoformat(str(p_open_ts).replace("Z", "+00:00"))).total_seconds() / 60.0
            except Exception:
                pos_age_mins = 0.0
            eff_shield_gate = 12.0 if pos_age_mins >= 45.0 else max(22.0, fast_shield_gate_bps)
            new_shield = 1 if (new_peak >= eff_shield_gate) else 0
            exit_reason, exit_exec_px, urgent_stop = None, mid, False
            if (p_dir == "LONG" and bids[0][0] >= p_tp) or (p_dir == "SHORT" and asks[0][0] <= p_tp):
                exit_reason, exit_exec_px = "CLOSED_PROFIT", p_tp
            elif inst_id in brain_skills.get("force_close_inst_ids", []):
                exit_reason, exit_exec_px, urgent_stop = "CLOSED_SHIELD", (bids[0][0] if p_dir == "LONG" else asks[0][0]), True
            elif new_shield == 1:
                base_trail = float(brain_skills.get("trail_lock_ratio") or 0.65)
                trail_ratio = 0.82 if new_peak >= 65.0 else base_trail
                locked_move_bps = max(10.0, new_peak * trail_ratio)
                if move_bps <= locked_move_bps:
                    exit_reason = "CLOSED_SHIELD"
                    exit_exec_px = bids[0][0] if p_dir == "LONG" else asks[0][0]
            if not exit_reason and move_bps <= -55.0:
                inv_1h = bool(pos_age_mins >= 15.0 and ((p_dir == "LONG" and k5m <= -5.0 and k10m <= -8.0 and k1h <= -18.0) or (p_dir == "SHORT" and k5m >= 5.0 and k10m >= 8.0 and k1h >= 18.0)))
                broken = bool((p_dir == "LONG" and k5m < -6.0 and k6h < -18.0) or (p_dir == "SHORT" and k5m > 6.0 and k6h > 18.0))
                if inv_1h or (move_bps <= -75.0 and broken) or move_bps <= -100.0:
                    exit_reason = "CLOSED_STOPLOSS"
                    exit_exec_px = bids[0][0] if p_dir == "LONG" else asks[0][0]
                    urgent_stop = True
            if exit_reason:
                if live_mode and inst_id in live_okx_pos:
                    pos_cts = abs(float(live_okx_pos[inst_id].get("pos") or 0.0))
                    dec_sz = int(meta.get("dec_sz", 0))
                    sz_str = f"{pos_cts:.{dec_sz}f}" if dec_sz > 0 else str(int(round(pos_cts)))
                    close_side = "sell" if p_dir == "LONG" else "buy"
                    _execute_live_xperp_order(inst_id, close_side, sz_str, exit_exec_px, meta["dec_px"], reduce_only=True, urgent_stop=urgent_stop)
                realized_move_bps = max(-156.0, ((exit_exec_px - p_entry) / p_entry * 10000.0) if p_dir == "LONG" else ((p_entry - exit_exec_px) / p_entry * 10000.0))
                exit_fee_rate = 0.0005 if (live_mode and (urgent_stop or True)) else MAKER_FEE_RATE
                exit_fee_usd = round(p_notional * exit_fee_rate, 4)
                net_pnl_usd = round((p_notional * (realized_move_bps / 10000.0)) - p_efee - exit_fee_usd, 4)
                free_mgn = round(free_mgn + p_mgn + net_pnl_usd, 4)
                realized_pnl = round(realized_pnl + net_pnl_usd, 4)
                tot_fees = round(tot_fees + p_efee + exit_fee_usd, 4)
                if exit_reason == "CLOSED_PROFIT": wins_cnt += 1
                elif exit_reason == "CLOSED_SHIELD" and net_pnl_usd >= 0.0: shields_cnt += 1
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
        btc_veto_long = bool(btc_k5m <= -12.0 or btc_k1h <= -25.0)
        btc_veto_short = bool(btc_k5m >= 12.0 or btc_k1h >= 25.0)
        eff_k10m_gate = max(6.0, min(12.0, min_k10m_gate))
        boost_bonus = 15.0 if inst_id in brain_skills.get("priority_boost_inst_ids", []) else 0.0
        is_blacklisted = inst_id in brain_skills.get("blacklist_inst_ids", [])
        if not is_blacklisted and inst_id not in open_positions and inst_id not in cooldown_blocked_insts and not lifecycle["reduce_only"]:
            if allowed_dir == "LONG" and not btc_veto_long and k5m >= 4.0 and k10m >= eff_k10m_gate and sig.ofi_norm >= 0.12 and sig.vpin_toxicity <= 0.85:
                score = round((k5m * 0.8) + (k10m * 1.1) + (k1h * 0.4) + (k6h * 0.15) + (sig.ofi_norm * 18.0) + boost_bonus, 2)
                candidates.append({"inst_id": inst_id, "dir": "LONG", "score": score, "px": bids[0][0], "dec_px": meta["dec_px"]})
            elif allowed_dir == "SHORT" and not btc_veto_short and k5m <= -4.0 and k10m <= -eff_k10m_gate and sig.ofi_norm <= -0.12 and sig.vpin_toxicity <= 0.85:
                score = round((abs(k5m) * 0.8) + (abs(k10m) * 1.1) + (abs(k1h) * 0.4) + (abs(k6h) * 0.15) + (abs(sig.ofi_norm) * 18.0) + boost_bonus, 2)
                candidates.append({"inst_id": inst_id, "dir": "SHORT", "score": score, "px": asks[0][0], "dec_px": meta["dec_px"]})
        telemetry_rows.append({
            "inst_id": inst_id, "mid_price": mid, "ofi_norm": round(sig.ofi_norm, 2), "vpin_toxicity": round(sig.vpin_toxicity, 2),
            "kronos_5m_bps": round(k5m, 1), "kronos_10m_bps": round(k10m, 1), "kronos_1h_bps": round(k1h, 1),
            "kronos_2h_bps": round(k2h, 1), "kronos_6h_bps": round(k6h, 1), "kronos_12h_bps": round(k12h, 1), "kronos_24h_bps": round(k24h, 1),
            "allowed_direction": allowed_dir,
        })
    live_nav_est = round(real_nav if (live_mode and real_nav > 10.0) else (base_nav + realized_pnl + unrealized_total_usd), 2)
    portfolio_dd_pct = ((live_nav_est - base_nav) / base_nav * 100.0) if base_nav > 0 else 0.0
    circuit_breaker_tripped = bool(portfolio_dd_pct <= -8.0)
    slot_margin_usd = round(live_nav_est * SLOT_NAV_PCT, 2)
    if not circuit_breaker_tripped and len(open_positions) < MAX_SLOTS and free_mgn >= slot_margin_usd and candidates:
        candidates.sort(key=lambda x: x["score"], reverse=True)
        for cand in candidates:
            if len(open_positions) >= MAX_SLOTS or free_mgn < slot_margin_usd: break
            c_id, c_dir, c_px, c_dec = cand["inst_id"], cand["dir"], cand["px"], cand["dec_px"]
            eff_lev = float(brain_skills.get("dynamic_slot_leverage") or LEVERAGE)
            target_notional = round(slot_margin_usd * eff_lev, 2)
            sz_str, actual_notional = _calc_contract_sz(c_id, target_notional, c_px)
            actual_margin = round(actual_notional / eff_lev, 2)
            if actual_margin > free_mgn: continue
            # Anti-Cascade Free-Roll Pyramiding: max 2 unshielded slots in the same direction!
            unshielded_same_dir = sum(1 for r in open_positions.values() if r[2] == c_dir and int(r[10]) == 0)
            if unshielded_same_dir >= 2:
                continue
            tp_px = round(c_px * 1.0110, c_dec) if c_dir == "LONG" else round(c_px * 0.9890, c_dec)
            sl_px = round(c_px * 0.9895, c_dec) if c_dir == "LONG" else round(c_px * 1.0105, c_dec)
            if live_mode:
                if c_id in live_okx_pend or c_id in live_okx_pos:
                    continue
                side = "buy" if c_dir == "LONG" else "sell"
                ok = _execute_live_xperp_order(c_id, side, sz_str, c_px, c_dec, reduce_only=False, urgent_stop=False, tp_px=tp_px, sl_px=sl_px)
                if not ok: continue
                # Do NOT insert into futures_demo_positions until the post_only order actually fills on OKX (live_okx_pos)!
                live_okx_pend.add(c_id)
                free_mgn = round(free_mgn - actual_margin, 4)
                actions_taken.append({"action": f"PLACE_POST_ONLY_{c_dir}_4.0X", "inst_id": c_id, "px": c_px, "sz_contracts": sz_str, "margin_usd": actual_margin, "notional_usd": actual_notional})
                continue
            entry_fee_usd = round(actual_notional * MAKER_FEE_RATE, 4)
            pos_id = f"XPERP_{c_id.split('-')[0]}_{int(time.time()*1000)}"
            cur.execute("INSERT INTO futures_demo_positions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0, ?, 'OPEN', ?, NULL, NULL, NULL)",
                        (pos_id, c_id, c_dir, LEVERAGE, actual_margin, actual_notional, c_px, c_px, tp_px, sl_px, entry_fee_usd, now_iso))
            free_mgn = round(free_mgn - actual_margin, 4)
            locked_margin_total_usd += actual_margin
            open_positions[c_id] = (pos_id, c_id, c_dir, LEVERAGE, actual_margin, actual_notional, c_px, tp_px, sl_px, 0.0, 0, entry_fee_usd, now_iso)
            actions_taken.append({"action": f"OPEN_{c_dir}_4.0X", "inst_id": c_id, "px": c_px, "sz_contracts": sz_str, "margin_usd": actual_margin, "notional_usd": actual_notional})
    curr_nav = live_nav_est
    cur.execute("UPDATE futures_demo_account SET current_nav_usd=?, free_margin_usd=?, realized_pnl_usd=?, total_fees_usd=?, wins_count=?, stops_count=?, shield_locks_count=?, updated_at=? WHERE id=1",
                (curr_nav, round(free_mgn, 2), round(realized_pnl, 4), round(tot_fees, 4), wins_cnt, stops_cnt, shields_cnt, now_iso))
    conn.commit()
    gross_prof_live = max(0.01, realized_pnl + tot_fees) if realized_pnl > 0 else 1.0
    fee_drag_pct = round((tot_fees / gross_prof_live) * 100.0, 2) if tot_fees > 0 else 0.0
    event_trigger = bool(len(actions_taken) > 0 or abs(btc_k5m) >= 15.0 or any(abs(float(r[9])) >= 30.0 for r in open_positions.values()))
    should_audit = bool(run_audit or (event_trigger and (time.time() - _LAST_GEMINI_AUDIT_TS) >= 90.0))
    if should_audit:
        aud_res = run_gemini_ordinary_futures_audit(conn, curr_nav, telemetry_rows)
        aud_model, aud_verdict, fee_drag_pct = aud_res["model_used"], aud_res["verdict"], aud_res["fee_drag_ratio_pct"]
    cur.execute("SELECT pos_id, inst_id, direction, margin_usd, notional_usd, entry_px, current_px, tp_px, sl_px, peak_move_bps, shield_armed, opened_at FROM futures_demo_positions WHERE status='OPEN'")
    active_pos_list = [{"pos_id": r[0], "inst_id": r[1], "direction": r[2], "margin_usd": r[3], "notional_usd": r[4], "entry_px": r[5], "current_px": r[6], "tp_px": r[7], "sl_px": r[8], "peak_move_bps": round(float(r[9]), 1), "shield_armed": bool(r[10]), "opened_at": r[11]} for r in cur.fetchall()]
    snap = {
        "timestamp": now_iso, "execution_mode": "LIVE_XPERP_2.5X" if live_mode else "DEMO_2.5X", "baseline_nav_usd": base_nav,
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
    parser = argparse.ArgumentParser(description="TRE OS v14.0 — Sovereign Perpetual Futures 2.5x Isolated Engine (LIVE & DEMO)")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--demo", action="store_true", help="Force paper simulation instead of live XPERP execution")
    parser.add_argument("--interval", type=float, default=15.0)
    args = parser.parse_args()
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    live_mode = not args.demo and (os.environ.get("FUTURES_LIVE_EXECUTION", "true").lower() in ("1", "true", "yes"))
    conn = init_futures_db(os.path.join(BASE_DIR, "config", "okx_futures_demo.db"))
    micro = MicrostructureEngine(bucket_volume_usd=25000.0)
    kronos = KronosOracleClient()
    if args.once:
        s = run_futures_demo_cycle(conn, micro, kronos, run_audit=True, live_mode=live_mode)
        print(f"[FUTURES {s['execution_mode']}] NAV={s['current_nav_usd']:.2f} | Free={s['free_margin_usd']:.2f} | OpenPos={len(s['open_positions'])} | Auditor={s['auditor_model']}")
        return
    cyc = 0
    while True:
        cyc += 1
        try: run_futures_demo_cycle(conn, micro, kronos, run_audit=(cyc % 80 == 1), live_mode=live_mode)
        except Exception as e: print(f"[!] Futures Engine cycle error: {e}")
        time.sleep(max(5.0, args.interval))

if __name__ == "__main__":
    main()