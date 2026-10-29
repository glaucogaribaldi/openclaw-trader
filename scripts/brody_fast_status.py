#!/usr/bin/env python3
"""
TRE OS v8.1 (Sovereign Predator) — Instant 1-Shot Executive & Diagnostic Query (`scripts/brody_fast_status.py`)
Designed for AI models (Lehman Brody / OpenClaw / Sub-Agents) to inspect the entire live state of `brody`
in < 150ms from cached JSON/SQLite WAL without triggering a redundant 15s cycle, OR with `--live` to run
both a live Predator cycle and Telegram report in one shot.
"""
import argparse
import json
import os
import sqlite3
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "config", "okx_trader.db")
SNAP_PATH = os.path.join(BASE_DIR, "config", "predator_live_snapshot.json")
AUDIT_PATH = os.path.join(BASE_DIR, "config", "predator_audit_report.json")
LLM_PATH = os.path.join(BASE_DIR, "config", "predator_llm_directive.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="TRE OS v8.1 Instant 1-Shot Status & Report Tool")
    parser.add_argument("--live", action="store_true", help="Run a fresh predator_daemon --once --live --audit cycle + telegram_reporter first")
    args = parser.parse_args()

    if args.live:
        r1 = subprocess.run(
            [os.path.join(BASE_DIR, "venv/bin/python"), os.path.join(BASE_DIR, "predator_daemon.py"), "--once", "--live", "--audit"],
            capture_output=True, text=True
        )
        print(r1.stdout)
        r2 = subprocess.run(
            [os.path.join(BASE_DIR, "venv/bin/python"), os.path.join(BASE_DIR, "scripts/telegram_reporter.py")],
            capture_output=True, text=True
        )
        print(r2.stdout)

    snap = json.load(open(SNAP_PATH)) if os.path.exists(SNAP_PATH) else {}
    ld = json.load(open(LLM_PATH)) if os.path.exists(LLM_PATH) else {}

    print(f"=== SNAPSHOT ({snap.get('timestamp')}) | NAV=${snap.get('nav_usdc')} | Free=${snap.get('free_usdc')} | BTC_Radar={snap.get('btc_lead_lag_bps')}bps | GlobalRegime={ld.get('global_regime')} ({ld.get('aggressiveness_multiplier')}x) ===")
    for t in sorted(snap.get("telemetry", []), key=lambda x: x.get("opp_score", 0), reverse=True):
        print(
            f"  {t['inst_id']:<12} | Mid=${t['mid_price']:<8} | Avg=${t['open_avg_px']:<8} | Fl=${t.get('cost_basis_floor_px',0):<8} | "
            f"OFI={t['ofi_norm']:>+5.2f} VPIN={t['vpin_toxicity']:<4.2f} | K1h={t['kronos_1h_bps']:>+5.1f} 2h={t.get('kronos_2h_bps',0):>+5.1f} 6h={t.get('kronos_6h_bps',0):>+5.1f} 12h={t.get('kronos_12h_bps',0):>+6.1f} 24h={t.get('kronos_24h_bps',0):>+6.1f} | "
            f"Pred={t['predicted_return_bps']:>+6.2f} | Opp={t['opp_score']:>+6.2f} | {t['regime']:<18} | BuyPx={t.get('active_buy_px')} SellPx={t.get('active_sell_px')}"
        )

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=3.0)
    cur = conn.cursor()
    print("=== LATEST 10 FILLS (predator_fills_ledger) ===")
    cur.execute("SELECT fill_time, inst_id, side, fill_px, fill_sz, notional_usd, realized_pnl_usd FROM predator_fills_ledger ORDER BY fill_time DESC LIMIT 10")
    for r in cur.fetchall():
        print(" ", r)

    print("=== ACTIVE / RECENT QUICK-SCALP TRANCHES (fresh_scalp_tranches) ===")
    cur.execute("SELECT trade_id, inst_id, buy_px, buy_sz, tp_ord_id, tp_px, status, created_at FROM fresh_scalp_tranches ORDER BY created_at DESC LIMIT 8")
    for r in cur.fetchall():
        print(" ", r)
    conn.close()


if __name__ == "__main__":
    main()
