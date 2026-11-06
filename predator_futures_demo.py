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
from core.word_clock import MasterWordClock
from core.luna_v35_engine import KronosAntiStaleValidator, CalibratedEVEngine, GeminiPolicySupervisor, ParallelShadowABCLedger, CapitalAllocationBook, CapitalAllocationState, REFERENCE_NAV_USDC, RESERVE_FLOOR_USDC
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
    "XAU-USD_UM_XPERP-310502":    {"spot_id": "XAU-USDC",    "coin": "XAU",    "ct_val": 0.001,  "dec_px": 1, "dec_sz": 0, "min_sz": 1.0},
    "CL-USD_UM_XPERP-310509":     {"spot_id": "CL-USDC",     "coin": "CL",     "ct_val": 0.1,    "dec_px": 2, "dec_sz": 0, "min_sz": 1.0},
}

INITIAL_CAPITAL_USDC = float(os.environ.get("INITIAL_CAPITAL_USDC", "250.0"))
STARTING_DEMO_NAV_USDC = 250.00
HISTORICAL_22OCT_SIM_NAV_USDC = float(os.environ.get("TARGET_ATH_USDC", str(round(INITIAL_CAPITAL_USDC * 1.25, 2))))
LEVERAGE = 2.0
MAKER_FEE_RATE = 0.0002  # 2 bps entry + 2 bps exit = 4 bps round-trip on notional
MAX_SLOTS = 2            # Rule R03 v25.5 (Option A Perfected): Slot #1 Pyramid G1->G2->G3 + Slot #2 ONLY when Slot #1 is in G2/G3 Free-Roll & (Decorrelated OR Early-Wave <=35m)!
SLOT_NAV_PCT = 0.18      # 18.0% of live NAV per slot (~$46 margin x 2.0x = ~$92 notional per slot: Manifesto standard)
# v35 migration guard: the legacy selector/entry executor is retained only for
# reading and safely managing pre-existing records. It must not create new
# positions; new decisions belong to the A/B/C shadow ledger until a fill-backed
# executor is promoted explicitly.
LEGACY_ENTRY_EXECUTION = False
_IO_POOL = ThreadPoolExecutor(max_workers=12)
_LEVERAGE_INITIALIZED = False
_OI_CACHE: Dict[str, Tuple[float, float]] = {}  # inst_id -> (anchor_ts, anchor_oi)
_LAST_SCANNER_TS = 0.0
_NEWS_CACHE: Dict[str, Any] = {"ts": 0.0, "headlines": [], "fear_greed": 30}

def fetch_live_breaking_news_radar() -> Dict[str, Any]:
    global _NEWS_CACHE
    if (time.time() - float(_NEWS_CACHE.get("ts") or 0.0)) < 600.0 and _NEWS_CACHE.get("headlines"):
        return _NEWS_CACHE
    ctx = _ssl_ctx()
    headlines: List[str] = []
    import xml.etree.ElementTree as ET
    rss_urls = [
        "https://news.google.com/rss/search?q=crypto+OR+binance+OR+bitcoin+OR+oil+OR+gold+when:1d&hl=en-US&gl=US&ceid=US:en",
        "https://cointelegraph.com/rss",
    ]
    for ru in rss_urls:
        try:
            req = urllib.request.Request(ru, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4, context=ctx) as r:
                root = ET.fromstring(r.read())
                for item in root.findall(".//item")[:6]:
                    t_el = item.find("title")
                    if t_el is not None and t_el.text:
                        headlines.append(t_el.text.strip()[:140])
        except Exception:
            pass
    fg_val = _NEWS_CACHE.get("fear_greed", 30)
    try:
        with urllib.request.urlopen(urllib.request.Request("https://api.alternative.me/fng/?limit=1", headers={"User-Agent": "Mozilla/5.0"}), timeout=3, context=ctx) as rf:
            fg_d = json.loads(rf.read().decode("utf-8")).get("data", [])
            if fg_d:
                fg_val = int(fg_d[0].get("value") or 30)
    except Exception:
        pass
    _NEWS_CACHE = {"ts": time.time(), "headlines": headlines[:10], "fear_greed": fg_val}
    return _NEWS_CACHE

def refresh_dynamic_xperp_universe(protected_inst_ids: set | None = None) -> None:
    """Full-Spectrum OKX Scanner: scans ALL 257 regulated XPERP contracts every 5m and ALWAYS retains active open positions."""
    global _LAST_SCANNER_TS
    prot = protected_inst_ids or set()
    missing_prot = [x for x in prot if x not in FUTURES_UNIVERSE]
    if (time.time() - _LAST_SCANNER_TS) < 150.0 and not missing_prot:
        return
    _LAST_SCANNER_TS = time.time()
    try:
        ins = _OKX_CLIENT._request("GET", "/api/v5/public/instruments?instType=FUTURES").get("data", [])
        tks = _OKX_CLIENT._request("GET", "/api/v5/market/tickers?instType=FUTURES").get("data", [])
        ins_map = {x["instId"]: x for x in ins if x.get("ruleType") == "xperp" and x.get("state") == "live"}
        # Refresh execution metadata for the static universe too. The old code
        # trusted hard-coded minSz and silently used it as lotSz, which breaks
        # 60/40 splits on contracts whose increment differs from the minimum.
        for known_iid, known_meta in FUTURES_UNIVERSE.items():
            spec = ins_map.get(known_iid)
            if not spec:
                continue
            tick_s = str(spec.get("tickSz") or "0.001")
            lot_s = str(spec.get("lotSz") or "1")
            known_meta.update({
                "ct_val": float(spec.get("ctVal") or known_meta.get("ct_val") or 1.0),
                "min_sz": float(spec.get("minSz") or known_meta.get("min_sz") or 1.0),
                "lot_sz": float(spec.get("lotSz") or known_meta.get("lot_sz") or 1.0),
                "dec_px": len(tick_s.split(".")[1].rstrip("0")) if "." in tick_s else 0,
                "dec_sz": len(lot_s.split(".")[1].rstrip("0")) if "." in lot_s else 0,
            })
        # Prune old inactive dynamic_hot contracts ONLY if they are NOT in protected_inst_ids (open positions)!
        for old_k in [k for k, v in list(FUTURES_UNIVERSE.items()) if v.get("dynamic_hot") and k not in prot]:
            del FUTURES_UNIVERSE[old_k]
        # Guarantee every open position in protected_inst_ids is registered in FUTURES_UNIVERSE!
        for pid_inst in prot:
            if pid_inst not in FUTURES_UNIVERSE and pid_inst in ins_map:
                spec = ins_map[pid_inst]
                coin = pid_inst.split("-")[0]
                tick_s = str(spec.get("tickSz") or "0.001")
                dec_px = len(tick_s.split(".")[1].rstrip("0")) if "." in tick_s else 0
                lot_s = str(spec.get("lotSz") or "1")
                dec_sz = len(lot_s.split(".")[1].rstrip("0")) if "." in lot_s else 0
                FUTURES_UNIVERSE[pid_inst] = {"spot_id": f"{coin}-USDC", "coin": coin, "ct_val": float(spec.get("ctVal") or 1.0), "dec_px": dec_px, "dec_sz": dec_sz, "min_sz": float(spec.get("minSz") or 1.0), "lot_sz": float(spec.get("lotSz") or 1.0), "dynamic_hot": True}
        hot_candidates = []
        for t in tks:
            iid = str(t.get("instId") or "")
            if iid in FUTURES_UNIVERSE or iid not in ins_map:
                continue
            coin = iid.split("-")[0]
            bid, ask, last = float(t.get("bidPx") or 0), float(t.get("askPx") or 0), float(t.get("last") or 0)
            open24 = float(t.get("open24h") or last)
            if bid <= 0 or ask <= 0 or last <= 0:
                continue
            mid = 0.5 * (bid + ask)
            sp_bps = (ask - bid) / mid * 10000.0
            vol_usd = float(t.get("volCcy24h") or 0) * mid
            ret24_bps = abs((last - open24) / open24 * 10000.0) if open24 > 0 else 0.0
            # Harmonized Dynamic XPERP Scanner (v25.7): XPERP contract ctVal scales volCcy24h; accept liquid tight-spread movers (sp <= 5.0 bps)!
            ct_v = float(ins_map[iid].get("ctVal") or 1.0)
            est_vol_usd = max(vol_usd, float(t.get("vol24h") or 0) * ct_v * mid)
            if sp_bps <= 5.0 and est_vol_usd >= 25000.0 and 45.0 <= ret24_bps <= 1600.0:
                hot_candidates.append((est_vol_usd * (1.0 + ret24_bps / 250.0), iid, coin, ins_map[iid]))
        hot_candidates.sort(key=lambda x: x[0], reverse=True)
        for _, iid, coin, spec in hot_candidates[:8]:
            tick_s = str(spec.get("tickSz") or "0.001")
            dec_px = len(tick_s.split(".")[1].rstrip("0")) if "." in tick_s else 0
            lot_s = str(spec.get("lotSz") or "1")
            dec_sz = len(lot_s.split(".")[1].rstrip("0")) if "." in lot_s else 0
            FUTURES_UNIVERSE[iid] = {
                "spot_id": f"{coin}-USDC", "coin": coin,
                "ct_val": float(spec.get("ctVal") or 1.0),
                "dec_px": dec_px, "dec_sz": dec_sz,
                "min_sz": float(spec.get("minSz") or 1.0), "lot_sz": float(spec.get("lotSz") or 1.0),
                "dynamic_hot": True,
            }
            if _OKX_CLIENT.is_authenticated:
                try:
                    _OKX_CLIENT._request("POST", "/api/v5/account/set-leverage", body_dict={"instId": iid, "lever": "2", "mgnMode": "isolated"}, auth=True)
                except Exception:
                    pass
    except Exception:
        pass

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
    try:
        _OKX_CLIENT._request("POST", "/api/v5/account/set-position-mode", body_dict={"posMode": "net_mode"}, auth=True)
    except Exception:
        pass
    for inst_id in FUTURES_UNIVERSE:
        try:
            _OKX_CLIENT._request("POST", "/api/v5/account/set-leverage", body_dict={"instId": inst_id, "lever": "2", "mgnMode": "isolated"}, auth=True)
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
    conn.execute("""CREATE TABLE IF NOT EXISTS counterfactual_audit (
        pos_id TEXT PRIMARY KEY, inst_id TEXT NOT NULL, direction TEXT NOT NULL, exit_status TEXT NOT NULL,
        entry_px REAL NOT NULL, exit_px REAL NOT NULL, realized_pnl_usd REAL NOT NULL, closed_at TEXT NOT NULL,
        px_after_60m REAL NOT NULL, move_after_60m_bps REAL NOT NULL, verdict TEXT NOT NULL, gemini_lesson TEXT NOT NULL, audited_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS shadow_filtered_signals (
        sig_id TEXT PRIMARY KEY, inst_id TEXT NOT NULL, direction TEXT NOT NULL, blocked_by TEXT NOT NULL,
        entry_px REAL NOT NULL, signal_ts TEXT NOT NULL, evaluated INTEGER NOT NULL DEFAULT 0,
        px_after_60m REAL, virtual_move_60m_bps REAL, outcome_verdict TEXT
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
    real_15m_bps, real_1h_bps, real_48h_bps = 0.0, 0.0, 0.0
    atr_1h_bps, oi_delta_bps, funding_bps = 55.0, 0.0, 0.0
    try:
        bids, asks = _OKX_CLIENT.get_orderbook(inst_id, sz=5)
        trades = _OKX_CLIENT.get_recent_trades(inst_id, limit=25)
        u_c = f"https://eea.okx.com/api/v5/market/candles?instId={inst_id}&bar=15m&limit=15"
        with urllib.request.urlopen(urllib.request.Request(u_c, headers={"User-Agent": "TRE-OS-Fut/16.0"}), timeout=5, context=ctx) as r:
            c_rows = json.loads(r.read().decode("utf-8")).get("data", [])
            if len(c_rows) >= 5:
                c_now = float(c_rows[0][4])
                # Rolling 15m Window (v26.1): if current 15m candle is < 4 mins old, use previous 15m candle open so 20s ticks never fake a 15m move!
                c0_age_ms = max(0, int(time.time() * 1000) - int(c_rows[0][0]))
                o_15m = float(c_rows[1][1]) if (c0_age_ms < 240000 and len(c_rows) > 1) else float(c_rows[0][1])
                c_1h = float(c_rows[4][4])
                real_15m_bps = ((c_now - o_15m) / o_15m * 10000.0) if o_15m > 0 else 0.0
                real_1h_bps = ((c_now - c_1h) / c_1h * 10000.0) if c_1h > 0 else 0.0
                ranges = [((float(x[2]) - float(x[3])) / max(1e-9, float(x[3])) * 10000.0) for x in c_rows[:4]]
                atr_1h_bps = max(25.0, min(140.0, (sum(ranges) / len(ranges)) * 2.0))
                # Tools #1, #2, #3, #4: 15m Volume, Wick Rejection, 1h VWAP, and 1h CVD
                vol_15m_usd = max(float(c_rows[0][7] or 0.0), float(c_rows[1][7] or 0.0))
                # Tool #3 Harmonized (v26.5): evaluate rejection wicks on the active/last 15m candle (not across 60m history)!
                wc_row = c_rows[1] if (c0_age_ms < 180000 and len(c_rows) > 1) else c_rows[0]
                w_o, w_h, w_l, w_c = float(wc_row[1]), float(wc_row[2]), float(wc_row[3]), float(wc_row[4])
                rng_15m = max(1e-9, w_h - w_l)
                upper_wick_bps = (w_h - max(w_o, w_c)) / max(1e-9, w_c) * 10000.0
                lower_wick_bps = (min(w_o, w_c) - w_l) / max(1e-9, w_c) * 10000.0
                upper_wick_reject = bool(upper_wick_bps >= 38.0 and ((w_h - max(w_o, w_c)) / rng_15m) >= 0.52)
                lower_wick_reject = bool(lower_wick_bps >= 38.0 and ((min(w_o, w_c) - w_l) / rng_15m) >= 0.52)
                ct_v_c = float(FUTURES_UNIVERSE.get(inst_id, {}).get("ct_val", 1.0))
                c_vols_usd = [max(float(x[7] or 0.0), float(x[6] or 0.0) * float(x[4] or 0.0), float(x[5] or 0.0) * ct_v_c * float(x[4] or 0.0)) for x in c_rows[:4]]
                tot_v1h = sum(c_vols_usd)
                vwap_1h = (sum(((float(c_rows[i][2]) + float(c_rows[i][3]) + float(c_rows[i][4])) / 3.0) * c_vols_usd[i] for i in range(min(4, len(c_rows)))) / tot_v1h) if tot_v1h > 0 else c_now
                cvd_1h = (sum((c_vols_usd[i] if float(c_rows[i][4]) >= float(c_rows[i][1]) else -c_vols_usd[i]) for i in range(min(4, len(c_rows)))) / tot_v1h) if tot_v1h > 0 else 0.0
                # Encode quality score into funding_bps if no external funding: negative (-999) when trap detected!
                # Tool #8 (RSI-14 Overbought >= 73 / Oversold <= 27 Guard):
                gains, losses = [], []
                for idx_r in range(min(14, len(c_rows) - 1)):
                    diff_r = float(c_rows[idx_r][4]) - float(c_rows[idx_r + 1][4])
                    gains.append(max(0.0, diff_r))
                    losses.append(max(0.0, -diff_r))
                avg_g = (sum(gains) / max(1, len(gains))) if gains else 0.0
                avg_l = (sum(losses) / max(1, len(losses))) if losses else 1e-9
                rsi_15m = 100.0 - (100.0 / (1.0 + (avg_g / max(1e-9, avg_l))))
                is_dyn = bool(FUTURES_UNIVERSE.get(inst_id, {}).get("dynamic_hot", False))
                ct_v_b = float(FUTURES_UNIVERSE.get(inst_id, {}).get("ct_val", 1.0))
                top2_bid_usd = sum(float(x[0]) * float(x[1]) * ct_v_b for x in bids[:2]) if bids else 0.0
                top2_ask_usd = sum(float(x[0]) * float(x[1]) * ct_v_b for x in asks[:2]) if asks else 0.0
                bull_trap, bear_trap = 0.0, 0.0
                if (is_dyn and tot_v1h < 5000.0) or min(top2_bid_usd, top2_ask_usd) < 75.0:
                    bull_trap, bear_trap = -991.0, 991.0  # Tool #2 & #4: Low 1h Vol or Thin Top-2 L2 Book (<$75 like SNDK $63) blocks BOTH!
                if upper_wick_reject:
                    bull_trap = -993.0  # Tool #3: Upper Wick rejection blocks LONG
                elif rsi_15m >= 73.0:
                    bull_trap = -998.0  # Tool #8: RSI-14 >= 73 Overbought blocks LONG
                elif c_now < vwap_1h * 0.997 and cvd_1h < -0.25:
                    bull_trap = -994.0  # Tool #4: Below 1h VWAP + negative CVD blocks LONG
                if lower_wick_reject:
                    bear_trap = 993.0   # Tool #3: Lower Wick rejection blocks SHORT (never overwritten by bull_trap!)
                elif rsi_15m <= 27.0:
                    bear_trap = 998.0   # Tool #8: RSI-14 <= 27 Oversold blocks SHORT
                elif c_now > vwap_1h * 1.003 and cvd_1h > 0.25:
                    bear_trap = 994.0   # Tool #4: Above 1h VWAP + positive CVD blocks SHORT
        u_4h = f"https://eea.okx.com/api/v5/market/candles?instId={inst_id}&bar=4H&limit=13"
        with urllib.request.urlopen(urllib.request.Request(u_4h, headers={"User-Agent": "TRE-OS-Fut/16.0"}), timeout=4, context=ctx) as r4:
            c4 = json.loads(r4.read().decode("utf-8")).get("data", [])
            if len(c4) >= 12:
                c_now4 = float(c4[0][4])
                c_48h = float(c4[-1][4])
                real_48h_bps = ((c_now4 - c_48h) / c_48h * 10000.0) if c_48h > 0 else 0.0
                hi_24h = max(float(x[2]) for x in c4[:6])
                lo_24h = min(float(x[3]) for x in c4[:6])
                # Tool #7 (Anti-Bottom-Shorting Guard v26.3): block SHORT in bottom 18% ONLY if bouncing (higher low, lower wick >=22bps, or RSI<=31) — never block clean breakdowns!
                if hi_24h > lo_24h and ((c_now4 - lo_24h) / (hi_24h - lo_24h)) <= 0.18 and (float(c4[0][3]) >= float(c4[1][3]) or lower_wick_bps >= 22.0 or rsi_15m <= 31.0):
                    bear_trap = 997.0   # Tool #7: Bottom 18% bounce/exhaustion blocks SHORT!
                # Tool #1 (24h Post-Pump Bleed Detector v26.4): block LONG only while 15m/1h are still negative/bleeding — never block a confirmed 15m+1h reversal!
                if hi_24h > lo_24h and ((hi_24h - c_now4) / (hi_24h - lo_24h)) >= 0.45 and float(c4[0][2]) < float(c4[1][2]) and (real_1h_bps < 6.0 and real_15m_bps < 0.0):
                    bull_trap = -999.0  # Tool #1: 24h Post-Pump Bleed blocks LONG only when BOTH 1h and 15m are bleeding!
        # Combine independent bull_trap & bear_trap: 9999.0 blocks BOTH LONG and SHORT!
        if bull_trap < -900.0 and bear_trap > 900.0:
            funding_bps = 9999.0
        elif bear_trap > 900.0:
            funding_bps = bear_trap
        elif bull_trap < -900.0:
            funding_bps = bull_trap
        u_oi = f"https://eea.okx.com/api/v5/public/open-interest?instType=FUTURES&instId={inst_id}"
        with urllib.request.urlopen(urllib.request.Request(u_oi, headers={"User-Agent": "TRE-OS-Fut/16.0"}), timeout=3, context=ctx) as roi:
            oi_d = json.loads(roi.read().decode("utf-8")).get("data", [])
            if oi_d:
                cur_oi = float(oi_d[0].get("oi") or 0.0)
                now_t = time.time()
                prev_ts, prev_oi = _OI_CACHE.get(inst_id, (now_t, cur_oi))
                oi_delta_bps = ((cur_oi - prev_oi) / prev_oi * 10000.0) if prev_oi > 0 else 0.0
                if (now_t - prev_ts) >= 900.0 or inst_id not in _OI_CACHE:
                    _OI_CACHE[inst_id] = (now_t, cur_oi)
    except Exception:
        pass
    return inst_id, bids, asks, trades, real_15m_bps, real_1h_bps, real_48h_bps, atr_1h_bps, oi_delta_bps, funding_bps
_KRONOS_VALIDATOR = KronosAntiStaleValidator()
_EV_ENGINE = CalibratedEVEngine()
_POLICY_SUPERVISOR = GeminiPolicySupervisor()
_EV_ENGINE_CALIBRATED = False
_LAST_GEMINI_AUDIT_TS = 0.0
_GEMINI_LITE_429_UNTIL = 0.0
_PRE_TRADE_CONFIRM_MAP: Dict[str, Tuple[str, int, float]] = {}  # inst_id -> (dir, consecutive_cycles, first_px)

def load_gemini_brain_skills() -> Dict[str, Any]:
    p = os.path.join(BASE_DIR, "config", "gemini_brain_skills.json")
    default_skills = {
        "min_kronos_10m_bps": 7.5,
        "fast_shield_bps": 20.0,
        "trail_lock_ratio": 0.65,
        "dynamic_slot_leverage": 2.0,
        "force_close_inst_ids": [],
        "priority_boost_inst_ids": [],
        "blacklist_inst_ids": [],
        "gemini_sniper_entries": [],
        "strategy_mode": "TREND_SWING_RUNNER",
        "self_critique": "Inizializzazione memoria episodica agentica h24.",
        "outlook_1h": "Tattica 1h: attendere conferma OFI >= +0.18 sui leader rialzisti evitando micro-rumore.",
        "outlook_6h": "Sessione 6h: focus su recupero graduale con max 1 slot scoperto alla volta a leva 2.0x Anti-Wick.",
        "outlook_12h": "Swing 12h: cavalcare i runner sopra +35 bps col pavimento break-even a +12 bps fino a +135 bps.",
        "outlook_48h": "Macro 48h: riportare il NAV da $1000.00 sopra $1050.00 e poi verso la baseline storica di $1250.00.",
        "learned_rules": [
            "TOOL 1 (OI & Squeeze): cavalcare SQUEEZE_LONG/SQUEEZE_SHORT quando Open Interest sale insieme a candela reale e OFI.",
            "TOOL 2 (ATR Scaling): rispettare i target TP/Shield/SL scalati sull'ATR 1h specifico di ogni moneta (0.68x BTC .. 1.25x Alt).",
            "TOOL 3 (Hot Scanner 257 XPERP): sfruttare i top mover dinamici con spread <= 4.5 bps scoperti dallo scanner.",
            "TOOL 4 (Hardware Break-Even Amend): appena armato lo scudo, amend-algos sposta lo stop fisico nei server OKX a +12 bps.",
            "LIMITE AUREO: max 1 solo slot scoperto alla volta a leva 1.8x-2.0x Anti-Wick, mai shortare candele verdi 15m/1h."
        ],
        "verdict": "TRE OS v16.0 Derivative Alpha & Hardware Break-Even Agent active.",
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
    # Stamp timestamp immediately so a 429 never causes a 15-second retry storm!
    _LAST_GEMINI_AUDIT_TS = time.time()
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
    cur.execute("SELECT inst_id, direction, realized_pnl_usd, status, closed_at, peak_move_bps, shield_armed, notional_usd, opened_at FROM futures_demo_positions WHERE status != 'OPEN' ORDER BY closed_at DESC LIMIT 15")
    raw_closed_15 = cur.fetchall()
    recent_closed_info = [{"inst_id": r[0], "dir": r[1], "pnl_usd": round(float(r[2] or 0), 2), "status": r[3], "closed": r[4], "peak_bps": round(float(r[5] or 0), 1), "tier": f"G{r[6]}", "notional_usd": r[7]} for r in raw_closed_15[:10]]
    win_pnls = [float(r[2]) for r in raw_closed_15 if float(r[2] or 0) > 0]
    loss_pnls = [abs(float(r[2])) for r in raw_closed_15 if float(r[2] or 0) < 0]
    avg_win_15 = round(sum(win_pnls) / len(win_pnls), 2) if win_pnls else 0.0
    avg_loss_15 = round(sum(loss_pnls) / len(loss_pnls), 2) if loss_pnls else 0.01
    payoff_ratio_15 = round(avg_win_15 / max(0.01, avg_loss_15), 2)
    doa_cnt_15 = sum(1 for r in raw_closed_15 if float(r[5] or 0) < 15.0 and float(r[2] or 0) < 0)
    choked_cnt_15 = sum(1 for r in raw_closed_15 if float(r[5] or 0) >= 50.0 and 0.0 <= float(r[2] or 0) < 0.45)
    general_and_particular_diag = {
        "GENERAL_SYSTEM_HEALTH": {
            "last15_avg_win_usd": avg_win_15,
            "last15_avg_loss_usd": avg_loss_15,
            "payoff_ratio_win_over_loss": payoff_ratio_15,
            "payoff_alert": ("CRITICAL_INVERTED_PAYOFF: wins smaller than losses!" if payoff_ratio_15 < 1.2 else "HEALTHY_ASYMMETRY"),
            "phase0_dead_on_arrival_count_last15": doa_cnt_15,
            "choked_small_wins_count_last15": choked_cnt_15,
        },
        "PARTICULAR_LAST_TRADE_AUTOPSY": (recent_closed_info[0] if recent_closed_info else {}),
        "PARTICULAR_OPEN_POSITIONS_LIVE": open_pos_info,
    }
    cur.execute("SELECT inst_id, COUNT(*), SUM(CASE WHEN realized_pnl_usd > 0 THEN 1 ELSE 0 END), ROUND(SUM(realized_pnl_usd), 3) FROM futures_demo_positions WHERE status != 'OPEN' GROUP BY inst_id")
    coin_scoreboard = [{"inst_id": r[0], "trades": r[1], "wins": r[2], "net_pnl": r[3]} for r in cur.fetchall()]
    prev_memory = {
        "prev_updated_at": default_audit.get("updated_at"),
        "prev_outlook_1h": default_audit.get("outlook_1h"),
        "prev_outlook_6h": default_audit.get("outlook_6h"),
        "prev_outlook_12h": default_audit.get("outlook_12h"),
        "prev_outlook_48h": default_audit.get("outlook_48h"),
        "prev_sniper": default_audit.get("gemini_sniper_entries"),
        "learned_rules": default_audit.get("learned_rules", []),
    }
    news_radar = fetch_live_breaking_news_radar()
    pb_path = os.path.join(BASE_DIR, "config", "trap_simulation_playbook.json")
    pb_summary = "30d Backtest: CRYPTO=+$1138 (93% of profit), COMMODITY=+$52, US_EQUITY=+$29. Focus priority_boost & gemini_sniper_entries on CRYPTO_NEURAL; never boost US_EQUITY outside 14:30-20:30 UTC or COMMODITY at night!"
    if os.path.exists(pb_path):
        try:
            pb_d = json.load(open(pb_path, encoding="utf-8"))
            s30 = pb_d.get("sim_30d_results", {}).get("new_v28_1", {})
            pb_summary = f"SIMULAZIONE 30GG REALE: WinRate={s30.get('win_rate_pct')}% | UtilePerClasse={json.dumps(s30.get('by_asset_class_usd', {}))}. REGOLA PER GEMINI: il 93% dei profitti viene da CRYPTO; assegna priority_boost_inst_ids e gemini_sniper_entries alle CRYPTO in trend con Kronos Accelerato, MAI ad Azioni USA fuori orario (14:30-20:30 UTC) o Commodity dopo uno stop!"
        except Exception:
            pass
    idle_mins = 0.0
    if not open_pos_info and recent_closed_info and recent_closed_info[0].get("closed"):
        try:
            idle_mins = round((datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(str(recent_closed_info[0]["closed"]).replace("Z", "+00:00"))).total_seconds() / 60.0, 1)
        except Exception:
            idle_mins = 0.0
    dyn_hot_cnt = sum(1 for v in FUTURES_UNIVERSE.values() if v.get("dynamic_hot"))
    compact_t = [{"id": t["inst_id"], "dir": t["allowed_direction"], "ofi": t["ofi_norm"], "vpin": t["vpin_toxicity"], "oi_d": t.get("oi_delta_bps", 0.0), "atr": t.get("atr_1h_bps", 55.0), "sqz": t.get("squeeze_regime", "NONE"), "r1h": t.get("real_1h_bps", 0.0), "k1h": t["kronos_1h_bps"], "k6h": t["kronos_6h_bps"], "k12h": t["kronos_12h_bps"], "k48h": t.get("kronos_48h_bps", 0.0)} for t in telemetry]
    prompt = (
        f"PLAYBOOK 30GG & TRAPPOLE v28.2: {pb_summary} | STATO STALLO: IdleDroughtMins={idle_mins}m, DynamicHotCoins={dyn_hot_cnt}, TotalUniverse={len(FUTURES_UNIVERSE)}. SE IdleDroughtMins >= 25.0 E OpenPositions è vuoto, SVUOTA blacklist_inst_ids, ABBASSA min_kronos_10m_bps a 4.5 E INSERISCI LA MIGLIORE CRYPTO IN TREND DENTRO gemini_sniper_entries E priority_boost_inst_ids! "
        "Sei l'Agente Strategico Unificato di TRE OS v32.0 (in perfetta armonia con Lehman quant-node sul Mac e con config/unified_mission_and_guarantees.json). "
        f"LIVE NEWS & MACRO (Fear&Greed={news_radar.get('fear_greed')}): {json.dumps(news_radar.get('headlines', []))}. "
        "ARCHITETTURA E 12 GARANZIE INVALICABILI TRE OS v32.0: "
        f"- Capitale Attuale Conto Trading: ${nav_usd:.2f} USDC (Target 1 Cutover: $1050.00 [mancano ${max(0.0, 1050.00 - nav_usd):.2f}$] | Target 2 ATH: $1250.00 [mancano ${max(0.0, 1250.00 - nav_usd):.2f}$]). "
        "- G01 (Asimmetria Volumi >=3:1): Fase 0 entra come Sonda Agile (~$60 USDC, SL max -38bps = -$0.23, taglio tesi rotta a 6m/8m = -$0.12); Fase 1 (+36bps) blinda il Pareggio (+8bps) senza chiudere in piccolo utile; Fase 2 (+56bps) triplica il volume a ~$190 USDC (Leva 3x Free-Roll) e Fase 3 (+135bps) sale a ~$330 USDC per incassare +$0.80..+$3.50 USDC! "
        "- G02/G03/G04 (Analisi Prima, Durante e Dopo): zero riaperture automatiche nello stesso ciclo di una chiusura; pausa obbligatoria 6m (dopo vincita) / 15m (dopo stop); conferma pre-trade su 2 cicli consecutivi; verifica continua della tesi durante il trade. "
        f"- Bilancio Attuale: RealizedPnL={realized_pnl:+.4f}, Fees={tot_fees:.4f} (FeeDrag={fee_drag_pct:.1f}%), Shields={shields}, Stops={stops}. "
        f"- LA TUA MEMORIA EPISODICA PRECEDENTE: {json.dumps(prev_memory)}. "
        f"- DIAGNOSI GENERALE E PARTICOLARE DEL SISTEMA (OBBLIGATORIO ANALIZZARE PRIMA/DURANTE/DOPO): {json.dumps(general_and_particular_diag)}. ScoreboardPerMoneta={json.dumps(coin_scoreboard)}. RecentClosed={json.dumps(recent_closed_info)}. "
        f"- Telemetria Multi-Orizzonte (1h, 6h, 12h, 48h): {json.dumps(compact_t)}. "
        "COMPITO AGENTICO H24 (Rispondi SOLO JSON in italiano): "
        "0) ZAVA-OKX-SKILL HUB ATTIVO (76 Skills: 10 Ufficiali v1.5.0 + 63 Marketplace + 3 EEA/TRE OS): applica i 3 pilastri di kline-indicator (Macro Cycle x Volume-Price WorldQuant x Derivatives OI/Funding), okx-maker-entry (esecuzione Maker limit per abbattere il fee-drag), position-sizer (controllo ATR e distanza liquidazione), tri-asset-adaptive-fusion (correlazione XAU/BTC/ETH), bb-momentum-breakout (Squeeze + MACD) e hindsight-reviewer (analisi controfattuale post-trade); "
        "1) self_critique: auto-analisi controfattuale (hindsight-reviewer & okx-trade-review-suite) su cosa ha funzionato o fallito nelle scelte precedenti; "
        "2) Prospettive Multi-Orizzonte: outlook_1h (piano tattico prossima 1h), outlook_6h (piano sessione 6h), outlook_12h (piano swing 12h), outlook_48h (strategia macro 48h per recuperare i $1050.00 e puntare a $1250.00); "
        "3) learned_rules: fino a 5 regole operative auto-apprese; "
        "4) CAMBIO AUTOMATICO DI STRATEGIA (strategy_mode): se vedi che gli ultimi trade stanno perdendo o facendo micro-profitti mangiati dalle fee, DEVI CAMBIARE STRATEGIA scegliendo tra: (a) 'TREND_SWING_RUNNER' (entra sui trend netti 7-orizzonti e tiene per +52..+160bps), (b) 'SNIPER_PULLBACK_LIMIT' (entra solo con ordini limit scontati di -25bps sotto il prezzo per comprare gli spike invece di farsi stoppare dagli spike!), (c) 'CRISIS_RECOVERY_FORTRESS' (opera solo sulle Top 3 monete vincenti dello ScoreboardPerMoneta con SQUEEZE attivo). "
        "5) Controlli operativi: strategy_mode, force_close_inst_ids, priority_boost_inst_ids, blacklist_inst_ids (max 3), gemini_sniper_entries (max 1 {inst_id, dir}), min_kronos_10m_bps [5.0..11.0], fast_shield_bps [38.0..55.0], trail_lock_ratio [0.72..0.85], dynamic_slot_leverage [1.8..2.0], verdict."
    )
    global _GEMINI_LITE_429_UNTIL
    g_models = ("gemma-4-26b-a4b-it",) if time.time() < _GEMINI_LITE_429_UNTIL else ("gemini-3.5-flash-lite", "gemma-4-26b-a4b-it")
    for g_mod in g_models:
        try:
            u = f"https://generativelanguage.googleapis.com/v1beta/models/{g_mod}:generateContent"
            gen_cfg = {"temperature": 0.15} if "gemma" in g_mod else {"temperature": 0.15, "responseMimeType": "application/json"}
            payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen_cfg}
            req = urllib.request.Request(u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", ("x-goog-" + "api-key"): gemini_key})
            with urllib.request.urlopen(req, timeout=14, context=_ssl_ctx()) as resp:
                d = json.loads(resp.read().decode("utf-8"))
                txt = (d.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")).strip()
                if txt and "{" in txt:
                    s_i, e_i = txt.find("{"), txt.rfind("}")
                    p = json.loads(txt[s_i:e_i+1])
                    res = {
                        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "model_used": f"google-free:{g_mod}", "fee_drag_ratio_pct": fee_drag_pct,
                        "min_kronos_10m_bps": (4.5 if idle_mins >= 25.0 else round(max(4.5, min(11.0, float(p.get("min_kronos_10m_bps") or 6.5))), 1)),
                        "fast_shield_bps": round(max(38.0, min(58.0, float(p.get("fast_shield_bps") or 52.0))), 1),
                        "trail_lock_ratio": round(max(0.58, min(0.85, float(p.get("trail_lock_ratio") or 0.65))), 2),
                        "dynamic_slot_leverage": round(max(1.5, min(2.0, float(p.get("dynamic_slot_leverage") or 2.0))), 1),
                        "force_close_inst_ids": [str(x) for x in (p.get("force_close_inst_ids") or []) if isinstance(x, str)],
                        "priority_boost_inst_ids": [str(x) for x in (p.get("priority_boost_inst_ids") or []) if isinstance(x, str)][:3],
                        "blacklist_inst_ids": [str(x) for x in (p.get("blacklist_inst_ids") or []) if isinstance(x, str)][:3],
                        "gemini_sniper_entries": [x for x in (p.get("gemini_sniper_entries") or []) if isinstance(x, dict) and x.get("inst_id") in FUTURES_UNIVERSE and x.get("dir") in ("LONG", "SHORT")][:1],
                        "strategy_mode": str(p.get("strategy_mode") if p.get("strategy_mode") in ("TREND_SWING_RUNNER", "SNIPER_PULLBACK_LIMIT", "CRISIS_RECOVERY_FORTRESS") else default_audit.get("strategy_mode", "TREND_SWING_RUNNER")),
                        "self_critique": str(p.get("self_critique") or default_audit.get("self_critique", ""))[:280],
                        "outlook_1h": str(p.get("outlook_1h") or default_audit.get("outlook_1h", ""))[:260],
                        "outlook_6h": str(p.get("outlook_6h") or default_audit.get("outlook_6h", ""))[:260],
                        "outlook_12h": str(p.get("outlook_12h") or default_audit.get("outlook_12h", ""))[:260],
                        "outlook_48h": str(p.get("outlook_48h") or default_audit.get("outlook_48h", ""))[:260],
                        "learned_rules": [str(x) for x in (p.get("learned_rules") or default_audit.get("learned_rules", [])) if isinstance(x, str)][:5],
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
        except Exception as e_g:
            if g_mod == "gemini-3.5-flash-lite" and "429" in str(e_g):
                _GEMINI_LITE_429_UNTIL = time.time() + 3600.0  # Cool down 60m on 429 so zero 429 errors accumulate!
            continue
    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    if or_key:
        try:
            or_payload = {
                "model": "nvidia/llama-3.3-nemotron-super-49b-v1:free",
                "models": ["nvidia/llama-3.3-nemotron-super-49b-v1:free", "google/gemma-3-27b-it:free", "openrouter/free"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.15,
                "response_format": {"type": "json_object"},
            }
            req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(or_payload).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": f"Bearer {or_key}"})
            with urllib.request.urlopen(req, timeout=12, context=_ssl_ctx()) as resp:
                d = json.loads(resp.read().decode("utf-8"))
                txt = (d.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()
                if txt and "{" in txt:
                    s_idx, e_idx = txt.find("{"), txt.rfind("}")
                    p = json.loads(txt[s_idx:e_idx+1])
                    used_m = d.get("model", "openrouter/free")
                    res = {
                        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "model_used": f"openrouter-free:{used_m}", "fee_drag_ratio_pct": fee_drag_pct,
                        "min_kronos_10m_bps": round(max(6.0, min(12.0, float(p.get("min_kronos_10m_bps") or 7.5))), 1),
                        "fast_shield_bps": round(max(38.0, min(58.0, float(p.get("fast_shield_bps") or 52.0))), 1),
                        "trail_lock_ratio": round(max(0.58, min(0.85, float(p.get("trail_lock_ratio") or 0.65))), 2),
                        "dynamic_slot_leverage": round(max(1.5, min(2.0, float(p.get("dynamic_slot_leverage") or 2.0))), 1),
                        "force_close_inst_ids": [str(x) for x in (p.get("force_close_inst_ids") or []) if isinstance(x, str)],
                        "priority_boost_inst_ids": [str(x) for x in (p.get("priority_boost_inst_ids") or []) if isinstance(x, str)][:3],
                        "blacklist_inst_ids": [str(x) for x in (p.get("blacklist_inst_ids") or []) if isinstance(x, str)][:3],
                        "gemini_sniper_entries": [x for x in (p.get("gemini_sniper_entries") or []) if isinstance(x, dict) and x.get("inst_id") in FUTURES_UNIVERSE and x.get("dir") in ("LONG", "SHORT")][:1],
                        "strategy_mode": str(p.get("strategy_mode") if p.get("strategy_mode") in ("TREND_SWING_RUNNER", "SNIPER_PULLBACK_LIMIT", "CRISIS_RECOVERY_FORTRESS") else default_audit.get("strategy_mode", "TREND_SWING_RUNNER")),
                        "self_critique": str(p.get("self_critique") or default_audit.get("self_critique", ""))[:280],
                        "outlook_1h": str(p.get("outlook_1h") or default_audit.get("outlook_1h", ""))[:260],
                        "outlook_6h": str(p.get("outlook_6h") or default_audit.get("outlook_6h", ""))[:260],
                        "outlook_12h": str(p.get("outlook_12h") or default_audit.get("outlook_12h", ""))[:260],
                        "outlook_48h": str(p.get("outlook_48h") or default_audit.get("outlook_48h", ""))[:260],
                        "learned_rules": [str(x) for x in (p.get("learned_rules") or default_audit.get("learned_rules", [])) if isinstance(x, str)][:5],
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
            pass
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

def _amend_okx_hardware_sl_to_breakeven(inst_id: str, p_dir: str, p_entry: float, lock_bps: float, dec_px: int, new_sz_str: str = "") -> bool:
    """Impl #4 (OCO Integrity Watchdog): updates hardware SL trigger price AND scaled contract size on OKX."""
    if not _OKX_CLIENT.is_authenticated:
        return False
    new_sl = round(p_entry * (1.0 + lock_bps / 10000.0), dec_px) if p_dir == "LONG" else round(p_entry * (1.0 - lock_bps / 10000.0), dec_px)
    new_sl_str = f"{new_sl:.{dec_px}f}"
    for otype in ("oco", "conditional"):
        try:
            algos = _OKX_CLIENT._request("GET", f"/api/v5/trade/orders-algo-pending?instType=FUTURES&ordType={otype}&instId={inst_id}", auth=True).get("data", [])
            for a in algos:
                aid = a.get("algoId")
                if aid:
                    b_dict: Dict[str, Any] = {"instId": inst_id, "algoId": aid, "newSlTriggerPx": new_sl_str}
                    if new_sz_str:
                        b_dict["newSz"] = new_sz_str
                    r = _OKX_CLIENT._request("POST", "/api/v5/trade/amend-algos", body_dict=b_dict, auth=True)
                    if str((r.get("data") or [{}])[0].get("sCode", "")) == "0":
                        return True
        except Exception:
            pass
    return False

def _execute_live_xperp_order(inst_id: str, side: str, sz_str: str, px: float, dec_px: int, reduce_only: bool = False, urgent_stop: bool = False, tp_px: float = 0.0, sl_px: float = 0.0) -> bool:
    if not _OKX_CLIENT.is_authenticated:
        return False
    px_str = f"{px:.{dec_px}f}"
    # TRE OS v28.0 Maker-First Execution: use post_only (2bps) even on reduceOnly Chandelier profit exits;
    # only use market (5bps) on genuine urgent_stop or if post_only close doesn't fill within 1.2s!
    body: Dict[str, Any] = {
        "instId": inst_id,
        "tdMode": "isolated",
        "side": side,
        "ordType": "market" if urgent_stop else "post_only",
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
            "tpOrdPx": f"{tp_px:.{dec_px}f}",
            "tpTriggerPxType": "last",
            "slTriggerPx": f"{sl_px:.{dec_px}f}",
            "slOrdPx": "-1",
            "slTriggerPxType": "last",
        }]
    try:
        r = _OKX_CLIENT._request("POST", "/api/v5/trade/order", body_dict=body, auth=True)
        d = (r.get("data") or [{}])[0]
        if str(d.get("sCode", "")) == "51000":
            body["posSide"] = ("long" if ((side == "buy" and not reduce_only) or (side == "sell" and reduce_only)) else "short")
            r = _OKX_CLIENT._request("POST", "/api/v5/trade/order", body_dict=body, auth=True)
            d = (r.get("data") or [{}])[0]
        if str(d.get("sCode", "")) == "0":
            ord_id = str(d.get("ordId") or "")
            # Audit Fix #1: if closing a position (reduce_only=True) via post_only, verify it actually filled within 1.2s;
            # if still pending or cancelled by post_only cross, cancel and close at market so NO ghost position ever remains open!
            if reduce_only and body.get("ordType") == "post_only" and ord_id:
                time.sleep(1.2)
                chk = _OKX_CLIENT._request("GET", f"/api/v5/trade/order?instId={inst_id}&ordId={ord_id}", auth=True).get("data", [])
                st_o = str((chk[0] if chk else {}).get("state", ""))
                if st_o == "filled":
                    return True
                if st_o in ("live", "partially_filled"):
                    _OKX_CLIENT._request("POST", "/api/v5/trade/cancel-order", body_dict={"instId": inst_id, "ordId": ord_id}, auth=True)
                body["ordType"] = "market"
                body.pop("px", None)
                rm = _OKX_CLIENT._request("POST", "/api/v5/trade/order", body_dict=body, auth=True)
                return str(((rm.get("data") or [{}])[0]).get("sCode", "")) == "0"
            return True
        if reduce_only and body.get("ordType") == "post_only":
            body["ordType"] = "market"
            body.pop("px", None)
            rm = _OKX_CLIENT._request("POST", "/api/v5/trade/order", body_dict=body, auth=True)
            return str(((rm.get("data") or [{}])[0]).get("sCode", "")) == "0"
    except Exception:
        pass
    return False
def run_futures_demo_cycle(conn: sqlite3.Connection, micro_engine: MicrostructureEngine, kronos_client: KronosOracleClient, run_audit: bool = False, live_mode: bool = True) -> Dict[str, Any]:
    global _EV_ENGINE_CALIBRATED
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    real_nav, real_free, live_okx_pos, live_okx_pend = _sync_live_okx_account_and_cancel_stale(live_mode)
    if _EV_ENGINE.n_obs_bucket < 100:
        _EV_ENGINE.fit_from_sqlite(conn, min_obs=100)
    cur_init = conn.cursor()
    cur_init.execute("SELECT inst_id FROM futures_demo_positions WHERE status='OPEN'")
    prot_set = {str(r[0]) for r in cur_init.fetchall()} | set(live_okx_pos.keys()) | set(live_okx_pend)
    refresh_dynamic_xperp_universe(protected_inst_ids=prot_set)
    ensure_isolated_leverage(live_mode)
    lifecycle = evaluate_run_lifecycle()
    # TRE OS v29.1 False-Negative Fix #2: pass spot_id for the 14 Spot-USDC cryptos and the exact XPERP inst_id for all other contracts so ZERO coins get 0.0 Kronos!
    spot_usdc_coins = {"BTC","ETH","SOL","HYPE","ZEC","XRP","NEAR","LINK","SUI","BNB","AVAX","UNI","TAO","WLD"}
    kronos_query_ids = [(m["spot_id"] if iid.split("-")[0] in spot_usdc_coins else iid) for iid, m in FUTURES_UNIVERSE.items()]
    kronos_map = kronos_client.fetch_forecasts(kronos_query_ids)
    cur = conn.cursor()
    cur.execute("SELECT baseline_nav_usd, current_nav_usd, free_margin_usd, realized_pnl_usd, total_fees_usd, wins_count, stops_count, shield_locks_count, started_at FROM futures_demo_account WHERE id=1")
    acct = cur.fetchone()
    base_nav, curr_nav, free_mgn, realized_pnl, tot_fees, wins_cnt, stops_cnt, shields_cnt, started_at = float(acct[0]), float(acct[1]), float(acct[2]), float(acct[3]), float(acct[4]), int(acct[5]), int(acct[6]), int(acct[7]), str(acct[8])
    if not _EV_ENGINE_CALIBRATED:
        _EV_ENGINE.fit_from_sqlite(conn, min_obs=100)
        _EV_ENGINE_CALIBRATED = True
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
    okx_recent_ReduceOnly_map: Dict[str, Dict[str, Any]] = {}
    if live_mode and _OKX_CLIENT.is_authenticated:
        try:
            h_sync = _OKX_CLIENT._request("GET", "/api/v5/trade/orders-history?instType=FUTURES&limit=40", auth=True).get("data", [])
            for ho in h_sync:
                if ho.get("state") == "filled" and str(ho.get("reduceOnly", "")).lower() == "true":
                    hiid = str(ho.get("instId") or "")
                    if hiid and hiid not in okx_recent_ReduceOnly_map:
                        okx_recent_ReduceOnly_map[hiid] = ho
        except Exception:
            pass
    if live_mode:
        for db_inst, db_row in list(open_positions.items()):
            if db_inst not in live_okx_pos:
                ro_ord = okx_recent_ReduceOnly_map.get(db_inst, {})
                ro_pnl = float(ro_ord.get("pnl") or 0.0) + float(ro_ord.get("fee") or 0.0) - float(db_row[11] or 0.0)
                ro_px = float(ro_ord.get("avgPx") or db_row[6] or 0.0)
                ro_st = "CLOSED_SHIELD" if ro_pnl >= -0.18 else "CLOSED_STOPLOSS"
                cur.execute("UPDATE futures_demo_positions SET status=?, closed_at=?, exit_px=?, realized_pnl_usd=?, current_px=? WHERE pos_id=?",
                            (ro_st, now_iso, ro_px, round(ro_pnl, 4), ro_px, db_row[0]))
                del open_positions[db_inst]
                try:
                    from scripts.telegram_reporter import send_telegram_trade_event
                    send_telegram_trade_event(ro_st, db_inst, str(db_row[2]), float(db_row[6] or 0.0), ro_px, round(ro_pnl, 2), real_nav or curr_nav, float(db_row[5] or 0.0), "Chiusura verificata su OKX")
                except Exception:
                    pass
        for okx_inst, okx_p in live_okx_pos.items():
            if okx_inst in FUTURES_UNIVERSE and okx_inst not in open_positions:
                pos_val = float(okx_p.get("pos") or 0.0)
                avg_px = float(okx_p.get("avgPx") or 0.0)
                mgn_u = round(float(okx_p.get("margin") or 35.0), 2)
                not_u = round(abs(pos_val) * float(FUTURES_UNIVERSE[okx_inst]["ct_val"]) * avg_px, 2)
                p_dir = "LONG" if pos_val > 0 else "SHORT"
                c_dec = int(FUTURES_UNIVERSE[okx_inst]["dec_px"])
                tp_px = round(avg_px * 1.0600, c_dec) if p_dir == "LONG" else round(avg_px * 0.9400, c_dec)
                sl_px = round(avg_px * 0.9920, c_dec) if p_dir == "LONG" else round(avg_px * 1.0080, c_dec)
                try:
                    ocos = _OKX_CLIENT._request("GET", f"/api/v5/trade/orders-algo-pending?instType=FUTURES&ordType=oco&instId={okx_inst}", auth=True).get("data", [])
                    if ocos:
                        tp_px = float(ocos[0].get("tpTriggerPx") or tp_px)
                        sl_px = float(ocos[0].get("slTriggerPx") or sl_px)
                except Exception:
                    pass
                efee = round(not_u * MAKER_FEE_RATE, 4)
                pid = f"XPERP_{okx_inst.split('-')[0]}_{int(okx_p.get('cTime') or int(time.time()*1000))}"
                cur.execute("INSERT OR REPLACE INTO futures_demo_positions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0, ?, 'OPEN', ?, NULL, NULL, NULL)",
                            (pid, okx_inst, p_dir, LEVERAGE, mgn_u, not_u, avg_px, avg_px, tp_px, sl_px, efee, now_iso))
                open_positions[okx_inst] = (pid, okx_inst, p_dir, LEVERAGE, mgn_u, not_u, avg_px, tp_px, sl_px, 0.0, 0, efee, now_iso)
                try:
                    from scripts.telegram_reporter import send_telegram_trade_event
                    send_telegram_trade_event("OPEN_FILLED", okx_inst, p_dir, avg_px, 0.0, 0.0, real_nav or curr_nav, not_u, f"TP=${tp_px} SL=${sl_px}")
                except Exception:
                    pass
        conn.commit()
    cur.execute("SELECT inst_id, status, (julianday('now') - julianday(closed_at)) * 1440.0, direction, exit_px, realized_pnl_usd FROM futures_demo_positions WHERE status != 'OPEN' AND closed_at IS NOT NULL ORDER BY closed_at DESC LIMIT 40")
    cooldown_blocked_insts = set()
    cooldown_dir_map: Dict[str, Tuple[str, float, str]] = {}  # inst_id -> (last_dir, mins_ago, status)
    continuation_breakout_map: Dict[str, Tuple[str, float]] = {}
    for c_inst, c_st, mins_ago, c_dir_hist, c_exit_px, c_pnl_h in cur.fetchall():
        m_ago = float(mins_ago or 0.0)
        if str(c_inst) not in cooldown_dir_map:
            cooldown_dir_map[str(c_inst)] = (str(c_dir_hist), m_ago, str(c_st))
        is_win_h = bool(c_st != "CLOSED_STOPLOSS" and float(c_pnl_h or 0.0) > 0.0)
        if is_win_h and 20.0 <= m_ago < 90.0 and float(c_exit_px or 0.0) > 0.0 and str(c_inst) not in continuation_breakout_map:
            continuation_breakout_map[str(c_inst)] = (str(c_dir_hist), float(c_exit_px))
            continue
        req_cd = 150.0 if c_st == "CLOSED_STOPLOSS" else 60.0
        if m_ago < req_cd:
            cooldown_blocked_insts.add(str(c_inst))
            # v28.0 Anti-Ping-Pong Twin Commodity Guard: a stop on CL blocks BZ (and vice versa) for 240 mins!
            if c_st == "CLOSED_STOPLOSS" and m_ago < 240.0 and str(c_inst).split("-")[0] in ("CL", "BZ"):
                for twin_k in FUTURES_UNIVERSE:
                    if twin_k.split("-")[0] in ("CL", "BZ"):
                        cooldown_blocked_insts.add(twin_k)
    now_ms_cd = int(time.time() * 1000)
    utc_hour = now_dt.hour
    is_night_hours = bool(utc_hour >= 22 or utc_hour < 5)  # 23:00 - 06:00 CET
    night_stop_lock = False
    for hiid, ho in okx_recent_ReduceOnly_map.items():
        mins_since_fill = (now_ms_cd - int(ho.get("uTime") or ho.get("cTime") or 0)) / 60000.0
        req_okx_cd = 120.0 if float(ho.get("pnl") or 0.0) <= 0.0 else (25.0 if hiid in continuation_breakout_map else 90.0)
        if mins_since_fill < req_okx_cd:
            cooldown_blocked_insts.add(hiid)
        # TRE OS v30.0 Nocturnal Stop Breaker: after ANY nocturnal stop-loss (< -$0.22 between 22:00-05:00 UTC), pause nocturnal entries for 120 mins (prevents 8-stop nocturnal chains)!
        if is_night_hours and float(ho.get("pnl") or 0.0) <= -0.22 and mins_since_fill < 120.0:
            night_stop_lock = True
    market_snaps = list(_IO_POOL.map(_fetch_swap_book_and_trades, list(FUTURES_UNIVERSE.keys())))
    btc_fc = kronos_map.get("BTC-USDC")
    btc_k5m = btc_fc.kronos_5m_bps if btc_fc else 0.0
    btc_k1h = btc_fc.expected_return_1h_bps if btc_fc else 0.0
    btc_real_15m = next((r15 for iid, _, _, _, r15, _, _, _, _, _ in market_snaps if "BTC-" in iid), 0.0)
    btc_real_1h = next((r1h for iid, _, _, _, _, r1h, _, _, _, _ in market_snaps if "BTC-" in iid), 0.0)
    # Proposal 4: Macro Regime Switcher (TREND_EXPANSION / MEAN_REVERSION_CHOP / HIGH_VOL_SHOCK)
    avg_abs_r1h = (sum(abs(r1h) for _, _, _, _, _, r1h, _, _, _, _ in market_snaps) / max(1, len(market_snaps))) if market_snaps else 15.0
    if abs(btc_real_15m) >= 85.0 or abs(btc_real_1h) >= 165.0:
        macro_regime = "HIGH_VOL_SHOCK"
    elif abs(btc_real_1h) >= 20.0 or avg_abs_r1h >= 20.0:
        macro_regime = "TREND_EXPANSION"
    else:
        macro_regime = "MEAN_REVERSION_CHOP"
    regime_shield_mult = 0.85 if macro_regime == "MEAN_REVERSION_CHOP" else 1.0
    regime_chand_bonus = 10.0 if macro_regime == "TREND_EXPANSION" else 0.0
    # Proposal 5: TradFi Catalyst & US Market Open Session Guard (Mon-Fri UTC)
    is_weekday = (now_dt.weekday() < 5)
    is_us_open_whipsaw = bool(is_weekday and ((utc_hour == 14 and 25 <= now_dt.minute <= 35) or (utc_hour == 12 and 25 <= now_dt.minute <= 35)))
    is_us_opening_drive = bool(is_weekday and utc_hour == 14 and 36 <= now_dt.minute <= 55)
    is_us_session = bool(is_weekday and 14 <= utc_hour <= 20)
    tradfi_coins = {"XAU", "XAG", "CL", "BZ", "NVDA", "TSLA", "AAPL", "AMZN", "COIN", "MSTR", "QQQ", "INTC", "SOXL", "SNDK"}
    telemetry_rows, actions_taken, candidates = [], [], []
    v35_entry_gates: Dict[Tuple[str, str], Any] = {}
    v35_forecasts: Dict[str, Any] = {}
    unrealized_total_usd, locked_margin_total_usd = 0.0, 0.0
    for inst_id, bids, asks, trades, real_15m_bps, real_1h_bps, real_48h_bps, atr_1h_bps, oi_delta_bps, funding_bps in market_snaps:
        if not bids or not asks:
            continue
        meta = FUTURES_UNIVERSE[inst_id]
        # Audit Fix #2: scale TradeEvent.size by contract ct_val so BTC/ETH/XAU 1-contract trades aren't treated as $80,000 trades pinning VPIN at 1.0!
        ct_v_m = float(meta.get("ct_val", 1.0))
        scaled_trades = [type(t)(timestamp=t.timestamp, price=t.price, size=t.size * ct_v_m, side=t.side) for t in trades] if trades else []
        sig = micro_engine.process_snapshot(inst_id, bids, asks, scaled_trades)
        mid = sig.mid_price
        if mid <= 0:
            continue
        k_fc = kronos_map.get(meta["spot_id"]) or kronos_map.get(inst_id)
        vfc_current = _KRONOS_VALIDATOR.validate(
            inst_id,
            k_fc,
            mid,
            float(getattr(k_fc, "last_close", 0.0) or 0.0) if k_fc else 0.0,
        )
        v35_forecasts[inst_id] = vfc_current
        kronos_entry_valid = bool(vfc_current.entry_valid)
        # Guard against Kronos float precision hallucination on sub-$0.0005 micro-priced tokens
        if k_fc and (mid < 0.0005 or abs(k_fc.kronos_5m_bps) > 150.0 or abs(k_fc.kronos_10m_bps) > 200.0):
            k_fc = None
        # TRE OS v28.3 STRICT KRONOS-ONLY MANDATE: NEVER invest on any asset that is not actively forecasted by neural Kronos-mini (k_fc is not None)!
        k5m = k_fc.kronos_5m_bps if k_fc else 0.0
        k10m = k_fc.kronos_10m_bps if k_fc else 0.0
        k1h = k_fc.expected_return_1h_bps if k_fc else 0.0
        k2h = k_fc.macro_return_2h_bps if k_fc else 0.0
        k6h = k_fc.horizon_6h_bps if k_fc else 0.0
        k12h = k_fc.swing_return_12h_bps if k_fc else 0.0
        k24h = k_fc.daily_return_24h_bps if k_fc else 0.0
        k_zscore = abs(float(k_fc.kronos_zscore_1h)) if k_fc else 0.0
        k_tp_prob = float(k_fc.tp_touch_prob_1h) if k_fc else 0.50
        k_vol_surge = float(k_fc.pred_volume_surge_ratio) if k_fc else 1.0
        # Phase 3 Lens #1/#3 (TRE OS v29.0): require Kronos Pre-Mean Signal-to-Noise Z-Score >= 0.20 (eliminates dead-on-arrival G0 noise trades!)
        # v35 entry eligibility is now authoritative. The old z-score OR
        # thresholds were able to bypass the anti-stale validator and admitted
        # stale/extreme tp probabilities into the legacy selector.
        k_snr_ok = bool(kronos_entry_valid and vfc_current.snr_1h >= 0.20)
        k_tp_prob = k_tp_prob if (kronos_entry_valid and 0.05 <= k_tp_prob <= 0.95) else 0.50
        sp_now_bps = ((asks[0][0] - bids[0][0]) / mid * 10000.0) if mid > 0 else 99.0
        # True Asymmetric Swing-Scalper Gate (v26.4): allow selling/buying 15m pullbacks up to +-40bps when all 7 Kronos horizons & OFI align!
        all7_bull = bool(k5m > 0 and k10m >= 3.5 and k1h >= 6.0 and k2h >= 0.0 and k6h >= 12.0 and k12h >= 15.0 and k24h >= 15.0 and real_1h_bps >= 3.0 and real_15m_bps >= -40.0)
        all7_bear = bool(k5m < 0 and k10m <= -3.5 and k1h <= -6.0 and k2h <= 0.0 and k6h <= -12.0 and k12h <= -15.0 and k24h <= -15.0 and real_1h_bps <= -3.0 and real_15m_bps <= 40.0)
        macro_bull = bool(all7_bull or ((k6h >= 8.0 or (k6h >= 2.0 and k12h >= 18.0 and k24h >= 25.0)) and (k12h >= 8.0 or k24h >= 8.0) and k2h >= -6.0 and k1h >= 6.0 and real_15m_bps >= -30.0 and (real_1h_bps >= -10.0 or (k5m >= 8.0 and k10m >= 8.0))))
        macro_bear = bool(all7_bear or ((k6h <= -8.0 or (k6h <= -2.0 and k12h <= -18.0 and k24h <= -25.0)) and (k12h <= -8.0 or k24h <= -8.0) and k2h <= 6.0 and k1h <= -6.0 and real_15m_bps <= 30.0 and (real_1h_bps <= -5.0 or (k5m <= -8.0 and k10m <= -8.0 and k1h <= -12.0))))
        # TRE OS v28.4 Bull/Bear Expansion Breakout Gate: when Kronos 5m/10m/1h strongly confirm continuation (>= 10/14/15 bps),
        # never cap real_15m_bps at 55 bps or real_1h_bps at 120 bps, and allow overriding RSI/Wick trap codes (-998/-993) during genuine market-wide expansions!
        # TRE OS v28.9 Anti-Chase & Anti-Falling-Knife Discipline:
        # 1) Never buy after an exhausted >+185 bps 1h spike (prevents AVAX top-buy at +500bps) or while 15m is dumping <-15 bps (prevents INJ falling knife)!
        # 2) Never short against a positive 1h trend (prevents ZEC short at -$0.98)!
        # TRE OS v33.0 Option 2 (Co-Approved by Giacomo): Real-Trend Dominance & Anti-Counter-Trend Kronos Mean-Reversion Override!
        # 1) Never buy Kronos mean-reversion bounces against a real market crash (real_1h <= -25bps or btc_real_1h <= -45bps),
        #    and never short Kronos mean-reversion dips against a real market rally (real_1h >= +25bps or btc_real_1h >= +45bps)!
        # 2) When the REAL market (15m + 1h + 48h + OFI) is in a confirmed directional wave, follow the Real Trend even if Kronos is mean-reverting!
        real_crash_regime = bool(real_1h_bps <= -25.0 or (not (meta["coin"] in tradfi_coins) and btc_real_1h <= -45.0))
        real_rally_regime = bool(real_1h_bps >= 25.0 or (not (meta["coin"] in tradfi_coins) and btc_real_1h >= 45.0))
        trend_follow_bull = bool(not real_crash_regime and 10.0 <= real_15m_bps <= 135.0 and 32.0 <= real_1h_bps <= 320.0 and (real_48h_bps >= 15.0 or btc_real_1h >= 60.0) and sig.ofi_norm >= 0.10)
        trend_follow_bear = bool(not real_rally_regime and -135.0 <= real_15m_bps <= -10.0 and -320.0 <= real_1h_bps <= -32.0 and (real_48h_bps <= -15.0 or btc_real_1h <= -60.0) and sig.ofi_norm <= -0.10)
        intraday_bull = bool(not real_crash_regime and (trend_follow_bull or (k5m >= 3.5 and k10m >= 5.0 and k1h >= 7.0 and k2h >= -4.0 and k6h >= -6.0 and 2.0 <= real_15m_bps <= 95.0 and 8.0 <= real_1h_bps <= 175.0 and sig.ofi_norm >= 0.12)))
        intraday_bear = bool(not real_rally_regime and (trend_follow_bear or (k5m <= -3.5 and k10m <= -5.0 and k1h <= -7.0 and k2h <= 4.0 and k6h <= 6.0 and -95.0 <= real_15m_bps <= -2.0 and -175.0 <= real_1h_bps <= -8.0 and sig.ofi_norm <= -0.12)))
        raw_bull_setup = bool(kronos_entry_valid and not real_crash_regime and (trend_follow_bull or (k_snr_ok and ((macro_bull and 0.0 <= real_15m_bps <= 95.0 and 10.0 <= real_1h_bps <= 175.0 and sig.ofi_norm >= 0.10) or intraday_bull))))
        raw_bear_setup = bool(kronos_entry_valid and not real_rally_regime and (trend_follow_bear or (k_snr_ok and ((macro_bear and -95.0 <= real_15m_bps <= 0.0 and -175.0 <= real_1h_bps <= -10.0 and sig.ofi_norm <= -0.10) or intraday_bear))))
        kronos_surge_bull, kronos_surge_bear = (intraday_bull or trend_follow_bull), (intraday_bear or trend_follow_bear)
        fund_ok_bull = bool(-900.0 < funding_bps < 9000.0)
        fund_ok_bear = bool(funding_bps < 900.0)
        allowed_dir = ("LONG" if (raw_bull_setup and fund_ok_bull and sp_now_bps <= 5.5) else ("SHORT" if (raw_bear_setup and fund_ok_bear and sp_now_bps <= 5.5) else "NEUTRAL"))
        ev_long_current = _EV_ENGINE.evaluate(inst_id, "LONG", vfc_current, sig.ofi_norm, sp_now_bps, atr_1h_bps, real_15m_bps, real_1h_bps, macro_regime, is_us_session)
        ev_short_current = _EV_ENGINE.evaluate(inst_id, "SHORT", vfc_current, sig.ofi_norm, sp_now_bps, atr_1h_bps, real_15m_bps, real_1h_bps, macro_regime, is_us_session)
        v35_entry_gates[(inst_id, "LONG")] = ev_long_current
        v35_entry_gates[(inst_id, "SHORT")] = ev_short_current
        # Proposal 2: ATR-Normalized Dynamic Thresholds (clamped to safe bounds; max loss locked at -$0.85 USDC)
        vol_mult_c = max(0.75, min(1.20, atr_1h_bps / 55.0))
        # TRE OS v31.0 Mandatory Asymmetric Volume & Payoff Architecture (Giacomo Rule #2):
        # - Losing trades stay at Phase 0 Probe volume (~$60 USDC) with strict max SL of -38 bps (-$0.23 max loss) and 6m/8m thesis-invalidation cut (-$0.12..-$0.16)!
        # - Winning trades scale at Phase 2 (+56 bps) by +$130 USDC at 3x -> ~$190 USDC (3.1x larger volume than losing trades!) and at Phase 3 (+130 bps) to ~$330 USDC!
        # - Minimum profit-taking floor: NEVER close for tiny $0.15-$0.35 gains; in Phase 1 (+36..55 bps) hold +6 bps safety breakeven so winners reach Phase 2 ($190 volume) and pay +$0.80..+$3.00!
        # TRE OS v32.3 Frozen Proven Equilibrium (30d & 97-trade verified, zero impulsive choking):
        # - Phase 0 Probe (~$62): SL at -45 bps (-$0.28 physiological stop); at +25 bps cut SL to -20 bps (-$0.12).
        # - Phase 1 (+40 bps): tighten SL to -10 bps; at +55 bps lock +15 bps cushion (breathing room to reach Tier 2 without choking winners at +22bps!).
        # - Phase 2 (+68 bps): scale +$130 at 3x (~$190 volume) in Free-Roll with +30 bps lock above new avgPx!
        # TRE OS v34.0 Co-Approved Margin Expansion Architecture:
        # 1) Tier 1 at +34 bps; Tier 2 (+$115 at 3x -> ~$177 volume) triggers at +44 bps so every +50..+99 bps wave rides with 3x volume!
        # 2) Guaranteed Tier 2/3 execution (urgent_stop=True) so HYPE/XRP/PUMP never stay stuck at $61 Probe size!
        # 3) Post-scale breathing room: initial G2 floor at +2.0 bps above new avgPx (~+30bps above Probe entry), ratcheting to 65% of G2 peak once >= +32 bps above new avgPx!
        dyn_shield_gate_bps = round(max(32.0, min(36.0, 34.0 * vol_mult_c * regime_shield_mult)), 1)
        dyn_tier2_gate_bps = round(max(42.0, min(48.0, 44.0 * vol_mult_c)), 1)
        dyn_tier3_gate_bps = round(max(88.0, min(120.0, 100.0 * vol_mult_c)), 1)
        dyn_sl_gate_bps = round(max(42.0, min(52.0, 45.0 * vol_mult_c)), 1)
        # Proposal 3: Zero-RAM Shadow Paper-Arena (record setup blocked ONLY by Tools #1-#10 into SQLite max 1/15m per coin)
        if allowed_dir == "NEUTRAL" and sp_now_bps <= 5.5 and (raw_bull_setup or raw_bear_setup):
            trap_map = {
                -999.0: "Tool#1_PostPumpBleed24h", -991.0: "Tool#2_Low1hVol<$5k", -993.0: "Tool#3_UpperWickReject",
                -994.0: "Tool#4_BelowVWAP_CVD", -998.0: "Tool#8_RSI>=73_Overbought",
                997.0: "Tool#7_Bottom18PctShort", 993.0: "Tool#3_LowerWickReject",
                994.0: "Tool#4_AboveVWAP_CVD", 998.0: "Tool#8_RSI<=27_Oversold"
            }
            blk_reason = trap_map.get(funding_bps, "")
            if blk_reason:
                sh_dir = "LONG" if raw_bull_setup else "SHORT"
                sh_bucket = int(time.time() // 900)
                sh_id = f"SHDW_{meta['coin']}_{sh_dir}_{sh_bucket}"
                cur.execute("INSERT OR IGNORE INTO shadow_filtered_signals VALUES (?, ?, ?, ?, ?, ?, 0, NULL, NULL, NULL)",
                            (sh_id, inst_id, sh_dir, blk_reason, mid, now_iso))
        if inst_id in open_positions:
            p_id, _, p_dir, p_lev, p_mgn, p_notional, p_entry, p_tp, p_sl, p_peak_bps, p_shield, p_efee, p_open_ts = open_positions[inst_id]
            move_bps = ((mid - p_entry) / p_entry * 10000.0) if p_dir == "LONG" else ((p_entry - mid) / p_entry * 10000.0)
            new_peak = max(float(p_peak_bps), move_bps)
            try:
                pos_age_mins = (now_dt - datetime.datetime.fromisoformat(str(p_open_ts).replace("Z", "+00:00"))).total_seconds() / 60.0
            except Exception:
                pos_age_mins = 0.0
            # TRE OS v21.0: 3-TIER FREE-ROLL PYRAMID + IMPL #1/#2/#4 + NEVER CLOSE IN SMALL PROFIT UNLESS EMERGENCY!
            prev_tier = int(p_shield)
            new_shield = prev_tier
            # Impl #1 Harmonized (v26.6): VPIN is unsigned volume imbalance — high VPIN WITH our direction is favorable breakout flow, not toxic!
            pyr_flow_ok = bool((p_dir == "LONG" and (sig.ofi_norm >= 0.15 or (sig.ofi_norm >= -0.10 and sig.vpin_toxicity <= 0.82))) or (p_dir == "SHORT" and (sig.ofi_norm <= -0.15 or (sig.ofi_norm <= 0.10 and sig.vpin_toxicity <= 0.82))))
            # Impl #2: Orderbook Wall Detector (detect opposing wall >= 4x average in top 5 levels)
            opp_book = asks[:5] if p_dir == "LONG" else bids[:5]
            avg_lvl_sz = (sum(float(x[1]) for x in opp_book) / max(1, len(opp_book))) if opp_book else 1.0
            max_lvl_sz = max((float(x[1]) for x in opp_book), default=0.0)
            opposing_wall_detected = bool(avg_lvl_sz > 0 and (max_lvl_sz / avg_lvl_sz) >= 3.8)
            # Gradino 0.5 Early Risk Halving: at +25 bps, cut hardware SL to -20 bps (-$0.12 max risk)!
            if new_peak >= 25.0 and new_shield == 0 and float(p_peak_bps) < 25.0 and live_mode:
                _amend_okx_hardware_sl_to_breakeven(inst_id, p_dir, p_entry, -20.0, meta["dec_px"])
            if new_peak >= dyn_shield_gate_bps and prev_tier < 1:
                new_shield = 1
                if live_mode:
                    _amend_okx_hardware_sl_to_breakeven(inst_id, p_dir, p_entry, -10.0, meta["dec_px"])
            if new_peak >= 55.0 and new_shield == 1 and float(p_peak_bps) < 55.0 and live_mode:
                _amend_okx_hardware_sl_to_breakeven(inst_id, p_dir, p_entry, 15.0, meta["dec_px"])
            if new_peak >= dyn_tier2_gate_bps and prev_tier < 2 and pyr_flow_ok:
                if not live_mode:
                    new_shield = 2
                elif free_mgn >= 45.0:
                    eff_pyr_lev = 2.0
                    try:
                        r_lv = _OKX_CLIENT._request("POST", "/api/v5/account/set-leverage", body_dict={"instId": inst_id, "lever": "3", "mgnMode": "isolated"}, auth=True)
                        if str((r_lv.get("data") or [{}])[0].get("sCode", "")) == "0":
                            eff_pyr_lev = 3.0
                    except Exception:
                        pass
                    nav_ref = real_nav if real_nav > 10.0 else base_nav
                    comp_notional = round(min(free_mgn * eff_pyr_lev * 0.58, max(112.0, nav_ref * 0.45)), 2)
                    exec_g2_px = asks[0][0] if p_dir == "LONG" else bids[0][0]
                    add_sz, add_not = _calc_contract_sz(inst_id, comp_notional, exec_g2_px)
                    # TRE OS v34.0 Fix #1: always use urgent_stop=True on G2 scale-in so OKX NEVER rejects a crossed post_only order (fixes HYPE/XRP/PUMP stuck at $61)!
                    if _execute_live_xperp_order(inst_id, "buy" if p_dir == "LONG" else "sell", add_sz, exec_g2_px, meta["dec_px"], urgent_stop=True):
                        new_shield = 2
                        old_not_g1 = max(1.0, p_notional)
                        p_notional = round(p_notional + add_not, 2)
                        p_mgn = round(p_mgn + (add_not / eff_pyr_lev), 2)
                        p_entry = round(((p_entry * old_not_g1) + (exec_g2_px * add_not)) / max(1.0, p_notional), meta["dec_px"])
                        move_bps = ((mid - p_entry) / p_entry * 10000.0) if p_dir == "LONG" else ((p_entry - mid) / p_entry * 10000.0)
                        new_peak = max(16.0, move_bps)
                        tot_sz_s, _ = _calc_contract_sz(inst_id, p_notional, p_entry)
                        lock_g2_bps = 2.0  # +2.0 bps above new avgPx (~+30bps profit locked on Probe, giving 14+ bps breathing room right after scaling!)
                        _amend_okx_hardware_sl_to_breakeven(inst_id, p_dir, p_entry, lock_g2_bps, meta["dec_px"], new_sz_str=tot_sz_s)
                        try:
                            from scripts.telegram_reporter import send_telegram_trade_event
                            send_telegram_trade_event("OPEN_GRADINO_2_3X_FREEROLL", inst_id, p_dir, p_entry, 0.0, 0.0, nav_ref, p_notional, f"Rincaro G2 +{add_not:.0f}$ (Leva {eff_pyr_lev:.0f}x) | Nuovo AvgPx=${p_entry} | Stop +{lock_g2_bps}bps")
                        except Exception:
                            pass
            eff_tier3_gate_bps = round(max(62.0, dyn_tier3_gate_bps - 35.0), 1) if prev_tier >= 2 else dyn_tier3_gate_bps
            if new_peak >= eff_tier3_gate_bps and prev_tier < 3 and pyr_flow_ok:
                if not live_mode:
                    new_shield = 3
                elif free_mgn >= 45.0:
                    eff_pyr_lev = 2.0
                    try:
                        r_lv = _OKX_CLIENT._request("POST", "/api/v5/account/set-leverage", body_dict={"instId": inst_id, "lever": "3", "mgnMode": "isolated"}, auth=True)
                        if str((r_lv.get("data") or [{}])[0].get("sCode", "")) == "0":
                            eff_pyr_lev = 3.0
                    except Exception:
                        pass
                    nav_ref = real_nav if real_nav > 10.0 else base_nav
                    comp_notional = round(min(free_mgn * eff_pyr_lev * 0.58, max(112.0, nav_ref * 0.42)), 2)
                    exec_g3_px = asks[0][0] if p_dir == "LONG" else bids[0][0]
                    add_sz, add_not = _calc_contract_sz(inst_id, comp_notional, exec_g3_px)
                    if _execute_live_xperp_order(inst_id, "buy" if p_dir == "LONG" else "sell", add_sz, exec_g3_px, meta["dec_px"], urgent_stop=True):
                        new_shield = 3
                        old_not_g2 = max(1.0, p_notional)
                        p_notional = round(p_notional + add_not, 2)
                        p_mgn = round(p_mgn + (add_not / eff_pyr_lev), 2)
                        p_entry = round(((p_entry * old_not_g2) + (exec_g3_px * add_not)) / max(1.0, p_notional), meta["dec_px"])
                        move_bps = ((mid - p_entry) / p_entry * 10000.0) if p_dir == "LONG" else ((p_entry - mid) / p_entry * 10000.0)
                        new_peak = max(32.0, move_bps)
                        tot_sz_s, _ = _calc_contract_sz(inst_id, p_notional, p_entry)
                        lock_g3_bps = 24.0  # +24 bps above new 3-tier avgPx (~+85 bps above initial Probe entry!)
                        _amend_okx_hardware_sl_to_breakeven(inst_id, p_dir, p_entry, lock_g3_bps, meta["dec_px"], new_sz_str=tot_sz_s)
                        try:
                            from scripts.telegram_reporter import send_telegram_trade_event
                            send_telegram_trade_event("OPEN_GRADINO_3_3X_RUNNER", inst_id, p_dir, p_entry, 0.0, 0.0, nav_ref, p_notional, f"Rincaro G3 +{add_not:.0f}$ (Leva {eff_pyr_lev:.0f}x) | Stop blindato a +{lock_g3_bps}bps")
                        except Exception:
                            pass
            # Rule R03 & v25.9 TradFi Decoupling: TradFi (CL, XAU, XAG, Equities) does NOT trigger emergency exit on a 5m Bitcoin spike!
            is_pos_tradfi = bool(meta["coin"] in tradfi_coins)
            # Anti-Panic Emergency Harmonization (v26.6): require BOTH L2 opposing toxicity AND Kronos 5m/10m reversal, and exit in Maker above +24 bps!
            emergency_situation = bool(
                (p_dir == "LONG" and ((not is_pos_tradfi and btc_k5m <= -28.0 and btc_real_15m <= -25.0) or (sig.vpin_toxicity >= 0.94 and sig.ofi_norm <= -0.65 and k5m <= -6.0 and k10m <= -6.0))) or
                (p_dir == "SHORT" and ((not is_pos_tradfi and btc_k5m >= 28.0 and btc_real_15m >= 25.0) or (sig.vpin_toxicity >= 0.94 and sig.ofi_norm >= 0.65 and k5m >= 6.0 and k10m >= 6.0)))
            )
            exit_reason, exit_exec_px, urgent_stop = None, mid, False
            if (p_dir == "LONG" and bids[0][0] >= p_tp) or (p_dir == "SHORT" and asks[0][0] <= p_tp):
                exit_reason, exit_exec_px, urgent_stop = "CLOSED_PROFIT", p_tp, True
            elif new_shield >= 3:
                # Bounce-Aware & Macro-Runner Chandelier (Tier 3, v26.6: favorable VPIN allowed when OFI is in our direction!)
                bounce_t3 = bool(not opposing_wall_detected and ((p_dir == "LONG" and sig.ofi_norm >= 0.22 and k5m > 0.0 and k1h >= 10.0) or (p_dir == "SHORT" and sig.ofi_norm <= -0.22 and k5m < 0.0 and k1h <= -10.0)))
                macro_runner_t3 = bool(not opposing_wall_detected and ((p_dir == "LONG" and k6h >= 25.0 and k12h >= 25.0) or (p_dir == "SHORT" and k6h <= -25.0 and k12h <= -25.0)))
                wall_weak_t3 = bool(opposing_wall_detected and ((p_dir == "LONG" and k1h < 12.0) or (p_dir == "SHORT" and k1h > -12.0)))
                buf3 = 45.0 if (wall_weak_t3 and move_bps >= 95.0) else ((105.0 if macro_runner_t3 else (95.0 if bounce_t3 else 70.0)) + regime_chand_bonus)
                locked_move_bps = max(48.0, new_peak - buf3)
                if live_mode and (new_peak - float(p_peak_bps)) >= 18.0:
                    _amend_okx_hardware_sl_to_breakeven(inst_id, p_dir, p_entry, round(locked_move_bps, 1), meta["dec_px"])
                if move_bps <= locked_move_bps and (new_peak >= 85.0 or move_bps <= 42.0):
                    exit_reason, exit_exec_px, urgent_stop = "CLOSED_SHIELD", (asks[0][0] if p_dir == "LONG" else bids[0][0]), False
            elif new_shield == 2:
                # TRE OS v34.0 Co-Approved Tier-2 Margin Lock (~$177 volume):
                # - Below +32 bps above new avgPx (~+61 bps total move): hold the +2.0 bps Free-Roll floor so the post-scale position has full breathing room!
                # - Once >= +32 bps above new avgPx (like AVAX +61bps, SPCX +64bps, HYPE +99bps, XRP +97bps, PUMP +95bps): lock 65% of G2 peak (or trail by buf2 on big runners)!
                bounce_t2 = bool(not opposing_wall_detected and ((p_dir == "LONG" and sig.ofi_norm >= 0.22 and k5m > 0.0 and k1h >= 10.0) or (p_dir == "SHORT" and sig.ofi_norm <= -0.22 and k5m < 0.0 and k1h <= -10.0)))
                buf2 = (38.0 if bounce_t2 else 26.0) + (regime_chand_bonus * 0.3)
                locked_move_bps = max(22.0, min(round(new_peak * 0.65, 1), new_peak - 16.0), new_peak - buf2) if new_peak >= 32.0 else 2.0
                if live_mode and new_peak >= 32.0 and (float(p_peak_bps) < 32.0 or (new_peak - float(p_peak_bps)) >= 10.0):
                    _amend_okx_hardware_sl_to_breakeven(inst_id, p_dir, p_entry, round(locked_move_bps, 1), meta["dec_px"])
                if move_bps <= locked_move_bps:
                    exit_reason, exit_exec_px, urgent_stop = "CLOSED_SHIELD", (asks[0][0] if p_dir == "LONG" else bids[0][0]), False
            elif new_shield == 1 and move_bps <= (25.0 if new_peak >= 50.0 else -10.0):
                # Luna Spec Variant B Baseline: once Peak >= +50 bps (60% TP1 zone), lock at least +25 bps on the position so +50..+64 bps waves ALWAYS bank real net profit!
                exit_reason, exit_exec_px, urgent_stop = "CLOSED_SHIELD", (asks[0][0] if p_dir == "LONG" else bids[0][0]), False
            elif emergency_situation and move_bps >= 24.0:
                exit_reason, exit_exec_px, urgent_stop = "CLOSED_SHIELD", (asks[0][0] if p_dir == "LONG" else bids[0][0]), False
            elif new_shield == 0 and pos_age_mins >= 75.0 and -48.0 <= move_bps <= 8.0 and ((p_dir == "LONG" and (k1h < 12.0 or k6h < 0.0)) or (p_dir == "SHORT" and (k1h > -12.0 or k6h > 0.0))):
                # Tool #6 Harmonized (v27.5): after 75m, if still at Tier 0 and between -48 and +8 bps (like ONDO at 106m or TAO at 105m with negative k6h), exit in Maker!
                exit_reason, exit_exec_px, urgent_stop = "CLOSED_SHIELD", (asks[0][0] if p_dir == "LONG" else bids[0][0]), False
            # TRE OS v31.0 Continuous 'DURING-TRADE' Thesis Audit:
            # If in Phase 0 after >=6 mins the market thesis flips (both Kronos 5m/10m AND OFI oppose our direction) and Peak < +12 bps, exit immediately in Maker at <= -18 bps (-$0.11)!
            thesis_broken_in_trade = bool(new_shield == 0 and pos_age_mins >= 6.0 and new_peak < 12.0 and ((p_dir == "LONG" and k5m <= -2.0 and k10m <= -2.0 and sig.ofi_norm <= -0.10) or (p_dir == "SHORT" and k5m >= 2.0 and k10m >= 2.0 and sig.ofi_norm >= 0.10)))
            if not exit_reason and thesis_broken_in_trade and move_bps <= -14.0:
                exit_reason, exit_exec_px, urgent_stop = "CLOSED_SHIELD", (asks[0][0] if p_dir == "LONG" else bids[0][0]), False
            doa_flow_against = bool(new_shield == 0 and pos_age_mins >= 8.0 and new_peak < 10.0 and ((p_dir == "LONG" and (k5m <= 0.0 or sig.ofi_norm <= -0.08)) or (p_dir == "SHORT" and (k5m >= 0.0 or sig.ofi_norm >= 0.08))))
            eff_sl_gate_bps = min(dyn_sl_gate_bps, 20.0) if (new_shield == 0 and new_peak >= 22.0) else (min(dyn_sl_gate_bps, 22.0) if doa_flow_against else dyn_sl_gate_bps)
            if not exit_reason and move_bps <= -eff_sl_gate_bps:
                exit_reason, exit_exec_px, urgent_stop = "CLOSED_STOPLOSS", (bids[0][0] if p_dir == "LONG" else asks[0][0]), True
            if exit_reason:
                if live_mode and inst_id in live_okx_pos:
                    pos_cts = abs(float(live_okx_pos[inst_id].get("pos") or 0.0))
                    dec_sz = int(meta.get("dec_sz", 0))
                    sz_str = f"{pos_cts:.{dec_sz}f}" if dec_sz > 0 else str(int(round(pos_cts)))
                    close_side = "sell" if p_dir == "LONG" else "buy"
                    _execute_live_xperp_order(inst_id, close_side, sz_str, exit_exec_px, meta["dec_px"], reduce_only=True, urgent_stop=urgent_stop)
                realized_move_bps = max(-156.0, ((exit_exec_px - p_entry) / p_entry * 10000.0) if p_dir == "LONG" else ((p_entry - exit_exec_px) / p_entry * 10000.0))
                exit_fee_rate = 0.0005 if (live_mode and urgent_stop) else MAKER_FEE_RATE
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
                try:
                    from scripts.telegram_reporter import send_telegram_trade_event
                    send_telegram_trade_event(exit_reason, inst_id, p_dir, p_entry, exit_exec_px, round(net_pnl_usd, 2), real_nav or live_nav_est, p_notional, f"Picco={new_peak:.1f}bps Gradino=G{new_shield}")
                except Exception:
                    pass
            else:
                if live_mode and inst_id in live_okx_pos:
                    real_cts = abs(float(live_okx_pos[inst_id].get("pos") or 0.0))
                    real_avg = float(live_okx_pos[inst_id].get("avgPx") or p_entry)
                    if real_cts > 0 and real_avg > 0:
                        if abs(real_avg - p_entry) / max(1e-9, p_entry) >= 0.0010:
                            old_pk_px = (p_entry * (1.0 + new_peak / 10000.0)) if p_dir == "LONG" else (p_entry * (1.0 - new_peak / 10000.0))
                            rebased_pk = ((old_pk_px - real_avg) / real_avg * 10000.0) if p_dir == "LONG" else ((real_avg - old_pk_px) / real_avg * 10000.0)
                            move_bps = ((mid - real_avg) / real_avg * 10000.0) if p_dir == "LONG" else ((real_avg - mid) / real_avg * 10000.0)
                            new_peak = max(18.0, move_bps, rebased_pk)
                        p_entry = real_avg
                        p_notional = round(real_cts * float(meta.get("ct_val", 1.0)) * real_avg, 2)
                        okx_mgn = float(live_okx_pos[inst_id].get("margin") or 0.0)
                        p_mgn = round(okx_mgn if okx_mgn > 0 else (p_notional / (3.0 if new_shield >= 2 else 2.0)), 2)
                unr_usd = round((p_notional * (move_bps / 10000.0)) - p_efee - (p_notional * MAKER_FEE_RATE), 3)
                unrealized_total_usd += unr_usd
                locked_margin_total_usd += p_mgn
                cur.execute("UPDATE futures_demo_positions SET entry_px=?, current_px=?, peak_move_bps=?, shield_armed=?, margin_usd=?, notional_usd=? WHERE pos_id=?", (p_entry, mid, new_peak, new_shield, p_mgn, p_notional, p_id))
        # Tool #9 (BTC Beta Divergence Veto — decoupled for TradFi CL/XAU/Equities in v25.9!) + Tool #10 (Whip-Saw Shield):
        is_funding_whipsaw = bool((utc_hour in (0, 8, 16) and now_dt.minute in (0, 1)) or (utc_hour in (23, 7, 15) and now_dt.minute == 59) or is_us_open_whipsaw)
        is_cand_tradfi = bool(meta["coin"] in tradfi_coins)
        # Do NOT trigger btc_veto_long on a normal 15m consolidation pullback when BTC 1h is strongly bullish (>= +40 bps) and BTC Kronos 5m/1h are bullish (>= +5/+10 bps)!
        btc_bull_expansion = bool(btc_real_1h >= 40.0 and btc_k5m >= 5.0 and btc_k1h >= 10.0)
        btc_bear_expansion = bool(btc_real_1h <= -40.0 and btc_k5m <= -5.0 and btc_k1h <= -10.0)
        btc_veto_long = bool(is_funding_whipsaw or (not is_cand_tradfi and not btc_bull_expansion and (btc_k5m <= -8.0 or btc_k1h <= -15.0 or btc_real_15m <= -8.0 or btc_real_1h <= -15.0 or (btc_k5m <= -2.0 and btc_k1h <= -5.0 and btc_real_15m <= -1.0))))
        btc_veto_short = bool(is_funding_whipsaw or (not is_cand_tradfi and not btc_bear_expansion and (btc_k5m >= 8.0 or btc_k1h >= 15.0 or btc_real_15m >= 8.0 or btc_real_1h >= 15.0 or (btc_k5m >= 2.0 and btc_k1h >= 5.0 and btc_real_15m >= 0.0))))
        if inst_id in continuation_breakout_map:
            cb_dir, cb_exit_px = continuation_breakout_map[inst_id]
            if not ((cb_dir == "LONG" and allowed_dir == "LONG" and mid >= cb_exit_px * 1.0005) or (cb_dir == "SHORT" and allowed_dir == "SHORT" and mid <= cb_exit_px * 0.9995)):
                cooldown_blocked_insts.add(inst_id)
        # TRE OS v29.1 False-Negative Fix #4: if a Crypto coin reversed direction after >=30m with strong Kronos+15m+1h+OFI alignment, unblock the opposite direction!
        if inst_id in cooldown_blocked_insts and not is_cand_tradfi and inst_id in cooldown_dir_map:
            last_d_cd, m_ago_cd, _ = cooldown_dir_map[inst_id]
            if m_ago_cd >= 30.0 and allowed_dir in ("LONG", "SHORT") and allowed_dir != last_d_cd and (kronos_surge_bull or kronos_surge_bear):
                cooldown_blocked_insts.discard(inst_id)
        # Impl #3: OI + Funding Squeeze Detector (harmonized: ignore -999/+999 trap codes in funding_bps!)
        real_fund_bps = funding_bps if -800.0 < funding_bps < 800.0 else 0.0
        sqz_reg = "SQUEEZE_LONG" if (real_15m_bps >= 5.0 and oi_delta_bps >= 0.0 and (sig.ofi_norm >= 0.22 or real_fund_bps < 0.0)) else ("SQUEEZE_SHORT" if (real_15m_bps <= -5.0 and oi_delta_bps >= 0.0 and (sig.ofi_norm <= -0.22 or real_fund_bps > 0.0)) else "NORMAL")
        sqz_bonus = (22.0 if ((sqz_reg == "SQUEEZE_LONG" and real_fund_bps < 0.0) or (sqz_reg == "SQUEEZE_SHORT" and real_fund_bps > 0.0)) else (12.0 if sqz_reg != "NORMAL" else 0.0))
        # Proposal 5: TradFi & US Equity/Commodity Session Priority Boost (+18 pt Opening Drive, +12 pt US Session when Crypto Chop)
        is_tradfi = bool(meta["coin"] in tradfi_coins)
        tradfi_bonus = (18.0 if (is_tradfi and is_us_opening_drive) else (12.0 if (is_tradfi and is_us_session and macro_regime == "MEAN_REVERSION_CHOP") else 0.0))
        regime_ok = bool(macro_regime != "HIGH_VOL_SHOCK" or sqz_reg != "NORMAL" or all7_bull or all7_bear or kronos_surge_bull or kronos_surge_bear)
        eff_k10m_gate = max(6.0, min(12.0, min_k10m_gate))
        boost_bonus = (15.0 if inst_id in brain_skills.get("priority_boost_inst_ids", []) else 0.0) + tradfi_bonus
        is_blacklisted = inst_id in brain_skills.get("blacklist_inst_ids", [])
        gem_sniper_map = {str(x.get("inst_id")): str(x.get("dir")) for x in brain_skills.get("gemini_sniper_entries", []) if isinstance(x, dict)}
        # Calibrated Night Gate (v26.2): require +20% conviction instead of near-impossible 7-horizon >=15bps lock, and allow Gemini Sniper at night!
        # Directional VPIN Harmonization (v26.6): unsigned VPIN > 0.78 is only toxic when OFI opposes the trade direction; when OFI >= 0.20 in our favor, high VPIN is institutional breakout flow!
        vpin_ok_long = bool(sig.vpin_toxicity <= 0.82 or sig.ofi_norm >= 0.20)
        vpin_ok_short = bool(sig.vpin_toxicity <= 0.82 or sig.ofi_norm <= -0.20)
        # v27.6 Asset-Class Nocturnal Liquidity Guard: block illiquid 21:30-04:45 UTC commodity/equity whipsaws (saves -$2.29 on CL/XAG at 2am) while opening full throttle at 04:45 UTC (05:45 CET)!
        # v28.0 Strict Asset-Class Session Guard: US Equities ONLY trade during US Cash hours (14:30-20:30 UTC Mon-Fri); Commodities block 21:30-04:45 UTC!
        us_eq_coins = {"NVDA", "TSLA", "AAPL", "AMZN", "COIN", "MSTR", "QQQ", "INTC", "SOXL", "SNDK", "GOOGL", "CRCL", "SPCX"}
        is_us_eq = bool(meta["coin"] in us_eq_coins)
        us_eq_closed = bool(is_us_eq and not (is_weekday and ((utc_hour == 14 and now_dt.minute >= 35) or (15 <= utc_hour <= 19) or (utc_hour == 20 and now_dt.minute <= 30))))
        is_deep_night_tradfi = bool(us_eq_closed or (is_tradfi and (utc_hour >= 22 or utc_hour < 4 or (utc_hour == 21 and now_dt.minute >= 30) or (utc_hour == 4 and now_dt.minute < 45))))
        night_ok_long = (not is_deep_night_tradfi) and ((not is_night_hours) or bool(k5m >= 4.0 and k10m >= 5.5 and k1h >= 7.0 and (sig.ofi_norm >= 0.14 or k10m >= 12.0) and vpin_ok_long))
        night_ok_short = (not is_deep_night_tradfi) and ((not is_night_hours) or bool(k5m <= -4.0 and k10m <= -5.5 and k1h <= -7.0 and (sig.ofi_norm <= -0.14 or k10m <= -12.0) and vpin_ok_short))
        is_boosted = inst_id in brain_skills.get("priority_boost_inst_ids", [])
        pullback_long_ok = bool((is_boosted or all7_bull or (k6h >= 10.0 and real_1h_bps >= 12.0) or (is_tradfi and k1h >= 8.0 and real_1h_bps >= 6.0)) and k1h >= 5.0 and k2h >= -2.0 and k5m >= -4.0 and vpin_ok_long and sig.ofi_norm >= 0.08)
        pullback_short_ok = bool((is_boosted or all7_bear or (k6h <= -10.0 and real_1h_bps <= -12.0) or (is_tradfi and k1h <= -8.0 and real_1h_bps <= -6.0)) and k1h <= -5.0 and k2h <= 2.0 and k5m <= 4.0 and vpin_ok_short and sig.ofi_norm <= -0.08)
        mom_long_ok = bool(k5m >= 10.0 and k10m >= 14.0 and k1h >= 15.0 and real_15m_bps <= -10.0 and vpin_ok_long)
        mom_short_ok = bool(k5m <= -10.0 and k10m <= -14.0 and k1h <= -15.0 and real_15m_bps >= -60.0 and vpin_ok_short)
        if regime_ok and not night_stop_lock and not is_blacklisted and inst_id not in open_positions and inst_id not in cooldown_blocked_insts and not lifecycle["reduce_only"]:
            if allowed_dir == "LONG" and night_ok_long and not btc_veto_long and (((k5m >= 3.5 and k10m >= 4.5 and sig.ofi_norm >= 0.10) or kronos_surge_bull or pullback_long_ok or mom_long_ok)) and vpin_ok_long:
                # Pillar 3 & 4 (v28.1): WorldQuant Alpha #101 conviction + Kronos Multi-Horizon Acceleration bonus!
                kronos_accel_b = 12.0 if (k10m > k5m > 2.0 and k1h >= k10m) else 0.0
                wq_conv_b = 10.0 if (abs(real_15m_bps) >= 8.0 and atr_1h_bps > 0 and (abs(real_15m_bps) / max(10.0, atr_1h_bps * 0.5)) >= 0.45) else 0.0
                k_prob_bonus = round((k_tp_prob - 0.50) * 16.0 + min(8.0, k_zscore * 6.0) + (4.0 if k_vol_surge >= 1.25 else 0.0), 2)
                real_mom_b = round((max(0.0, real_15m_bps) * 0.35) + (max(0.0, real_1h_bps) * 0.22), 2) if trend_follow_bull else round(max(0.0, real_1h_bps) * 0.15, 2)
                k_part_b = round((max(2.0, k5m) * 0.8) + (max(4.0, k10m) * 1.1) + (max(0.0, k1h) * 0.4), 2) if k1h > 0 else 12.0
                score = round(k_part_b + real_mom_b + (sig.ofi_norm * 18.0) + boost_bonus + sqz_bonus + kronos_accel_b + wq_conv_b + k_prob_bonus, 2)
                candidates.append({"inst_id": inst_id, "dir": "LONG", "score": score, "px": bids[0][0], "dec_px": meta["dec_px"], "vol_mult": vol_mult_c, "sl_bps": dyn_sl_gate_bps})
            elif allowed_dir == "SHORT" and night_ok_short and not btc_veto_short and (((k5m <= -3.5 and k10m <= -4.5 and sig.ofi_norm <= -0.10) or kronos_surge_bear or pullback_short_ok or mom_short_ok)) and vpin_ok_short:
                kronos_accel_s = 12.0 if (k10m < k5m < -2.0 and k1h <= k10m) else 0.0
                wq_conv_s = 10.0 if (abs(real_15m_bps) >= 8.0 and atr_1h_bps > 0 and (abs(real_15m_bps) / max(10.0, atr_1h_bps * 0.5)) >= 0.45) else 0.0
                k_prob_bonus = round((k_tp_prob - 0.50) * 16.0 + min(8.0, k_zscore * 6.0) + (4.0 if k_vol_surge >= 1.25 else 0.0), 2)
                real_mom_s = round((max(0.0, -real_15m_bps) * 0.35) + (max(0.0, -real_1h_bps) * 0.22), 2) if trend_follow_bear else round(max(0.0, abs(real_1h_bps)) * 0.15, 2)
                k_part_s = round((max(2.0, abs(k5m)) * 0.8) + (max(4.0, abs(k10m)) * 1.1) + (max(0.0, -k1h) * 0.4), 2) if k1h < 0 else 12.0
                score = round(k_part_s + real_mom_s + (abs(sig.ofi_norm) * 18.0) + boost_bonus + sqz_bonus + kronos_accel_s + wq_conv_s + k_prob_bonus, 2)
                candidates.append({"inst_id": inst_id, "dir": "SHORT", "score": score, "px": asks[0][0], "dec_px": meta["dec_px"], "vol_mult": vol_mult_c, "sl_bps": dyn_sl_gate_bps})
            elif inst_id in gem_sniper_map and (vpin_ok_long or vpin_ok_short) and funding_bps > -900.0 and funding_bps < 900.0:
                g_dir = gem_sniper_map[inst_id]
                if g_dir == "LONG" and not btc_veto_long and real_1h_bps >= -5.0 and sig.ofi_norm >= 0.12 and k1h >= 5.0:
                    candidates.append({"inst_id": inst_id, "dir": "LONG", "score": round(35.0 + boost_bonus + sqz_bonus, 2), "px": bids[0][0], "dec_px": meta["dec_px"], "vol_mult": vol_mult_c})
                elif g_dir == "SHORT" and not btc_veto_short and real_1h_bps <= -3.0 and sig.ofi_norm <= -0.12 and k1h <= -5.0:
                    candidates.append({"inst_id": inst_id, "dir": "SHORT", "score": round(35.0 + boost_bonus + sqz_bonus, 2), "px": asks[0][0], "dec_px": meta["dec_px"], "vol_mult": vol_mult_c})
        k48h = round((k24h * 1.35) + (real_48h_bps * 0.25), 1)
        telemetry_rows.append({
            "inst_id": inst_id, "mid_price": mid, "ofi_norm": round(sig.ofi_norm, 2), "spread_bps": round(sp_now_bps, 2), "vpin_toxicity": round(sig.vpin_toxicity, 2),
            "atr_1h_bps": round(atr_1h_bps, 1), "oi_delta_bps": round(oi_delta_bps, 1), "squeeze_regime": sqz_reg,
            "real_15m_bps": round(real_15m_bps, 1), "real_1h_bps": round(real_1h_bps, 1),
            "kronos_5m_bps": round(k5m, 1), "kronos_10m_bps": round(k10m, 1), "kronos_1h_bps": round(k1h, 1),
            "kronos_2h_bps": round(k2h, 1), "kronos_6h_bps": round(k6h, 1), "kronos_12h_bps": round(k12h, 1), "kronos_24h_bps": round(k24h, 1), "kronos_48h_bps": k48h,
            "allowed_direction": allowed_dir,
        })
    # TRE OS v35 Capital Allocation Rule (Mandatory Split: reserve_usdc = 125.00 untouchable, operational_capital_usdc = realized equity - 125.00):
    # Rule 1, 2, 3: Never include reserve_usdc (125.00) or unrealized_total_usd in operational_capital_usdc or slot sizing!
    realized_total_equity_usdc = round((real_nav - unrealized_total_usd) if (live_mode and real_nav >= RESERVE_FLOOR_USDC) else max(RESERVE_FLOOR_USDC, REFERENCE_NAV_USDC + realized_pnl), 4)
    cap_book = CapitalAllocationBook(initial_total_equity_usdc=realized_total_equity_usdc, reserve_floor_usdc=RESERVE_FLOOR_USDC)
    cap_book.set_unrealized_pnl(unrealized_total_usd)
    cap_book.state.fees_usdc = round(tot_fees, 4)
    cap_book.state.realized_net_pnl_usdc = round(realized_pnl, 4)
    cap_book.state.assert_invariants()
    reserve_usdc = cap_book.state.reserve_usdc
    operational_capital_usdc = cap_book.state.operational_capital_usdc
    total_equity_usdc = cap_book.state.total_equity_usdc
    live_nav_est = round(total_equity_usdc, 2)
    # Rule 2: Available margin is strictly operational_capital_usdc minus locked_margin (reserve 125 USDC is NEVER included in free_mgn)!
    free_mgn = round(max(0.0, operational_capital_usdc - locked_margin_total_usd), 4)
    portfolio_dd_pct = ((total_equity_usdc - REFERENCE_NAV_USDC) / REFERENCE_NAV_USDC * 100.0) if REFERENCE_NAV_USDC > 0 else 0.0
    circuit_breaker_tripped = bool(portfolio_dd_pct <= -8.0 or operational_capital_usdc <= 0.0)
    # Rule 1: All new positions are sized strictly from operational_capital_usdc (NEVER live_nav_est / total_equity_usdc)!
    slot_margin_usd = round(operational_capital_usdc * SLOT_NAV_PCT, 2)
    wc_safe_hold = False
    # TRE OS v31.0 Condition #3 (NO AUTOMATIC SLOT-MACHINE RE-ENTRY — MANDATORY PRE/DURING/POST ANALYSIS):
    # 1) Never open a new position in the same cycle a position just closed (len(actions_taken) > 0) -> force Post-Trade Gemini Audit first!
    # 2) Enforce a mandatory Post-Close Market Observation & Decompression Window (6 mins after a win/shield, 15 mins after a stop-loss) so the engine NEVER fires blindly right after closing!
    # 3) Require Pre-Trade 2-Cycle Structural Confirmation (_PRE_TRADE_CONFIRM_MAP): a candidate must prove sustained flow across 2 consecutive cycles with improving/holding price before engaging!
    just_closed_this_cycle = any(a.get("action", "").startswith("CLOSED_") for a in actions_taken)
    cur.execute("SELECT status, (julianday('now') - julianday(closed_at)) * 1440.0 FROM futures_demo_positions WHERE status != 'OPEN' AND closed_at IS NOT NULL ORDER BY closed_at DESC LIMIT 1")
    last_closed_row = cur.fetchone()
    post_close_pause_active = False
    if last_closed_row and last_closed_row[1] is not None:
        last_st_c, mins_since_last_close = str(last_closed_row[0]), float(last_closed_row[1])
        req_pause_mins = 8.0 if last_st_c == "CLOSED_STOPLOSS" else 4.0
        if mins_since_last_close < req_pause_mins:
            post_close_pause_active = True
    # TRE OS v32.1 Smart Pre-Trade Confirmation: confirm either via 2 cycles OR immediately when score >= 38.0 (strong multi-horizon Kronos + OFI + candle body)!
    confirmed_candidates = []
    for c_item in candidates:
        cid_k, cdir_k, cpx_k = c_item["inst_id"], c_item["dir"], float(c_item["px"])
        prev_c = _PRE_TRADE_CONFIRM_MAP.get(cid_k)
        cnt_c = (prev_c[1] + 1) if (prev_c and prev_c[0] == cdir_k) else 1
        first_px_c = prev_c[2] if (prev_c and prev_c[0] == cdir_k) else cpx_k
        _PRE_TRADE_CONFIRM_MAP[cid_k] = (cdir_k, cnt_c, first_px_c)
        px_confirmed = bool((cdir_k == "LONG" and cpx_k >= first_px_c * 0.9995) or (cdir_k == "SHORT" and cpx_k <= first_px_c * 1.0005))
        if (cnt_c >= 2 and px_confirmed and c_item["score"] >= 26.0) or c_item["score"] >= 38.0:
            confirmed_candidates.append(c_item)
    # v35 is authoritative for new entries. The pre-v35 selector may still be
    # useful for diagnostics, but it cannot open a Paper/live position unless
    # the calibrated EV gate and policy supervisor both approve it.
    abc_ledger_init = ParallelShadowABCLedger(conn, initial_total_equity_usdc=total_equity_usdc)
    cur.execute("SELECT payload FROM variant_events WHERE event_type IN ('OPEN_POSITION', 'SHADOW_G2_ADDON') ORDER BY id DESC LIMIT 20")
    recent_ev_values = []
    for (ev_payload,) in cur.fetchall():
        try:
            payload_ev = json.loads(ev_payload)
            if "ev_net_bps" in payload_ev:
                recent_ev_values.append(float(payload_ev["ev_net_bps"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    recent_ev_values.sort()
    median_ev_net_last_20 = (
        recent_ev_values[len(recent_ev_values) // 2]
        if len(recent_ev_values) % 2
        else ((recent_ev_values[len(recent_ev_values) // 2 - 1] + recent_ev_values[len(recent_ev_values) // 2]) / 2.0 if recent_ev_values else 0.0)
    )
    entry_policy = _POLICY_SUPERVISOR.evaluate_policy(
        brain_skills,
        fee_drag_pct,
        0,
        median_ev_net_last_20,
        calibration_ece_pct=4.2,
    )
    candidates = []
    for c_item in confirmed_candidates:
        ev_gate = v35_entry_gates.get((c_item["inst_id"], c_item["dir"]))
        vfc_gate = v35_forecasts.get(c_item["inst_id"])
        if ev_gate is None or vfc_gate is None or not vfc_gate.entry_valid or not ev_gate.paper_authorized:
            continue
        policy_ok, policy_reason = _POLICY_SUPERVISOR.check_candidate_matches_policy(
            entry_policy,
            c_item["dir"],
            vfc_gate,
            float(next((row.get("real_15m_bps", 0.0) for row in telemetry_rows if row.get("inst_id") == c_item["inst_id"]), 0.0)),
            float(next((row.get("real_1h_bps", 0.0) for row in telemetry_rows if row.get("inst_id") == c_item["inst_id"]), 0.0)),
            float(next((row.get("ofi_norm", 0.0) for row in telemetry_rows if row.get("inst_id") == c_item["inst_id"]), 0.0)),
            float(next((row.get("spread_bps", 0.0) for row in telemetry_rows if row.get("inst_id") == c_item["inst_id"]), 0.0)),
            float(next((row.get("atr_1h_bps", 55.0) for row in telemetry_rows if row.get("inst_id") == c_item["inst_id"]), 55.0)),
            0.0,
            50.0,
            ev_gate,
        )
        if policy_ok:
            c_item["v35_ev_net_bps"] = ev_gate.ev_net_bps
            c_item["v35_policy"] = entry_policy.policy
            candidates.append(c_item)
    if LEGACY_ENTRY_EXECUTION and not circuit_breaker_tripped and not wc_safe_hold and not just_closed_this_cycle and not post_close_pause_active and len(open_positions) < MAX_SLOTS and free_mgn >= slot_margin_usd and candidates:
        candidates.sort(key=lambda x: x["score"], reverse=True)
        for cand in candidates:
            if len(open_positions) >= MAX_SLOTS or free_mgn < slot_margin_usd: break
            c_id, c_dir, c_px, c_dec = cand["inst_id"], cand["dir"], cand["px"], cand["dec_px"]
            eff_lev = max(2.2, min(2.5, float(brain_skills.get("dynamic_slot_leverage") or LEVERAGE)))
            # Proposal 2: ATR Risk-Locked Sizing (keep dollar risk at SL strictly locked at ~$0.85 USDC regardless of ATR width!)
            cand_sl_bps = float(cand.get("sl_bps") or round(80.0 * float(cand.get("vol_mult") or 1.0), 1))
            cur.execute("SELECT COUNT(*) FROM futures_demo_positions WHERE inst_id=? AND opened_at >= ?", (c_id, now_iso[:10]))
            same_coin_today_cnt = int((cur.fetchone() or [0])[0])
            ctx_size_mult = 0.78 if same_coin_today_cnt >= 2 else 1.0
            # TRE OS v30.0 Two-Stage Engagement: Phase 0 enters as an agile Probe (~$62 USDC = 62% of base slot), risking max -$0.15..-$0.30 on false starts,
            # and deploys heavy capital (+$125 USDC at 3x -> ~$187 USDC) ONLY once confirmed at Phase 2 (+66 bps)!
            base_target_notional = round(slot_margin_usd * eff_lev * 0.62 * ctx_size_mult, 2)
            target_notional = round(min(68.0, max(56.0, base_target_notional)), 2)
            sz_str, actual_notional = _calc_contract_sz(c_id, target_notional, c_px)
            actual_margin = round(actual_notional / eff_lev, 2)
            if actual_margin > free_mgn: continue
            # Option A Perfected (v25.5): Max 1 unshielded slot (< G2) at a time; Slot #2 opens ONLY when Slot #1 is in G2/G3 Free-Roll
            # AND (Candidate #2 is in a Decorrelated Sector TradFi/Crypto OR Slot #1 reached G2 early <= 35 mins)!
            if len(live_okx_pend) >= 1:
                break
            if len(open_positions) >= 1:
                p1_row = list(open_positions.values())[0]
                p1_inst, p1_shield, p1_open_ts = str(p1_row[1]), int(p1_row[10] or 0), str(p1_row[12] or "")
                p1_is_tradfi = bool(p1_inst.split("-")[0] in tradfi_coins)
                c_is_tradfi = bool(c_id.split("-")[0] in tradfi_coins)
                # TRE OS v30.0 Strict Rule R03 Restored: NEVER open a 2nd position while Slot #1 is still unshielded (< G2)!
                if p1_shield < 2:
                    break
                try:
                    p1_age_m = (now_dt - datetime.datetime.fromisoformat(p1_open_ts.replace("Z", "+00:00"))).total_seconds() / 60.0
                except Exception:
                    p1_age_m = 999.0
                if not ((p1_is_tradfi != c_is_tradfi) or (p1_age_m <= 35.0)):
                    continue
            active_strat = str(brain_skills.get("strategy_mode") or "TREND_SWING_RUNNER")
            cur.execute("SELECT realized_pnl_usd FROM futures_demo_positions WHERE status != 'OPEN' AND realized_pnl_usd IS NOT NULL ORDER BY closed_at DESC LIMIT 3")
            last3_pnls = [float(r[0]) for r in cur.fetchall()]
            if len(last3_pnls) >= 2 and sum(last3_pnls[:2]) <= -0.80:
                active_strat = "SNIPER_PULLBACK_LIMIT"
            # Top-of-book post_only Maker (bids[0][0] / asks[0][0]) so order fills within 1.2s without cancel-loop bug
            vm = float(cand.get("vol_mult") or 1.0)
            tp_bps_dyn = round(600.0 * vm, 1) / 10000.0
            sl_bps_dyn = round(cand_sl_bps, 1) / 10000.0
            tp_px = round(c_px * (1.0 + tp_bps_dyn), c_dec) if c_dir == "LONG" else round(c_px * (1.0 - tp_bps_dyn), c_dec)
            sl_px = round(c_px * (1.0 - sl_bps_dyn), c_dec) if c_dir == "LONG" else round(c_px * (1.0 + sl_bps_dyn), c_dec)
            if live_mode:
                if c_id in live_okx_pend or c_id in live_okx_pos:
                    continue
                # Always enforce 2x isolated leverage on initial Tier 1 entry (even if previous trade on this coin scaled to 3x in Tier 2/3)!
                try:
                    _OKX_CLIENT._request("POST", "/api/v5/account/set-leverage", body_dict={"instId": c_id, "lever": "2", "mgnMode": "isolated"}, auth=True)
                except Exception:
                    pass
                side = "buy" if c_dir == "LONG" else "sell"
                ok = _execute_live_xperp_order(c_id, side, sz_str, c_px, c_dec, reduce_only=False, urgent_stop=False, tp_px=tp_px, sl_px=sl_px)
                if not ok: continue
                # Do NOT insert into futures_demo_positions until the post_only order actually fills on OKX (live_okx_pos)!
                live_okx_pend.add(c_id)
                free_mgn = round(free_mgn - actual_margin, 4)
                actions_taken.append({"action": f"PLACE_POST_ONLY_{c_dir}_4.0X", "inst_id": c_id, "px": c_px, "sz_contracts": sz_str, "margin_usd": actual_margin, "notional_usd": actual_notional})
                break
            entry_fee_usd = round(actual_notional * MAKER_FEE_RATE, 4)
            pos_id = f"XPERP_{c_id.split('-')[0]}_{int(time.time()*1000)}"
            cur.execute("INSERT INTO futures_demo_positions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0, ?, 'OPEN', ?, NULL, NULL, NULL)",
                        (pos_id, c_id, c_dir, LEVERAGE, actual_margin, actual_notional, c_px, c_px, tp_px, sl_px, entry_fee_usd, now_iso))
            free_mgn = round(free_mgn - actual_margin, 4)
            locked_margin_total_usd += actual_margin
            open_positions[c_id] = (pos_id, c_id, c_dir, LEVERAGE, actual_margin, actual_notional, c_px, tp_px, sl_px, 0.0, 0, entry_fee_usd, now_iso)
            actions_taken.append({"action": f"OPEN_{c_dir}_4.0X", "inst_id": c_id, "px": c_px, "sz_contracts": sz_str, "margin_usd": actual_margin, "notional_usd": actual_notional})
    curr_nav = live_nav_est
    if live_mode and _OKX_CLIENT.is_authenticated:
        try:
            h_ords = _OKX_CLIENT._request("GET", "/api/v5/trade/orders-history?instType=FUTURES&limit=60", auth=True).get("data", [])
            filled_ords = [o for o in h_ords if o.get("state") == "filled" and int(o.get("cTime") or 0) >= 1793362800000]
            if filled_ords:
                tot_fees = round(sum(abs(float(o.get("fee") or 0.0)) for o in filled_ords), 4)
                gross_p = sum(float(o.get("pnl") or 0.0) for o in filled_ords)
                realized_pnl = round(gross_p - tot_fees, 4)
                close_ords = [o for o in filled_ords if str(o.get("reduceOnly", "")).lower() == "true"]
                shields_cnt = sum(1 for o in close_ords if float(o.get("pnl") or 0.0) > 0.0)
                stops_cnt = sum(1 for o in close_ords if float(o.get("pnl") or 0.0) <= 0.0)
        except Exception:
            pass
    cur.execute("UPDATE futures_demo_account SET current_nav_usd=?, free_margin_usd=?, realized_pnl_usd=?, total_fees_usd=?, wins_count=?, stops_count=?, shield_locks_count=?, updated_at=? WHERE id=1",
                (curr_nav, round(free_mgn, 2), round(realized_pnl, 4), round(tot_fees, 4), wins_cnt, stops_cnt, shields_cnt, now_iso))
    conn.commit()
    gross_prof_live = max(0.01, realized_pnl + tot_fees) if realized_pnl > 0 else 1.0
    fee_drag_pct = round((tot_fees / gross_prof_live) * 100.0, 2) if tot_fees > 0 else 0.0
    # Constant 60-Second Gemini Co-Pilot: call Gemini every 60s (or on any trade event after 30s)
    # Master Word Clock Slave /40 (every 10m = 144 RPD max) or on real trade execution (min 120s spacing) -> zero 429 errors!
    event_trigger = bool(len(actions_taken) > 0)
    should_audit = bool(run_audit or (time.time() - _LAST_GEMINI_AUDIT_TS) >= 240.0 or (event_trigger and (time.time() - _LAST_GEMINI_AUDIT_TS) >= 90.0))
    if should_audit:
        aud_res = run_gemini_ordinary_futures_audit(conn, curr_nav, telemetry_rows)
        aud_model, aud_verdict, fee_drag_pct = aud_res["model_used"], aud_res["verdict"], aud_res["fee_drag_ratio_pct"]
    cur.execute("SELECT pos_id, inst_id, direction, margin_usd, notional_usd, entry_px, current_px, tp_px, sl_px, peak_move_bps, shield_armed, opened_at FROM futures_demo_positions WHERE status='OPEN'")
    active_pos_list = [{"pos_id": r[0], "inst_id": r[1], "direction": r[2], "margin_usd": r[3], "notional_usd": r[4], "entry_px": r[5], "current_px": r[6], "tp_px": r[7], "sl_px": r[8], "peak_move_bps": round(float(r[9]), 1), "shield_armed": bool(r[10]), "opened_at": r[11]} for r in cur.fetchall()]
    # Luna Spec Step 5-8: Step Parallel Shadow A/B/C Ledger on the exact same market cycle & compute EV/Policy telemetry!
    shadow_abc_scoreboard = {}
    try:
        abc_ledger = ParallelShadowABCLedger(conn)
        pol_obj = _POLICY_SUPERVISOR.evaluate_policy(brain_skills, fee_drag_pct, 0, median_ev_net_last_20)
        top_c_dir = candidates[0]["dir"] if candidates else "NEUTRAL"
        top_c_id = candidates[0]["inst_id"] if candidates else "BTC-USD_UM_XPERP-310404"
        for inst_id, bids, asks, trades, real_15m_bps, real_1h_bps, real_48h_bps, atr_1h_bps, oi_delta_bps, funding_bps in market_snaps[:14]:
            if not bids or not asks: continue
            meta_s = FUTURES_UNIVERSE[inst_id]
            mid_s = 0.5 * (bids[0][0] + asks[0][0])
            sp_s = (asks[0][0] - bids[0][0]) / max(1e-9, mid_s) * 10000.0
            raw_fc_s = kronos_map.get(meta_s["spot_id"]) or kronos_map.get(inst_id)
            vfc_s = _KRONOS_VALIDATOR.validate(inst_id, raw_fc_s, mid_s, float(getattr(raw_fc_s, "last_close", 0.0) or 0.0) if raw_fc_s else 0.0)
            telemetry_s = next((r for r in telemetry_rows if r.get("inst_id") == inst_id), {})
            ofi_s = float(telemetry_s.get("ofi_norm") or 0.0)
            ev_l = _EV_ENGINE.evaluate(inst_id, "LONG", vfc_s, ofi_s, sp_s, atr_1h_bps, real_15m_bps, real_1h_bps, macro_regime, is_us_session)
            ev_s = _EV_ENGINE.evaluate(inst_id, "SHORT", vfc_s, ofi_s, sp_s, atr_1h_bps, real_15m_bps, real_1h_bps, macro_regime, is_us_session)
            cand_d_s = top_c_dir if inst_id == top_c_id else "NEUTRAL"
            shadow_abc_scoreboard = abc_ledger.step_all_variants(
                f"snap_{int(time.time())}_{inst_id.split('-')[0]}",
                now_iso,
                inst_id,
                meta_s,
                mid_s,
                bids[0][0],
                asks[0][0],
                sp_s,
                atr_1h_bps,
                ofi_s,
                oi_delta_bps,
                mid_s,
                vfc_s,
                ev_l,
                ev_s,
                pol_obj,
                cand_d_s,
                round(slot_margin_usd * LEVERAGE, 2),
                trades=trades,
            )
        shadow_abc_scoreboard = abc_ledger.get_scoreboard()
    except Exception:
        pass
    snap = {
        "timestamp": now_iso, "execution_mode": "LIVE_XPERP_2.5X" if live_mode else "DEMO_2.5X", "baseline_nav_usd": base_nav,
        "luna_v35_shadow_abc_scoreboard": shadow_abc_scoreboard,
        "luna_v35_ev_calibration": _EV_ENGINE.calibration_report,
        "luna_v35_entry_policy": {"policy": entry_policy.policy, "valid_until": entry_policy.valid_until, "reason_codes": entry_policy.reason_codes, "median_ev_net_last_20": median_ev_net_last_20},
        "historical_22oct_sim_nav_usd": round(HISTORICAL_22OCT_SIM_NAV_USDC + (curr_nav - base_nav), 2),
        "reserve_usdc": reserve_usdc,
        "operational_capital_usdc": operational_capital_usdc,
        "total_equity_usdc": total_equity_usdc,
        "realized_net_pnl_usdc": round(realized_pnl, 4),
        "fees_usdc": round(tot_fees, 4),
        "current_nav_usd": curr_nav, "free_margin_usd": round(free_mgn, 2), "locked_margin_usd": round(locked_margin_total_usd, 2),
        "realized_pnl_usd": round(realized_pnl, 4), "unrealized_pnl_usd": round(unrealized_total_usd, 3),
        "total_fees_usd": round(tot_fees, 4), "fee_drag_ratio_pct": fee_drag_pct,
        "wins_count": wins_cnt, "shield_locks_count": shields_cnt, "stops_count": stops_cnt,
        "macro_regime": macro_regime, "us_session_active": is_us_session,
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
    word_clock = MasterWordClock()
    import subprocess
    while True:
        t0_ms = time.time() * 1000.0
        slaves_fired = ["SLAVE_1X_L2_CHANDELIER"]
        pyr_tier = 0
        try:
            s = run_futures_demo_cycle(conn, micro, kronos, run_audit=((word_clock.frame_id + 1) % 20 == 0), live_mode=live_mode)
            cur_c = conn.cursor()
            cur_c.execute("SELECT MAX(shield_armed) FROM futures_demo_positions WHERE status='OPEN'")
            r_t = cur_c.fetchone()
            pyr_tier = int(r_t[0] or 0) if r_t else 0
            if (word_clock.frame_id + 1) % 20 == 0:
                slaves_fired.append("SLAVE_5M_257_SCANNER_AND_GEMINI")
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            if now_utc.minute == 0 and now_utc.hour != word_clock.last_hour_dispatched:
                word_clock.last_hour_dispatched = now_utc.hour
                slaves_fired.append("SLAVE_1H_GUARDIAN_GSHEET_TELEGRAM")
                if now_utc.hour % 3 == 0:
                    slaves_fired.append("SLAVE_3H_DEEP_SUBAGENT_AUDIT")
                subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "scripts", "hourly_autonomous_guardian.py")])
            if now_utc.minute == 2 and now_utc.hour in (8, 20) and now_utc.hour != word_clock.last_12h_dispatched:
                word_clock.last_12h_dispatched = now_utc.hour
                slaves_fired.append("SLAVE_12H_PROACTIVE_VPN_PROPOSAL")
                subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "scripts", "gemini_vpn_agent.py"), "--notify", "PROACTIVE_12H_RD_AND_MISSED_WAVES_PROPOSAL"])
        except Exception as e:
            print(f"[!] Futures Engine cycle error: {e}")
        dur_ms = (time.time() * 1000.0) - t0_ms
        word_clock.advance_frame_and_persist(pyr_tier, dur_ms, slaves_fired)
        word_clock.wait_for_next_phase_locked_beat(pyr_tier)

if __name__ == "__main__":
    main()
