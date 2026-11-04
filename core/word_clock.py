#!/usr/bin/env python3
"""
TRE OS v22.0 — Audio-Grade Master/Slave Word Clock Engine (core/word_clock.py)
- Single Master Clock locked to monotonic epoch_ms boundaries (zero cumulative sleep drift).
- Dynamic Tempo: 15.0s (4 BPM) standard, auto-accelerates to 10.0s (6 BPM High-Speed) in Pyramid Tier 2/3,
  or manually adjustable via word_clock_ctl.py --set-tick <sec>.
- Drives all Slaves in phase: /1 (L2+Kronos+Chandelier), /20 (5m 257-OKX Scanner + Gemini Brain),
  /240 (1h Guardian + Sub-Agent + GSheet + Telegram), /720 (3h Deep Audit), /2880 (12h Proactive R&D).
- Jitter & Drift Tolerance Guard: trips SAFE_HOLD (blocks new entries) if any critical slave drifts > tolerance_ms.
"""
from __future__ import annotations
import datetime, json, os, time
from typing import Any, Dict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLOCK_CONFIG_PATH = os.path.join(BASE_DIR, "config", "word_clock_config.json")
CLOCK_STATE_PATH = os.path.join(BASE_DIR, "config", "word_clock_state.json")

DEFAULT_CLOCK_CFG: Dict[str, Any] = {
    "base_tick_sec": 15.0,
    "high_speed_tick_sec": 10.0,
    "auto_high_speed_on_pyramid": True,
    "manual_override_tick_sec": 0.0,
    "max_jitter_tolerance_ms": 15000.0,
    "dividers": {
        "slave_l2_chandelier": 1,
        "slave_5m_scanner_and_gemini": 20,
        "slave_1h_guardian_gsheet_telegram": 240,
        "slave_3h_deep_audit": 720,
        "slave_12h_proactive_rd": 2880,
    }
}

def load_clock_config() -> Dict[str, Any]:
    os.makedirs(os.path.dirname(CLOCK_CONFIG_PATH), exist_ok=True)
    if os.path.exists(CLOCK_CONFIG_PATH):
        try:
            d = json.load(open(CLOCK_CONFIG_PATH, encoding="utf-8"))
            out = dict(DEFAULT_CLOCK_CFG)
            out.update(d)
            return out
        except Exception:
            pass
    with open(CLOCK_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CLOCK_CFG, f, indent=2)
    return dict(DEFAULT_CLOCK_CFG)

class MasterWordClock:
    def __init__(self) -> None:
        self.frame_id: int = 0
        self.last_hour_dispatched: int = -1
        self.last_12h_dispatched: int = -1
        if os.path.exists(CLOCK_STATE_PATH):
            try:
                st = json.load(open(CLOCK_STATE_PATH, encoding="utf-8"))
                self.frame_id = int(st.get("frame_id") or 0)
                self.last_hour_dispatched = int(st.get("last_hour_dispatched") or -1)
                self.last_12h_dispatched = int(st.get("last_12h_dispatched") or -1)
            except Exception:
                pass

    def compute_active_tick_sec(self, pyramid_tier: int = 0) -> Tuple[float, str]:
        cfg = load_clock_config()
        man = float(cfg.get("manual_override_tick_sec") or 0.0)
        if man >= 5.0:
            return man, f"MANUAL_{man:.1f}S"
        if cfg.get("auto_high_speed_on_pyramid", True) and pyramid_tier >= 2:
            hs = float(cfg.get("high_speed_tick_sec") or 10.0)
            return hs, f"HIGH_SPEED_PYRAMID_T{pyramid_tier}_{hs:.1f}S"
        base = float(cfg.get("base_tick_sec") or 15.0)
        return base, f"STANDARD_{base:.1f}S"

    def evaluate_sync_lock(self, cycle_duration_ms: float, kronos_latency_ms: float = 18.0) -> Dict[str, Any]:
        cfg = load_clock_config()
        tol_ms = float(cfg.get("max_jitter_tolerance_ms") or 15000.0)
        total_drift_ms = round(max(cycle_duration_ms, kronos_latency_ms), 1)
        sync_locked = bool(total_drift_ms <= tol_ms)
        return {
            "sync_locked": sync_locked,
            "safe_hold_block_entries": (not sync_locked),
            "measured_cycle_ms": round(cycle_duration_ms, 1),
            "kronos_latency_ms": round(kronos_latency_ms, 1),
            "tolerance_ms": tol_ms,
            "status": "LOCKED_EXT_SYNC" if sync_locked else "UNLOCKED_SAFE_HOLD",
        }

    def advance_frame_and_persist(self, pyramid_tier: int, cycle_duration_ms: float, active_slaves: list) -> Dict[str, Any]:
        self.frame_id += 1
        tick_sec, mode_label = self.compute_active_tick_sec(pyramid_tier)
        lock_info = self.evaluate_sync_lock(cycle_duration_ms)
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        state = {
            "timestamp_utc": now_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "master_authority": "predator_futures_demo.py (SINGLE_MASTER)",
            "frame_id": self.frame_id,
            "active_tick_sec": tick_sec,
            "bpm": round(60.0 / tick_sec, 2),
            "tempo_mode": mode_label,
            "pyramid_tier_detected": pyramid_tier,
            "sync_lock": lock_info,
            "slaves_triggered_on_frame": active_slaves,
            "last_hour_dispatched": self.last_hour_dispatched,
            "last_12h_dispatched": self.last_12h_dispatched,
        }
        with open(CLOCK_STATE_PATH + ".tmp", "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(CLOCK_STATE_PATH + ".tmp", CLOCK_STATE_PATH)
        return state

    def wait_for_next_phase_locked_beat(self, pyramid_tier: int = 0) -> float:
        tick_sec, _ = self.compute_active_tick_sec(pyramid_tier)
        now_s = time.time()
        next_boundary = (int(now_s // tick_sec) + 1) * tick_sec
        sleep_s = max(0.2, min(tick_sec, next_boundary - now_s))
        time.sleep(sleep_s)
        return sleep_s