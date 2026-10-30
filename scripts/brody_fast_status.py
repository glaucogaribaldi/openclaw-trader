#!/usr/bin/env python3
"""
TRE OS v14.0 — Instant Live XPERP Perpetual Futures 2.5x Isolated Status Inspector (brody_fast_status.py)
"""
import json, os, sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_PATH = os.path.join(BASE_DIR, "config", "futures_demo_snapshot.json")
DB_PATH = os.path.join(BASE_DIR, "config", "okx_futures_demo.db")

if os.path.exists(SNAP_PATH):
    s = json.load(open(SNAP_PATH, encoding="utf-8"))
    print(f"=== TRE OS v14.0 ({s.get('execution_mode','LIVE_XPERP_2.5X')}) | {s.get('timestamp')} ===")
    print(f"NAV=$${s.get('current_nav_usd',0):.2f} USDC (Start=$${s.get('baseline_nav_usd',268.95):.2f} | Sim22Oct=$${s.get('historical_22oct_sim_nav_usd',298.89):.2f}) | FreeMgn=$${s.get('free_margin_usd',0):.2f} | LockedMgn=$${s.get('locked_margin_usd',0):.2f}")
    print(f"RealizedPnL=$${s.get('realized_pnl_usd',0):+.4f} | UnrPnL=$${s.get('unrealized_pnl_usd',0):+.3f} | Fees=$${s.get('total_fees_usd',0):.4f} (FeeDrag={s.get('fee_drag_ratio_pct',0):.2f}%) | Wins={s.get('wins_count',0)} Shields={s.get('shield_locks_count',0)} Stops={s.get('stops_count',0)}")
    print(f"Auditor={s.get('auditor_model')} -> {s.get('auditor_verdict')}")
    print("--- ACTIVE XPERP 2.5X ISOLATED POSITIONS ---")
    pos_list = s.get("open_positions", [])
    if not pos_list:
        print("  (0 open positions — 100% Free USDC Margin ready)")
    for p in pos_list:
        print(f"  [{p.get('direction')} 2.5x] {p.get('inst_id'):26s} | Mgn=$${p.get('margin_usd')} (Notional=$${p.get('notional_usd')}) | Entry=$${p.get('entry_px')} -> Now=$${p.get('current_px')} | TP=$${p.get('tp_px')} SL=$${p.get('sl_px')} | Peak={p.get('peak_move_bps'):+.1f}bps Shield={p.get('shield_armed')}")
    print("--- 7-HORIZON KRONOS + L2 OFI TELEMETRY (12 REGULATED XPERP CONTRACTS) ---")
    for t in s.get("telemetry", []):
        print(f"  {t.get('inst_id'):26s} | Mid=$${t.get('mid_price'):<9} | OFI={t.get('ofi_norm'):+.2f} VPIN={t.get('vpin_toxicity'):.2f} | K5m={t.get('kronos_5m_bps'):+5.1f} 10m={t.get('kronos_10m_bps'):+5.1f} 1h={t.get('kronos_1h_bps'):+5.1f} 2h={t.get('kronos_2h_bps'):+5.1f} 6h={t.get('kronos_6h_bps'):+6.1f} 12h={t.get('kronos_12h_bps'):+6.1f} 24h={t.get('kronos_24h_bps'):+6.1f} | Dir={t.get('allowed_direction')}")

if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    print("=== RECENT XPERP POSITIONS LEDGER (futures_demo_positions) ===")
    for r in c.execute("SELECT pos_id, inst_id, direction, margin_usd, entry_px, exit_px, realized_pnl_usd, status, opened_at, closed_at FROM futures_demo_positions ORDER BY opened_at DESC LIMIT 8"):
        print(" ", r)
