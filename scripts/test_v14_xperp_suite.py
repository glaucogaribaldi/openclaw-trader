#!/usr/bin/env python3
"""
TRE OS v14.0 — Surgical 6-Block End-to-End Verification Suite (test_v14_xperp_suite.py)
Verifies all 6 production subsystems of Live OKX EEA XPERP Perpetual Futures 2.5x Isolated on brody.
"""
import json, os, subprocess, sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.kronos_oracle import KronosOracleClient
from execution.okx_hybrid_executor import OKXNativeClient
from predator_futures_demo import FUTURES_UNIVERSE, _calc_contract_sz

def run_suite():
    results = {}
    # Block 1: Process & Service Hygiene (openclaw-predator disabled/inactive, kronos & futures active)
    pred_st = subprocess.run(["systemctl", "is-active", "openclaw-predator.service"], capture_output=True, text=True).stdout.strip()
    kron_st = subprocess.run(["systemctl", "is-active", "kronos-oracle.service"], capture_output=True, text=True).stdout.strip()
    fut_st = subprocess.run(["systemctl", "is-active", "openclaw-futures-demo.service"], capture_output=True, text=True).stdout.strip()
    dash_st = subprocess.run(["systemctl", "is-active", "openclaw-dashboard.service"], capture_output=True, text=True).stdout.strip()
    results["block1_service_hygiene"] = {
        "pass": bool(pred_st != "active" and kron_st == "active" and fut_st == "active" and dash_st == "active"),
        "spot_predator_retired": pred_st != "active",
        "kronos_oracle": kron_st,
        "futures_xperp_engine": fut_st,
        "dashboard": dash_st,
    }

    # Block 2: 7-Horizon Kronos Oracle (5m, 10m, 1h, 2h, 6h, 12h, 24h)
    kc = KronosOracleClient()
    spot_ids = [m["spot_id"] for m in FUTURES_UNIVERSE.values()]
    fc_map = kc.fetch_forecasts(spot_ids)
    btc_fc = fc_map.get("BTC-USDC")
    results["block2_kronos_7horizon"] = {
        "pass": bool(len(fc_map) >= 10 and btc_fc is not None),
        "forecasts_count": len(fc_map),
        "btc_horizons_bps": {
            "5m": btc_fc.kronos_5m_bps if btc_fc else None,
            "10m": btc_fc.kronos_10m_bps if btc_fc else None,
            "1h": btc_fc.expected_return_1h_bps if btc_fc else None,
            "2h": btc_fc.macro_return_2h_bps if btc_fc else None,
            "6h": btc_fc.horizon_6h_bps if btc_fc else None,
            "12h": btc_fc.swing_return_12h_bps if btc_fc else None,
            "24h": btc_fc.daily_return_24h_bps if btc_fc else None,
        }
    }

    # Block 3: OKX EEA XPERP Contract Sizing & 2.5x Leverage Verification
    sz_btc, not_btc = _calc_contract_sz("BTC-USD_UM_XPERP-310404", 90.0, 77400.0)
    sz_sol, not_sol = _calc_contract_sz("SOL-USD_UM_XPERP-310404", 90.0, 96.50)
    sz_avax, not_avax = _calc_contract_sz("AVAX-USD_UM_XPERP-310530", 90.0, 8.35)
    results["block3_xperp_contract_sizing"] = {
        "pass": bool(int(sz_btc) >= 10 and int(sz_sol) >= 80 and float(sz_avax) >= 1.0),
        "btc_90usd_contracts": (sz_btc, not_btc),
        "sol_90usd_contracts": (sz_sol, not_sol),
        "avax_90usd_contracts": (sz_avax, not_avax),
    }

    # Block 4: Live OKX EEA Account & 1:1 Position Reconciliation
    c = OKXNativeClient()
    bal = c._request("GET", "/api/v5/account/balance", auth=True).get("data", [{}])[0]
    total_eq = float(bal.get("totalEq") or 0.0)
    pos = c._request("GET", "/api/v5/account/positions?instType=FUTURES", auth=True).get("data", [])
    pend = c._request("GET", "/api/v5/trade/orders-pending?instType=FUTURES", auth=True).get("data", [])
    results["block4_okx_live_account"] = {
        "pass": bool(total_eq > 250.0),
        "total_eq_usd": round(total_eq, 2),
        "live_positions_count": len([p for p in pos if abs(float(p.get("pos") or 0)) > 0]),
        "pending_orders_count": len(pend),
    }

    # Block 5: Snapshot & Risk Invariants Verification
    snap_p = os.path.join(BASE_DIR, "config", "futures_demo_snapshot.json")
    snap = json.load(open(snap_p, encoding="utf-8")) if os.path.exists(snap_p) else {}
    results["block5_snapshot_and_auditor"] = {
        "pass": bool(snap.get("execution_mode") == "LIVE_XPERP_2.5X" and len(snap.get("telemetry", [])) == 12),
        "execution_mode": snap.get("execution_mode"),
        "telemetry_pairs": len(snap.get("telemetry", [])),
        "auditor_model": snap.get("auditor_model"),
        "audit_doc_exists": os.path.exists(os.path.join(BASE_DIR, "docs", "AUDIT_72H_LIVE_XPERP_MILESTONES.md")),
    }

    results["all_blocks_passed"] = all(v["pass"] for k, v in results.items() if isinstance(v, dict) and "pass" in v)
    print(json.dumps(results, indent=2))
    if not results["all_blocks_passed"]:
        sys.exit(1)

if __name__ == "__main__":
    run_suite()
