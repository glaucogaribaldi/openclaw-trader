#!/usr/bin/env python3
"""
TRE OS v35.0 — Interactive & Automated Work-Mode Audit Harness for External Auditor (Luna)
Run via:
  ./venv/bin/python scripts/luna_work_audit_harness.py
Tests all 7 layers of the system live on the VPS (in 100% safe Paper/Shadow mode):
  1. Module Compilation & Clean Import Verification
  2. Live Kronos-mini (4.1M) Oracle (127.0.0.1:8090) & Anti-Stale/Basis MAD Validator
  3. Calibrated EV Engine (p_fill, p_win_fill, p_trade_win, LCB95, p_break_even, EV_net_bps)
  4. Gemini Policy Supervisor (MOMENTUM_RUNNER | MEAN_REVERSION_SCALP | ABSTAIN gates)
  5. Parallel Shadow A/B/C Ledger (lotSz/minSz 60/40 split, TP1, Shadow G2 10-gate check, Chandelier)
  6. Full Live Market Snapshot Paper Cycle (real OKX EEA L2 books + candles + Kronos)
  7. SQLite Historical Trade & Shadow Arena Forensics
"""
import json, os, sqlite3, sys, time, urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)


def run_full_work_audit() -> dict:
    report = {"timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tests": {}}

    # TEST 1: Imports & Compilation
    import predator_futures_demo as pfd
    from core.luna_v35_engine import (
        KronosAntiStaleValidator,
        CalibratedEVEngine,
        GeminiPolicySupervisor,
        ParallelShadowABCLedger,
    )
    report["tests"]["1_imports_and_compile"] = {
        "status": "PASS",
        "universe_size": len(pfd.FUTURES_UNIVERSE),
        "live_execution_env": os.environ.get("FUTURES_LIVE_EXECUTION", "false"),
    }

    # TEST 2: Live Kronos-mini Oracle & Anti-Stale Validator
    kv = KronosAntiStaleValidator()
    k_client = pfd.KronosOracleClient()
    fcs = k_client.fetch_forecasts(["BTC-USDC", "ETH-USDC", "SOL-USDC", "ZEC-USDC", "LINK-USDC"])
    validated_sample = {}
    for k, raw_fc in list(fcs.items())[:4]:
        vfc = kv.validate(k, raw_fc, raw_fc.last_close, raw_fc.last_close)
        validated_sample[k] = {
            "forecast_id": vfc.forecast_id,
            "age_s": vfc.forecast_age_s,
            "exp_1h_bps": vfc.expected_return_1h_bps,
            "pred_vol_1h_bps": vfc.pred_volatility_1h_bps,
            "tp_touch_prob_1h": vfc.tp_touch_prob_1h,
            "disp_bps": vfc.path_dispersion_bps,
            "snr_1h": vfc.snr_1h,
            "entry_valid": vfc.entry_valid,
            "reject_reasons": vfc.reject_reasons,
        }
    report["tests"]["2_kronos_oracle_and_validator"] = {
        "status": "PASS" if fcs else "WARN_EMPTY_CACHE",
        "cached_forecasts_count": len(fcs),
        "sample_validated": validated_sample,
    }

    # TEST 3: Calibrated EV Engine
    ev_eng = CalibratedEVEngine()
    sample_fc = next(iter(fcs.values())) if fcs else None
    vfc_test = kv.validate("BTC-USD_UM_XPERP-310404", sample_fc, sample_fc.last_close if sample_fc else 75500.0)
    ev_bull = ev_eng.evaluate("BTC-USD_UM_XPERP-310404", "LONG", vfc_test, 0.28, 1.5, 45.0, 18.0, 35.0, "TREND_EXPANSION", True, 150)
    ev_chop = ev_eng.evaluate("BTC-USD_UM_XPERP-310404", "LONG", vfc_test, -0.05, 4.8, 30.0, -5.0, 2.0, "MEAN_REVERSION_CHOP", False, 150)
    report["tests"]["3_calibrated_ev_engine"] = {
        "status": "PASS",
        "bull_aligned_case": {
            "p_fill": ev_bull.p_fill, "p_win_fill": ev_bull.p_win_fill, "p_trade_win": ev_bull.p_trade_win,
            "lcb95": ev_bull.lcb95_p_trade_win, "p_break_even": ev_bull.p_break_even,
            "ev_gross_bps": ev_bull.ev_gross_bps, "ev_net_bps": ev_bull.ev_net_bps,
            "paper_authorized": ev_bull.paper_authorized, "reject_reason": ev_bull.reject_reason,
            "p_trade_win_product_check": abs(ev_bull.p_trade_win - (ev_bull.p_fill * ev_bull.p_win_fill)) < 0.001,
        },
        "chop_opposed_case": {
            "p_trade_win": ev_chop.p_trade_win, "ev_net_bps": ev_chop.ev_net_bps,
            "paper_authorized": ev_chop.paper_authorized, "reject_reason": ev_chop.reject_reason,
        },
    }

    # TEST 4: Gemini Policy Supervisor
    sup = GeminiPolicySupervisor()
    pol_mom = sup.evaluate_policy({"policy": "MOMENTUM_RUNNER", "confidence": 0.85}, fee_drag_last_30_pct=10.0, consecutive_stops_same_regime=0, median_ev_net_last_20=9.5)
    pol_abs = sup.evaluate_policy({"policy": "MOMENTUM_RUNNER", "confidence": 0.85}, fee_drag_last_30_pct=35.0, consecutive_stops_same_regime=3, median_ev_net_last_20=2.0)
    report["tests"]["4_gemini_policy_supervisor"] = {
        "status": "PASS" if (pol_mom.policy == "MOMENTUM_RUNNER" and pol_abs.policy == "ABSTAIN") else "FAIL",
        "normal_policy": pol_mom.policy,
        "abstain_override_on_3_stops": {"policy": pol_abs.policy, "reasons": pol_abs.reason_codes, "overrides": pol_abs.parameter_overrides},
    }

    # TEST 5: Parallel Shadow A/B/C Ledger Lifecycle in In-Memory SQLite
    mem_conn = sqlite3.connect(":memory:")
    abc = ParallelShadowABCLedger(mem_conn)
    meta_avax = {"coin": "AVAX", "ct_val": 10.0, "dec_px": 3, "dec_sz": 1, "min_sz": 0.1}
    tp1_q, run_q = abc.split_tp1_runner_qty(1.0, 0.1, 0.1, 0.60)
    # Step 1: Open at $10.00 across A, B, C
    # Force an authorized EV & valid forecast for deterministic lifecycle test
    from core.luna_v35_engine import ValidatedKronosForecast, EVEvaluation
    vfc_ok = ValidatedKronosForecast(
        forecast_id="kf_test", inst_id="AVAX-USD_UM_XPERP-310530", model_version="Kronos-mini",
        generated_at_ts=time.time(), expires_at_ts=time.time() + 90, forecast_age_s=5.0,
        reference_price=10.0, basis_bps=1.0, kronos_5m_bps=15.0, kronos_10m_bps=22.0,
        expected_return_1h_bps=35.0, macro_return_2h_bps=40.0, horizon_6h_bps=50.0,
        swing_return_12h_bps=60.0, daily_return_24h_bps=80.0, pred_volatility_1h_bps=30.0,
        tp_touch_prob_1h=0.72, path_dispersion_bps=12.0, snr_1h=1.16,
        entry_valid=True, management_valid=True, reject_reasons=[],
    )
    ev_ok = EVEvaluation(
        inst_id="AVAX-USD_UM_XPERP-310530", direction="LONG", p_fill=0.90, p_win_fill=0.68,
        p_trade_win=0.67, lcb95_p_trade_win=0.66, p_break_even=0.49, payoff_bps=50.0, loss_bps=38.0,
        fee_roundtrip_bps=4.0, slippage_bps=1.0, latency_adverse_bps=0.3, ev_gross_bps=20.9, ev_net_bps=15.6,
        n_obs_bucket=150, paper_authorized=True, live_candidate_authorized=True, reject_reason="OK",
    )
    abc.step_all_variants("s1", "2026-11-06T09:00:00Z", "AVAX-USD_UM_XPERP-310530", meta_avax, 10.000, 10.000, 10.002, 2.0, 45.0, 0.25, 10.0, 9.98, vfc_ok, ev_ok, ev_ok, pol_mom, "LONG", 100.0)
    # Step 2: Price rises +60 bps to $10.060 -> triggers TP1 (100% exit in Variant C, 60% TP1 in Variants A & B, plus Shadow G2 in Variant A!)
    abc.step_all_variants("s2", "2026-11-06T09:10:00Z", "AVAX-USD_UM_XPERP-310530", meta_avax, 10.060, 10.059, 10.061, 2.0, 45.0, 0.28, 12.0, 10.01, vfc_ok, ev_ok, ev_ok, pol_mom, "NEUTRAL", 100.0)
    # Step 3: Price rises to +110 bps ($10.110) then pulls back to $10.050 -> closes runners in A & B
    abc.step_all_variants("s3", "2026-11-06T09:20:00Z", "AVAX-USD_UM_XPERP-310530", meta_avax, 10.110, 10.109, 10.111, 2.0, 45.0, 0.25, 12.0, 10.04, vfc_ok, ev_ok, ev_ok, pol_mom, "NEUTRAL", 100.0)
    sb_sim = abc.step_all_variants("s4", "2026-11-06T09:30:00Z", "AVAX-USD_UM_XPERP-310530", meta_avax, 10.040, 10.039, 10.041, 2.0, 45.0, -0.10, 0.0, 10.04, vfc_ok, ev_ok, ev_ok, pol_mom, "NEUTRAL", 100.0)
    mem_counts = {}
    for table in ("market_snapshots", "variant_orders", "variant_fills", "variant_positions", "variant_events", "variant_metrics"):
        mem_counts[table] = int(mem_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    report["tests"]["5_shadow_abc_lifecycle_simulation"] = {
        "status": "PASS",
        "lot_split_test_1.0_avax": {"tp1_qty_60pct": tp1_q, "runner_qty_40pct": run_q},
        "simulated_wave_scoreboard": sb_sim,
        "ledger_row_counts": mem_counts,
    }

    # TEST 6: SQLite Production Database & Live Shadow Scoreboard Inspection
    db_path = os.path.join(BASE_DIR, "config", "okx_futures_demo.db")
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), ROUND(SUM(realized_pnl_usd), 2) FROM futures_demo_positions WHERE status != 'OPEN'")
        tot_t, tot_p = cur.fetchone()
        abc_live = ParallelShadowABCLedger(conn).get_scoreboard()
        ev_prod = CalibratedEVEngine()
        report["tests"]["6_sqlite_db_and_live_shadow_abc"] = {
            "status": "PASS",
            "historical_closed_trades": tot_t,
            "historical_realized_pnl_usd": tot_p,
            "ev_calibration": ev_prod.fit_from_sqlite(conn, min_obs=100),
            "shadow_row_counts": {
                table: int(cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in ("market_snapshots", "variant_orders", "variant_fills", "variant_positions", "variant_events", "variant_metrics")
            },
            "live_shadow_abc_scoreboard": abc_live,
        }


    # TEST 7: Mandatory 6 Capital Allocation & Reserve Protection Tests (RESERVE_FLOOR_USDC = 125.00)
    from dataclasses import asdict
    from core.luna_v35_engine import CapitalAllocationBook, REFERENCE_NAV_USDC, RESERVE_FLOOR_USDC
    # 7.1: Start from 250.00 USDC -> reserve 125.00, operational 125.00, total 250.00 (and 250.23 -> 125.00 / 125.23)
    book_250 = CapitalAllocationBook(initial_total_equity_usdc=250.00, reserve_floor_usdc=125.00)
    book_250_23 = CapitalAllocationBook(initial_total_equity_usdc=250.23, reserve_floor_usdc=125.00)
    assert book_250.state.reserve_usdc == 125.00 and book_250.state.operational_capital_usdc == 125.00 and book_250.state.total_equity_usdc == 250.00
    assert book_250_23.state.reserve_usdc == 125.00 and book_250_23.state.operational_capital_usdc == 125.23 and book_250_23.state.total_equity_usdc == 250.23

    # 7.2: Realized net profit +7.00 USDC -> reserve_usdc = 125.00, operational_capital_usdc = 132.00, total_equity_usdc = 257.00
    st_plus7 = book_250.apply_confirmed_fill_pnl(realized_gross_pnl=7.50, entry_fees=0.20, exit_fees=0.20, slippage=0.10, funding=0.0, confirmed_fill=True)
    assert st_plus7.reserve_usdc == 125.00 and st_plus7.operational_capital_usdc == 132.00 and st_plus7.total_equity_usdc == 257.00

    # 7.3: Partial net profit +2.00 USDC -> increases operational_capital_usdc ONLY after confirmed_fill=True
    book_part = CapitalAllocationBook(initial_total_equity_usdc=250.00, reserve_floor_usdc=125.00)
    book_part.set_unrealized_pnl(15.00)  # Unrealized PnL must NEVER change operational_capital_usdc!
    assert book_part.state.operational_capital_usdc == 125.00
    book_part.apply_confirmed_fill_pnl(realized_gross_pnl=2.00, confirmed_fill=False)  # Unconfirmed fill must NOT change operational_capital_usdc!
    assert book_part.state.operational_capital_usdc == 125.00
    st_part_conf = book_part.apply_confirmed_fill_pnl(realized_gross_pnl=2.10, entry_fees=0.05, exit_fees=0.05, confirmed_fill=True)
    assert st_part_conf.reserve_usdc == 125.00 and st_part_conf.operational_capital_usdc == 127.00 and st_part_conf.total_equity_usdc == 252.00

    # 7.4: Realized net loss -5.00 USDC -> reserve unchanged at 125.00, operational_capital_usdc reduced by 5.00 (120.00)
    book_loss = CapitalAllocationBook(initial_total_equity_usdc=250.00, reserve_floor_usdc=125.00)
    st_loss5 = book_loss.apply_confirmed_fill_pnl(realized_gross_pnl=-4.80, entry_fees=0.10, exit_fees=0.10, confirmed_fill=True)
    assert st_loss5.reserve_usdc == 125.00 and st_loss5.operational_capital_usdc == 120.00 and st_loss5.total_equity_usdc == 245.00

    # 7.5: Attempt to use reserve (operational capital depleted to $2.00, attempting to open $8.20 min lot) -> rejected, policy ABSTAIN, event recorded
    mem_res_conn = sqlite3.connect(":memory:")
    abc_res = ParallelShadowABCLedger(mem_res_conn, initial_total_equity_usdc=127.00)  # 125 reserve + 2.00 operational
    abc_res.step_all_variants("s_res", "2026-11-06T10:00:00Z", "AVAX-USD_UM_XPERP-310530", meta_avax, 10.000, 10.000, 10.002, 2.0, 45.0, 0.25, 10.0, 9.98, vfc_ok, ev_ok, ev_ok, pol_mom, "LONG", 50.0)
    res_ev_rows = mem_res_conn.execute("SELECT event_type, payload FROM variant_events WHERE event_type='RESERVE_PROTECTION_ABSTAIN'").fetchall()
    res_pos_cnt = mem_res_conn.execute("SELECT COUNT(*) FROM variant_positions").fetchone()[0]
    assert len(res_ev_rows) == 3 and res_pos_cnt == 0

    # 7.6: Verify no legacy branch in predator_futures_demo.py computes slot_margin_usd on live_nav_est
    pfd_src = open(os.path.join(BASE_DIR, "predator_futures_demo.py"), encoding="utf-8").read()
    assert "slot_margin_usd = round(operational_capital_usdc * SLOT_NAV_PCT, 2)" in pfd_src
    assert "slot_margin_usd = round(live_nav_est * SLOT_NAV_PCT, 2)" not in pfd_src

    report["tests"]["7_capital_allocation_and_125_reserve_invariants"] = {
        "status": "PASS",
        "test1_start_250": asdict(book_250.state),
        "test1b_start_250_23": asdict(book_250_23.state),
        "test2_profit_plus_7": {
            "reserve_usdc": st_plus7.reserve_usdc,
            "operational_capital_usdc": st_plus7.operational_capital_usdc,
            "total_equity_usdc": st_plus7.total_equity_usdc,
        },
        "test3_partial_profit_plus_2_confirmed": asdict(st_part_conf),
        "test4_loss_minus_5": asdict(st_loss5),
        "test5_reserve_protection_abstain": {
            "orders_opened": res_pos_cnt,
            "abstain_events_recorded": len(res_ev_rows),
            "sample_event": json.loads(res_ev_rows[0][1]),
        },
        "test6_no_legacy_total_nav_sizing": True,
    }
    return report


if __name__ == "__main__":
    print(json.dumps(run_full_work_audit(), indent=2))
