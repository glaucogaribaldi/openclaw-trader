#!/usr/bin/env python3
"""
TRE OS v22.0 — Master Word Clock Control & Verification CLI (scripts/word_clock_ctl.py)
Usage:
  python scripts/word_clock_ctl.py --status
  python scripts/word_clock_ctl.py --set-tick 10.0   (or 0 to restore auto 15s/10s)
  python scripts/word_clock_ctl.py --set-tolerance 15000
  python scripts/word_clock_ctl.py --test-all
"""
import json, os, sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from core.word_clock import CLOCK_CONFIG_PATH, CLOCK_STATE_PATH, MasterWordClock, load_clock_config

def run_tests() -> dict:
    wc = MasterWordClock()
    t_std, m_std = wc.compute_active_tick_sec(pyramid_tier=1)
    t_hs, m_hs = wc.compute_active_tick_sec(pyramid_tier=2)
    lock_ok = wc.evaluate_sync_lock(cycle_duration_ms=1420.0, kronos_latency_ms=18.0)
    lock_trip = wc.evaluate_sync_lock(cycle_duration_ms=18500.0, kronos_latency_ms=18.0)
    res = {
        "test1_dynamic_tempo_15s_to_10s": {"pass": (t_std == 15.0 and t_hs == 10.0), "tier1_tick": t_std, "tier2_tick": t_hs},
        "test2_normal_phase_lock": {"pass": (lock_ok["sync_locked"] is True and lock_ok["safe_hold_block_entries"] is False), "details": lock_ok},
        "test3_tolerance_breach_safe_hold": {"pass": (lock_trip["sync_locked"] is False and lock_trip["safe_hold_block_entries"] is True), "details": lock_trip},
    }
    res["all_word_clock_tests_passed"] = all(v["pass"] for v in res.values() if isinstance(v, dict))
    return res

if __name__ == "__main__":
    args = sys.argv[1:]
    cfg = load_clock_config()
    if "--set-tick" in args:
        idx = args.index("--set-tick")
        val = float(args[idx + 1])
        cfg["manual_override_tick_sec"] = val
        json.dump(cfg, open(CLOCK_CONFIG_PATH, "w", encoding="utf-8"), indent=2)
    if "--set-tolerance" in args:
        idx = args.index("--set-tolerance")
        val = float(args[idx + 1])
        cfg["max_jitter_tolerance_ms"] = val
        json.dump(cfg, open(CLOCK_CONFIG_PATH, "w", encoding="utf-8"), indent=2)
    if "--test-all" in args:
        print(json.dumps(run_tests(), indent=2))
        sys.exit(0)
    st = json.load(open(CLOCK_STATE_PATH, encoding="utf-8")) if os.path.exists(CLOCK_STATE_PATH) else {}
    print(json.dumps({"config": cfg, "live_master_state": st}, indent=2))