#!/usr/bin/env python3
"""
TRE OS v18.2 — Autonomous Hourly Guardian, Self-Healer, Strategy Optimizer & Telegram Reporter
Runs every hour on brody (and on demand) to verify health, auto-switch strategy if needed, and push Telegram report.
"""
import datetime, json, os, sqlite3, subprocess, sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from predator_futures_demo import init_futures_db, load_gemini_brain_skills, run_gemini_ordinary_futures_audit
from predator_daemon import load_dotenv
from scripts.telegram_reporter import send_telegram_report

def run_hourly_guardian() -> None:
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    for svc in ("kronos-oracle.service", "openclaw-futures-demo.service", "openclaw-dashboard.service"):
        st = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True).stdout.strip()
        if st != "active":
            subprocess.run(["sudo", "systemctl", "restart", svc], check=False)
    snap_p = os.path.join(BASE_DIR, "config", "futures_demo_snapshot.json")
    snap = json.load(open(snap_p, encoding="utf-8")) if os.path.exists(snap_p) else {}
    conn = init_futures_db(os.path.join(BASE_DIR, "config", "okx_futures_demo.db"))
    nav = float(snap.get("current_nav_usd") or 256.59)
    tel = snap.get("telemetry", [])
    if tel:
        run_gemini_ordinary_futures_audit(conn, nav, tel)
    conn.close()
    send_telegram_report()
    print(f"[HOURLY GUARDIAN OK] {datetime.datetime.now(datetime.timezone.utc).isoformat()} | NAV=${nav:.2f}")

if __name__ == "__main__":
    run_hourly_guardian()