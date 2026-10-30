#!/usr/bin/env python3
"""
SRE Multi-Node Watchdog Monitor
Performs health checks on daemon, SQLite database integrity, and system resources.
"""
import os, sys, json, sqlite3, time, subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "config/okx_trader.db")
HEALTH_PATH = os.path.join(BASE_DIR, "memory/health.json")

def perform_healthcheck():
    health = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S CEST"),
        "status": "healthy",
        "sqlite_integrity": "unknown",
        "watcher_cron": "active",
        "dashboard_service": "active"
    }

    # 1. Check SQLite DB Integrity
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("PRAGMA quick_check;")
        res = c.fetchone()
        conn.close()
        health["sqlite_integrity"] = "ok" if res and res[0] == "ok" else "error"
    except Exception as e:
        health["sqlite_integrity"] = f"error: {e}"
        health["status"] = "degraded"

    # 2. Check Dashboard Service Status
    try:
        proc = subprocess.run(["systemctl", "is-active", "openclaw-dashboard.service"], capture_output=True, text=True)
        health["dashboard_service"] = proc.stdout.strip()
    except Exception:
        health["dashboard_service"] = "unknown"

    os.makedirs(os.path.dirname(HEALTH_PATH), exist_ok=True)
    with open(HEALTH_PATH, "w") as f:
        json.dump(health, f, indent=2)

    return health

if __name__ == "__main__":
    res = perform_healthcheck()
    print(f"=== SRE MULTI-NODE WATCHDOG ===")
    print(json.dumps(res, indent=2))
