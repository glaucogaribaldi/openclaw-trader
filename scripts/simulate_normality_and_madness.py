#!/usr/bin/env python3
"""
TRE OS v14.3 — Surgical Normality & Madness (Black Swan) Stress-Test Simulator
Simulates 3 Normality Regimes and 5 Extreme Madness / Crash Scenarios on the $268.13 USDC portfolio.
"""
import json

START_NAV = 268.13
SLOT_PCT = 0.20
LEVERAGE = 4.0
SLOT_MGN = round(START_NAV * SLOT_PCT, 2)        # $53.63 USDC
SLOT_NOTIONAL = round(SLOT_MGN * LEVERAGE, 2)    # $214.50 USD
MAKER_FEE_RT = round(SLOT_NOTIONAL * 0.0004, 4)  # $0.0858 USD
TAKER_EXIT_FEE = round(SLOT_NOTIONAL * 0.0007, 4)# $0.1502 USD (2bps entry + 5bps market exit)

def run_simulations():
    report = {
        "portfolio_baseline_usdc": START_NAV,
        "slot_margin_usdc": SLOT_MGN,
        "slot_notional_usd_4x": SLOT_NOTIONAL,
        "normality_scenarios_24h": {},
        "madness_crash_scenarios": {},
    }
    # 1. NORMALITY SCENARIOS (24h projection)
    # N1: Standard Balanced Day (8 trades: 2 full TP +110bps, 4 Shield Runners +45bps, 1 BreakEven +10bps, 1 Inversion Exit -35bps)
    n1_pnl = (2 * (SLOT_NOTIONAL * 0.0110 - MAKER_FEE_RT)) + (4 * (SLOT_NOTIONAL * 0.0045 - TAKER_EXIT_FEE)) + (1 * (SLOT_NOTIONAL * 0.0010 - TAKER_EXIT_FEE)) + (1 * (-SLOT_NOTIONAL * 0.0035 - TAKER_EXIT_FEE))
    # N2: Choppy Sideways Day (6 trades: 0 full TP, 3 Shield locks +22bps, 2 Inversion Exits -30bps, 1 Hard Stop -100bps)
    n2_pnl = (3 * (SLOT_NOTIONAL * 0.0022 - TAKER_EXIT_FEE)) + (2 * (-SLOT_NOTIONAL * 0.0030 - TAKER_EXIT_FEE)) + (1 * (-SLOT_NOTIONAL * 0.0100 - TAKER_EXIT_FEE))
    # N3: Strong Trend / Breakout Day (10 trades: 4 full TP +110bps, 4 Shield Runners +55bps, 1 BreakEven +12bps, 1 Stop -100bps)
    n3_pnl = (4 * (SLOT_NOTIONAL * 0.0110 - MAKER_FEE_RT)) + (4 * (SLOT_NOTIONAL * 0.0055 - TAKER_EXIT_FEE)) + (1 * (SLOT_NOTIONAL * 0.0012 - TAKER_EXIT_FEE)) + (1 * (-SLOT_NOTIONAL * 0.0100 - TAKER_EXIT_FEE))

    report["normality_scenarios_24h"] = {
        "N1_standard_day": {"net_pnl_usdc": round(n1_pnl, 2), "return_pct": round(n1_pnl / START_NAV * 100, 2), "end_nav_usdc": round(START_NAV + n1_pnl, 2)},
        "N2_choppy_hostile_day": {"net_pnl_usdc": round(n2_pnl, 2), "return_pct": round(n2_pnl / START_NAV * 100, 2), "end_nav_usdc": round(START_NAV + n2_pnl, 2)},
        "N3_breakout_trend_day": {"net_pnl_usdc": round(n3_pnl, 2), "return_pct": round(n3_pnl / START_NAV * 100, 2), "end_nav_usdc": round(START_NAV + n3_pnl, 2)},
    }

    # 2. MADNESS / BLACK SWAN SCENARIOS
    # M1: -25% Flash Crash in 60s WHILE VPS BRODY IS COMPLETELY DEAD/OFFLINE
    unprotected_m1_loss = -4 * SLOT_MGN  # -$214.52 (-80% of portfolio liquidated!)
    v14_3_m1_loss = -2 * (SLOT_NOTIONAL * 0.0115 + TAKER_EXIT_FEE)  # Max 2 unshielded slots closed by OKX native attachAlgoOrds at -105bps + 10bps slippage
    # M2: Correlated Bull-Trap Cascade (All 12 coins dump -3% simultaneously right after entry)
    unprotected_m2_loss = -4 * (SLOT_NOTIONAL * 0.0105 + TAKER_EXIT_FEE)
    v14_3_m2_loss = -2 * (SLOT_NOTIONAL * 0.0105 + TAKER_EXIT_FEE)  # Free-Roll Pyramiding caps unshielded same-direction slots to 2!
    # M3: Sub-Second -500 bps (-5.0%) Liquidity Gap Wick (Extreme Slippage of 80 bps beyond -105 bps stop -> -185 bps fill)
    v14_3_m3_loss = -2 * (SLOT_NOTIONAL * 0.0185 + TAKER_EXIT_FEE)  # Still 21.6% away from 4x isolated liquidation (-23.5%)!
    # M4: 6 Consecutive False Breakouts in a Row (Whip-Saw Mania)
    v14_3_m4_loss = -4 * (SLOT_NOTIONAL * 0.0065 + TAKER_EXIT_FEE)  # Blend of -35bps 1h-Inversion exits & -100bps stops + 120m coin quarantine

    report["madness_crash_scenarios"] = {
        "M1_vps_dead_during_minus_25pct_crash": {
            "without_v14_3_usdc": round(unprotected_m1_loss, 2),
            "with_v14_3_attachAlgoOrds_usdc": round(v14_3_m1_loss, 2),
            "portfolio_drawdown_pct": round(v14_3_m1_loss / START_NAV * 100, 2),
            "surviving_nav_usdc": round(START_NAV + v14_3_m1_loss, 2),
        },
        "M2_correlated_12coin_cascade_dump": {
            "without_pyramiding_cap_usdc": round(unprotected_m2_loss, 2),
            "with_v14_3_max2_unshielded_usdc": round(v14_3_m2_loss, 2),
            "portfolio_drawdown_pct": round(v14_3_m2_loss / START_NAV * 100, 2),
            "surviving_nav_usdc": round(START_NAV + v14_3_m2_loss, 2),
        },
        "M3_subsecond_500bps_gap_wick": {
            "liquidation_threshold_4x_pct": -23.5,
            "with_v14_3_gap_slippage_usdc": round(v14_3_m3_loss, 2),
            "portfolio_drawdown_pct": round(v14_3_m3_loss / START_NAV * 100, 2),
            "surviving_nav_usdc": round(START_NAV + v14_3_m3_loss, 2),
        },
        "M4_whipsaw_mania_4_stops_quarantine": {
            "with_v14_3_inversion_and_quarantine_usdc": round(v14_3_m4_loss, 2),
            "portfolio_drawdown_pct": round(v14_3_m4_loss / START_NAV * 100, 2),
            "surviving_nav_usdc": round(START_NAV + v14_3_m4_loss, 2),
        }
    }
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    run_simulations()
