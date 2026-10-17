#!/usr/bin/env python3
"""
OKX Simple Earn / Flexible Savings Helper (10% Bonus APR Tracker)
Monitors idle USDC cash and tracks passive interest accrued on unallocated balance.
"""
import os, sys, json, subprocess, time

BASE_DIR = "/home/zavattoni_giacomo/openclaw-trader"

def check_savings_balance():
    try:
        res = subprocess.run(["okx", "--profile", "democlaw", "account", "balance", "--json"], capture_output=True, text=True, timeout=8)
        data = json.loads(res.stdout)
        usdc_avail = 0.0
        if isinstance(data, list) and len(data) > 0 and 'details' in data[0]:
            for b in data[0]['details']:
                if b.get('ccy') == 'USDC':
                    usdc_avail = float(b.get('availBal') or 0.0)
        
        # Calculate estimated 10% APR passive yield on idle cash
        est_daily_yield = (usdc_avail * 0.10) / 365.0
        return {
            "status": "active",
            "idle_usdc_avail": usdc_avail,
            "bonus_apr_pct": 10.0,
            "est_daily_yield_usdc": round(est_daily_yield, 4),
            "est_annual_yield_usdc": round(usdc_avail * 0.10, 2)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    info = check_savings_balance()
    print(f"=== OKX SIMPLE EARN FLEXIBLE TRACKER ===")
    print(f"Idle USDC Cash: ${info.get('idle_usdc_avail', 0):.2f} USDC")
    print(f"Bonus APR: {info.get('bonus_apr_pct', 10)}%")
    print(f"Est. Daily Passive Yield: +${info.get('est_daily_yield_usdc', 0):.4f} USDC/giorno")
