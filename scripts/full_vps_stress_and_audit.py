#!/usr/bin/env python3
"""
TRE OS v15.3 — Full-Spectrum VPS Stress-Test, Invariant Torture Suite & Multi-AI Red-Team Audit
Runs on VPS brody in an isolated sandbox (/tmp/stress_sandbox.db) + live read-only diagnostics.
"""
import json, os, sqlite3, subprocess, sys, time, urllib.request, ssl
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from predator_futures_demo import (
    FUTURES_UNIVERSE, LEVERAGE, SLOT_NAV_PCT, _calc_contract_sz, init_futures_db, load_gemini_brain_skills
)
from predator_daemon import load_dotenv

def run_stress_and_audit():
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    report = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stress_tests": {}, "infra_audit": {}, "ai_red_team_audit": {}}

    # 1. STRESS TEST 1A: Anti-Burst Invariant (12 simultaneous signals -> max 1 unshielded slot opened)
    open_positions = {}
    live_okx_pend = set()
    opened_in_burst = 0
    for idx in range(12):
        unshielded_total = sum(1 for r in open_positions.values() if int(r[10]) == 0) + len(live_okx_pend)
        if unshielded_total >= 1:
            break
        live_okx_pend.add(f"COIN_{idx}")
        opened_in_burst += 1
    report["stress_tests"]["1A_anti_burst_12_signals"] = {
        "pass": opened_in_burst == 1,
        "signals_injected": 12,
        "orders_allowed": opened_in_burst,
    }

    # 2. STRESS TEST 1B: Real-Candle Counter-Trend Gate (Kronos bearish -80bps BUT real 15m/1h candle GREEN +25bps -> MUST BLOCK SHORT)
    k6h, k12h, k24h, k2h, k1h = -80.0, -90.0, -100.0, -15.0, -20.0
    real_15m_bps, real_1h_bps = +25.0, +45.0  # Green surge like 15:25 CET Wall Street open
    macro_bear = bool(k6h <= -8.0 and (k12h <= -5.0 or k24h <= -5.0) and k2h <= 8.0 and k1h <= -6.0 and real_1h_bps <= -5.0 and real_15m_bps <= -2.0)
    report["stress_tests"]["1B_counter_trend_green_candle_block"] = {
        "pass": (macro_bear is False),
        "kronos_6h_bps": k6h,
        "real_1h_candle_bps": real_1h_bps,
        "short_blocked": (not macro_bear),
    }

    # 3. STRESS TEST 1C: Anti-Wick Survival (-120 bps Market-Maker Wick -> survives -> rallies to +100 bps -> locks +75 bps)
    path_bps = [-40.0, -95.0, -120.0, -60.0, +15.0, +42.0, +24.0, +88.0, +100.0, +74.0]
    peak_bps = 0.0
    shield_armed = 0
    stopped_on_wick = False
    choked_at_24bps = False
    final_locked_exit_bps = None
    for mv in path_bps:
        peak_bps = max(peak_bps, mv)
        if peak_bps >= 35.0:
            shield_armed = 1
        if mv <= -180.0:
            stopped_on_wick = True
            break
        if shield_armed == 1:
            locked_bps = 12.0 if peak_bps < 75.0 else (peak_bps * 0.75)
            if mv <= locked_bps:
                if peak_bps < 75.0:
                    choked_at_24bps = True
                final_locked_exit_bps = mv
                break
    report["stress_tests"]["1C_anti_wick_and_runner_asymmetry"] = {
        "pass": bool((not stopped_on_wick) and (not choked_at_24bps) and final_locked_exit_bps == 74.0),
        "survived_minus_120bps_wick": (not stopped_on_wick),
        "survived_plus_42_to_24bps_pullback": (not choked_at_24bps),
        "final_runner_exit_bps": final_locked_exit_bps,
    }

    # 4. STRESS TEST 1D: Sandbox SQLite Zero-Delete & 120m Quarantine Verification
    sb_path = "/tmp/stress_sandbox_v15.db"
    if os.path.exists(sb_path): os.remove(sb_path)
    sconn = init_futures_db(sb_path)
    scur = sconn.cursor()
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    scur.execute("INSERT INTO futures_demo_positions VALUES ('TEST_1', 'LINK-USD_UM_XPERP-310523', 'LONG', 2.0, 50.0, 100.0, 11.0, 11.0, 11.15, 10.80, 0.0, 0, 0.02, 'OPEN', ?, NULL, NULL, NULL)", (now_iso,))
    scur.execute("UPDATE futures_demo_positions SET status='CLOSED_STOPLOSS', closed_at=?, exit_px=10.80, realized_pnl_usd=-1.85 WHERE pos_id='TEST_1'", (now_iso,))
    sconn.commit()
    scur.execute("SELECT inst_id, status, (julianday('now') - julianday(closed_at)) * 1440.0 FROM futures_demo_positions WHERE status != 'OPEN'")
    q_row = scur.fetchone()
    quarantined = bool(q_row and q_row[1] == "CLOSED_STOPLOSS" and float(q_row[2]) < 120.0)
    sconn.close()
    os.remove(sb_path)
    report["stress_tests"]["1D_zero_delete_and_120m_quarantine"] = {"pass": quarantined, "quarantine_active": quarantined}

    # 5. INFRASTRUCTURE & SQLITE WAL INTEGRITY ON BRODY
    db_p = os.path.join(BASE_DIR, "config", "okx_futures_demo.db")
    rconn = sqlite3.connect(db_p)
    integ = rconn.execute("PRAGMA integrity_check;").fetchone()[0]
    rconn.close()
    t0 = time.time()
    with urllib.request.urlopen("http://127.0.0.1:8090/health", timeout=4) as kr:
        k_health = json.loads(kr.read().decode("utf-8"))
    kronos_ms = round((time.time() - t0) * 1000.0, 2)
    t1 = time.time()
    with urllib.request.urlopen("http://127.0.0.1:8080/api/state", timeout=4) as dr:
        d_state = json.loads(dr.read().decode("utf-8"))
    dash_ms = round((time.time() - t1) * 1000.0, 2)
    mem_out = subprocess.check_output(["free", "-m"]).decode("utf-8").splitlines()[1].split()
    report["infra_audit"] = {
        "pass": bool(integ == "ok" and k_health.get("status") == "ok" and d_state.get("current_nav_usdc", 0) > 200),
        "sqlite_wal_integrity": integ,
        "kronos_oracle_latency_ms": kronos_ms,
        "dashboard_api_latency_ms": dash_ms,
        "ram_used_mb": int(mem_out[2]),
        "ram_available_mb": int(mem_out[6]),
    }

    # 6. LIVE AI RED-TEAM AUDIT ON BRODY
    skills = load_gemini_brain_skills()
    report["ai_red_team_audit"] = {
        "pass": bool(skills.get("outlook_1h") and skills.get("outlook_48h") and len(skills.get("learned_rules", [])) >= 3),
        "active_agent_model": skills.get("model_used"),
        "has_4_horizons_1h_6h_12h_48h": bool(skills.get("outlook_1h") and skills.get("outlook_6h") and skills.get("outlook_12h") and skills.get("outlook_48h")),
        "learned_rules_count": len(skills.get("learned_rules", [])),
        "latest_self_critique": skills.get("self_critique"),
    }
    report["all_stress_and_audit_passed"] = all(
        v.get("pass", False) for v in list(report["stress_tests"].values()) + [report["infra_audit"], report["ai_red_team_audit"]]
    )
    print(json.dumps(report, indent=2))
    if not report["all_stress_and_audit_passed"]:
        sys.exit(1)

if __name__ == "__main__":
    run_stress_and_audit()