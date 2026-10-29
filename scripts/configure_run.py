#!/usr/bin/env python3
"""
TRE OS v12.0 — Universal Run Calibrator & Setup Wizard (scripts/configure_run.py)

Allows any human operator (interactive mode) OR any installing AI agent (non-interactive CLI flags)
to calibrate TRE OS v12.0 according to the user's exact portfolio size, risk tolerance,
expiration date (or perpetual mode), and API credentials — with zero hardcoded assumptions.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(BASE_DIR, "config", "purified_run_config.json")
ENV_PATH = os.path.join(BASE_DIR, ".env")


def _prompt(label: str, default: str) -> str:
    try:
        val = input(f"  • {label} [{default}]: ").strip()
        return val if val else default
    except EOFError:
        return default


def main() -> None:
    parser = argparse.ArgumentParser(description="TRE OS v12.0 — Universal Run Calibration Wizard")
    parser.add_argument("--non-interactive", action="store_true", help="Run without interactive prompts (for AI agents / CI)")
    parser.add_argument("--baseline-nav", type=str, default="AUTO", help="Starting capital in USDC, or AUTO to detect from live OKX wallet on first run")
    parser.add_argument("--expiry-iso", type=str, default="NONE", help="Target expiration ISO-8601 UTC (e.g. 2026-12-31T21:00:00Z) or NONE for perpetual")
    parser.add_argument("--cashout-days", type=float, default=6.0, help="Days before expiry to start 4-stage USDC cashout taper (default: 6.0)")
    parser.add_argument("--chamber1-pct", type=float, default=63.0, help="Chamber 1 Assault Sniper allocation %% of NAV (default: 63.0)")
    parser.add_argument("--max-loss-bps", type=float, default=-400.0, help="Hard Max-Loss Stop Cap in bps per position (default: -400.0 = -4.00%%)")
    parser.add_argument("--fast-shield-bps", type=float, default=38.0, help="Fast Break-Even + Profit Shield trigger in bps (default: 38.0 = +0.38%%)")
    parser.add_argument("--daily-min-pct", type=float, default=0.70, help="Daily compounding target minimum %% (default: 0.70)")
    parser.add_argument("--daily-max-pct", type=float, default=5.00, help="Daily compounding target maximum %% (default: 5.00)")
    args = parser.parse_args()

    os.makedirs(os.path.join(BASE_DIR, "config"), exist_ok=True)
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    now_ms = int(now_dt.timestamp() * 1000)

    if args.non_interactive:
        raw_nav = args.baseline_nav
        expiry_iso = args.expiry_iso.strip()
        cashout_days = float(args.cashout_days)
        c1_pct = max(10.0, min(95.0, float(args.chamber1_pct)))
        max_loss_bps = -abs(float(args.max_loss_bps))
        fast_shield_bps = abs(float(args.fast_shield_bps))
        d_min = float(args.daily_min_pct)
        d_max = float(args.daily_max_pct)
    else:
        print("======================================================================")
        print("  ⚡ TRE OS v12.0 — PORTFOLIO & RISK CALIBRATION WIZARD")
        print("======================================================================")
        raw_nav = _prompt("Starting Capital in USDC (or AUTO to read live OKX balance)", args.baseline_nav)
        expiry_iso = _prompt("Run Expiration Date ISO-8601 UTC (e.g. 2026-12-31T21:00:00Z or NONE for perpetual)", args.expiry_iso)
        cashout_days = float(_prompt("Cashout Taper Window in days before expiry", str(args.cashout_days)))
        c1_pct = max(10.0, min(95.0, float(_prompt("Chamber 1 (Assault Sniper) %% of capital", str(args.chamber1_pct)))))
        max_loss_bps = -abs(float(_prompt("Hard Max-Loss Cap in bps (e.g. -400 = -4.00%)", str(args.max_loss_bps))))
        fast_shield_bps = abs(float(_prompt("Fast Break-Even Shield trigger in bps (e.g. 38 = +0.38%)", str(args.fast_shield_bps))))
        d_min = float(_prompt("Target Daily Compounding Min %%", str(args.daily_min_pct)))
        d_max = float(_prompt("Target Daily Compounding Max %%", str(args.daily_max_pct)))

    auto_init_nav = str(raw_nav).strip().upper() in ("AUTO", "0", "")
    baseline_val = 0.0 if auto_init_nav else float(raw_nav)

    cfg = {
        "baseline_nav_usdc": baseline_val,
        "auto_detect_baseline_on_start": auto_init_nav,
        "run_start_iso": now_iso,
        "run_start_ts_ms": now_ms,
        "purified_two_chamber_mode": True,
        "expiry_iso": expiry_iso,
        "cashout_taper_days": cashout_days,
        "chamber1_assault_pct": round(c1_pct / 100.0, 4),
        "chamber2_shield_pct": round((100.0 - c1_pct) / 100.0, 4),
        "max_loss_cap_bps": max_loss_bps,
        "fast_shield_trigger_bps": fast_shield_bps,
        "daily_min_pct": d_min,
        "daily_max_pct": d_max,
    }
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    if not os.path.exists(ENV_PATH):
        example_env = os.path.join(BASE_DIR, "config", ".env.example")
        if os.path.exists(example_env):
            with open(example_env, "r", encoding="utf-8") as src, open(ENV_PATH, "w", encoding="utf-8") as dst:
                dst.write(src.read())
            os.chmod(ENV_PATH, 0o600)

    print(f"[+] Saved user calibration to {CFG_PATH}:")
    print(json.dumps(cfg, indent=2))
    if auto_init_nav:
        print("[*] Note: baseline_nav_usdc is set to AUTO — run 'python predator_daemon.py --once --live --init-purified-run' after adding OKX keys to snapshot your live wallet balance.")


if __name__ == "__main__":
    main()
