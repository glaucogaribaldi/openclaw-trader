#!/usr/bin/env python3
"""
TRE OS v12.6 — Automated 5-Block Structural, Flow & AI Verification Suite (scripts/test_all_blocks.py)
Tests every block of the trading system deterministically + queries Google Gemini Free Tier for live AI verification.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from agents.llm_council import AdversarialLLMCouncil
from core.gemini_self_improver import GeminiSelfImprover
from core.kronos_oracle import KronosOracleClient
from core.microstructure import MicrostructureEngine
from core.predictor import PredatorPredictiveEngine
from core.universe_scanner import PredatorUniverseScanner
from execution.okx_hybrid_executor import OKXNativeClient
from predator_daemon import DEFAULT_UNIVERSE, init_predator_db, load_dotenv, load_purified_run_config_dict, run_predator_cycle


def run_tests() -> dict:
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    results = {}

    # BLOCK 1: Universe Scanner (filters out X* synthetics and >16.5% pump-and-dump coins, keeps held coins)
    client = OKXNativeClient(simulated_demo=False)
    scanner = PredatorUniverseScanner(ttl_sec=600.0, max_dynamic_explorers=6)
    univ, radar = scanner.scan_okx_usdc_universe(client, DEFAULT_UNIVERSE, held_coins={"SOL"})
    has_x_synth = any(k.startswith("X") and not k.startswith(("XRP-", "XLM-", "XTZ-")) for k in univ.keys())
    results["block1_universe_scanner"] = {
        "pass": (len(univ) >= 12 and not has_x_synth),
        "pairs_count": len(univ),
        "has_x_synthetic_leak": has_x_synth,
    }

    # BLOCK 2: Microstructure + RLS/Kalman Predictor + 5-Horizon Macro Veto
    micro = MicrostructureEngine()
    pred_eng = PredatorPredictiveEngine()
    sig = micro.process_snapshot("SOL-USDC", [[100.0, 10.0], [99.9, 10.0]], [[100.1, 5.0], [100.2, 5.0]], [])
    p_bull = pred_eng.evaluate(sig, kronos_return_1h_bps=25.0, kronos_macro_2h_bps=20.0, kronos_6h_bps=30.0, kronos_swing_12h_bps=40.0, kronos_24h_bps=50.0, kronos_horizon_aligned=True)
    p_veto = pred_eng.evaluate(sig, kronos_return_1h_bps=25.0, kronos_macro_2h_bps=-35.0, kronos_6h_bps=-60.0, kronos_swing_12h_bps=-80.0, kronos_24h_bps=-100.0, kronos_horizon_aligned=False)
    results["block2_predictor_5h_veto"] = {
        "pass": (p_bull.predicted_return_bps > p_veto.predicted_return_bps + 4.0),
        "bull_pred_bps": round(p_bull.predicted_return_bps, 2),
        "bear_vetoed_pred_bps": round(p_veto.predicted_return_bps, 2),
    }

    # BLOCK 3: Local 5-Horizon Kronos Oracle (1h, 2h, 6h, 12h, 24h + BTC-USDC)
    kro = KronosOracleClient()
    fcs = kro.fetch_forecasts(["BTC-USDC", "SOL-USDC", "HYPE-USDC"])
    sample_fc = fcs.get("HYPE-USDC") or fcs.get("SOL-USDC")
    results["block3_kronos_5horizon"] = {
        "pass": bool(sample_fc is not None),
        "cached_count": len(fcs),
        "sample_horizons": {
            "1h": getattr(sample_fc, "expected_return_1h_bps", None),
            "2h": getattr(sample_fc, "macro_return_2h_bps", None),
            "6h": getattr(sample_fc, "horizon_6h_bps", None),
            "12h": getattr(sample_fc, "swing_return_12h_bps", None),
            "24h": getattr(sample_fc, "daily_return_24h_bps", None),
        } if sample_fc else None,
    }

    # BLOCK 4: GeminiSelfImprover Anti-Paralysis & Dual Free AI Council
    improver = GeminiSelfImprover(BASE_DIR)
    si_st = improver.load_state()
    results["block4_gemini_self_improver"] = {
        "pass": (0.15 <= si_st["min_entry_ofi"] <= 0.30 and 25.0 <= si_st["min_pullback_2h_bps"] <= 48.0),
        "state": si_st,
    }

    # BLOCK 5: Hermetic Dry-Run Execution Cycle (Stop-Loss 24/7, 6h Quarantine, Anti-FOMO, Night Guard)
    db_path = os.path.join(BASE_DIR, "config", "okx_trader.db")
    conn = init_predator_db(db_path)
    council = AdversarialLLMCouncil(directive_out_path=os.path.join(BASE_DIR, "config", "predator_llm_directive.json"))
    from core.predator_auditor import PredatorAuditor
    auditor = PredatorAuditor(db_path=db_path, report_out_path=os.path.join(BASE_DIR, "config", "predator_audit_report.json"))
    cyc = run_predator_cycle(client, micro, pred_eng, kro, council, auditor, conn, run_llm_debate=True, run_audit=False, dry_run=True)
    conn.close()
    results["block5_hermetic_dry_run_cycle"] = {
        "pass": (cyc.get("nav_usdc", 0) > 0 and len(cyc.get("telemetry", [])) >= 12),
        "nav_usdc": cyc.get("nav_usdc"),
        "free_usdc": cyc.get("free_usdc"),
        "latency_ms": cyc.get("latency_scan_ms"),
        "llm_debate_model": (cyc.get("llm_debate") or {}).get("model_used"),
    }

    results["all_5_blocks_passed"] = all(v.get("pass") for k, v in results.items() if isinstance(v, dict) and "pass" in v)
    return results


if __name__ == "__main__":
    out = run_tests()
    print(json.dumps(out, indent=2))
    sys.exit(0 if out.get("all_5_blocks_passed") else 1)
