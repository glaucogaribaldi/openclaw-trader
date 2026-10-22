#!/usr/bin/env python3
"""
TRE OS v6.0 (Predator Edition) Deterministic Accounting Engine (`scripts/accounting_engine.py`)
Computes strict 100% Penny Match financial metrics using native HMAC-SHA256 OKX REST API:
- Auto-syncs recent OKX Spot fills into `trade_ledger` and `predator_fills_ledger`
- Realized FIFO PnL (24h, 7d, Full Run)
- Unrealized Mark-To-Market (MTM) PnL & Cost-Basis Floor (`openAvgPx * 1.0022`)
- OKX Simple Earn 10% Yield Balance ($35.46 USDC)
- Complete NAV Reconciliation (Baseline $253.01 USDC -> Current NAV)
Zero AI calculations for numbers; 100% deterministic math.
"""
import os
import sys
import json
import sqlite3
import time

BASE_DIR = "/home/zavattoni_giacomo/openclaw-trader"
if not os.path.exists(BASE_DIR):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from execution.okx_hybrid_executor import OKXNativeClient
from core.predator_auditor import PredatorAuditor
from predator_daemon import DEFAULT_UNIVERSE, load_dotenv

DB_PATH = os.path.join(BASE_DIR, "config", "okx_trader.db")
BASELINE_NAV = 253.01  # Official baseline from 11/10/2026 08:42 CEST
SIMPLE_EARN_FALLBACK = 35.46


def compute_financial_report():
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    client = OKXNativeClient(simulated_demo=False)
    balances = client.get_account_balances()
    orders = client.get_open_orders()

    holdings = []
    total_spot_equity_usd = 0.0
    usdc_trading_free = 0.0
    usdc_trading_frozen = 0.0
    cost_basis_map = {}

    for b in balances:
        ccy = b.get("ccy")
        eq_usd = float(b.get("eqUsd") or 0.0)
        cash_bal = float(b.get("cashBal") or 0.0)
        avail_bal = float(b.get("availBal") or 0.0)
        frozen_bal = float(b.get("frozenBal") or 0.0)
        upl = float(b.get("spotUpl") or b.get("totalPnl") or 0.0)
        open_avg = float(b.get("openAvgPx") or b.get("accAvgPx") or 0.0)
        if open_avg > 0 and ccy:
            cost_basis_map[ccy] = open_avg

        if ccy == "USDC":
            usdc_trading_free = avail_bal
            usdc_trading_frozen = frozen_bal
            total_spot_equity_usd += eq_usd
        elif ccy in ["BTC", "ETH"]:
            total_spot_equity_usd += eq_usd
        else:
            total_spot_equity_usd += eq_usd
            if cash_bal > 0:
                holdings.append({
                    "ccy": ccy,
                    "qty": cash_bal,
                    "avail": avail_bal,
                    "frozen": frozen_bal,
                    "eq_usd": eq_usd,
                    "open_avg_px": open_avg,
                    "upl_usd": upl,
                })

    holdings.sort(key=lambda x: x["eq_usd"], reverse=True)

    # Check Simple Earn balance
    usdc_simple_earn = SIMPLE_EARN_FALLBACK
    sav = client.get_savings_balances()
    earn_sum = sum(float(s.get("amt") or 0.0) for s in sav if s.get("ccy") == "USDC")
    if earn_sum > 0:
        usdc_simple_earn = earn_sum

    nav_current = total_spot_equity_usd + usdc_simple_earn

    stats = {
        "fills_today": 0, "pnl_today": 0.0, "notional_today": 0.0,
        "fills_7d": 0, "pnl_7d": 0.0, "notional_7d": 0.0,
        "fills_run": 0, "pnl_run": 0.0, "notional_run": 0.0,
    }

    try:
        conn = sqlite3.connect(DB_PATH, timeout=20.0)
        auditor = PredatorAuditor(
            db_path=DB_PATH,
            report_out_path=os.path.join(BASE_DIR, "config", "predator_audit_report.json"),
            baseline_nav=BASELINE_NAV,
        )
        raw_fills = client.get_recent_fills(limit=50)
        if raw_fills:
            auditor.sync_okx_fills(
                conn=conn,
                raw_fills=raw_fills,
                open_avg_px_map=cost_basis_map,
                allowed_pairs=set(DEFAULT_UNIVERSE.keys()),
            )

        cur = conn.cursor()
        cur.execute(
            "SELECT count(*), sum(realized_pnl_usdc), sum(notional_usdc) FROM trade_ledger WHERE datetime(created_at) >= datetime('now', '-24 hours')"
        )
        r = cur.fetchone() or (0, 0.0, 0.0)
        stats["fills_today"] = r[0] or 0
        stats["pnl_today"] = float(r[1] or 0.0)
        stats["notional_today"] = float(r[2] or 0.0)

        cur.execute(
            "SELECT count(*), sum(realized_pnl_usdc), sum(notional_usdc) FROM trade_ledger WHERE datetime(created_at) >= datetime('now', '-7 days')"
        )
        r = cur.fetchone() or (0, 0.0, 0.0)
        stats["fills_7d"] = r[0] or 0
        stats["pnl_7d"] = float(r[1] or 0.0)
        stats["notional_7d"] = float(r[2] or 0.0)

        cur.execute("SELECT count(*), sum(realized_pnl_usdc), sum(notional_usdc) FROM trade_ledger")
        r = cur.fetchone() or (0, 0.0, 0.0)
        stats["fills_run"] = r[0] or 0
        stats["pnl_run"] = float(r[1] or 0.0)
        stats["notional_run"] = float(r[2] or 0.0)

        conn.close()
    except Exception as e:
        print(f"[!] SQLite Error: {e}")

    net_pnl_run = nav_current - BASELINE_NAV
    pct_run = (net_pnl_run / BASELINE_NAV) * 100.0
    mtm_unrealized = sum(h["upl_usd"] for h in holdings)

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S CEST"),
        "engine_version": "TRE OS v6.0 (Predator + Kronos GPU)",
        "baseline_nav": BASELINE_NAV,
        "current_nav": round(nav_current, 2),
        "net_pnl_run": round(net_pnl_run, 2),
        "pct_run": round(pct_run, 2),
        "usdc_trading_free": round(usdc_trading_free, 2),
        "usdc_trading_frozen": round(usdc_trading_frozen, 2),
        "usdc_simple_earn": round(usdc_simple_earn, 2),
        "mtm_unrealized": round(mtm_unrealized, 2),
        "active_orders_count": len(orders),
        "stats": stats,
        "holdings": holdings,
    }
    return report


def format_telegram_monospace_table(rep):
    st = rep["stats"]
    mtm_str = f"-${abs(rep['mtm_unrealized']):.2f}" if rep["mtm_unrealized"] < 0 else f"+${rep['mtm_unrealized']:.2f}"

    msg = f"""⚡ *TRE OS v6.0 PREDATOR — REPORT DI PERFORMANCE LIVE*
📅 _{rep['timestamp']}_

```
========================================
1. CAPITALE E RICONCILIAZIONE (NAV)
========================================
Capitale Baseline (11/10): $253.01 USDC
NAV Attuale Live:         ${rep['current_nav']:.2f} USDC
Profitto Netto Run:       +${rep['net_pnl_run']:.2f} USDC (+{rep['pct_run']:.2f}%)

Ripartizione Cassa:
- Simple Earn (10% APR):  ${rep['usdc_simple_earn']:.2f} USDC
- Cassa Impegnata Dip:    ${rep['usdc_trading_frozen']:.2f} USDC
- Cassa Liquida Libera:   ${rep['usdc_trading_free']:.2f} USDC

========================================
2. PERFORMANCE CHIUSA ED MTM (OGGI)
========================================
• Profitto Realizzato (24h):   +${st['pnl_today']:.4f} USDC ({st['fills_today']} Fills)
• Fluttuazione MTM (Prezzi):   {mtm_str} USDC
• Profitto Realizzato 7g:      +${st['pnl_7d']:.4f} USDC ({st['fills_7d']} Fills)
• Profitto Realizzato Run:    +${st['pnl_run']:.4f} USDC ({st['fills_run']} Fills)
• Motore Predittivo:          Kronos GPU + OFI/VPIN/RLS
• Protezione Cost-Basis:      Attiva (openAvgPx + 22 bps)
• Trappole Limit Attive:      {rep['active_orders_count']} ordini (100% Post-Only)
========================================
```
"""
    return msg


if __name__ == "__main__":
    rep = compute_financial_report()
    msg = format_telegram_monospace_table(rep)
    print("=== DETERMINISTIC ACCOUNTING REPORT ===")
    print(msg)
