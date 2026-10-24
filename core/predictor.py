#!/usr/bin/env python3
"""
TRE PREDATOR v1.0 — Online Streaming Predictive Engine (RLS + Kalman Velocity)
Implements zero-overhead incremental Machine Learning in pure Python:
1. Recursive Least Squares (RLS) with Exponential Forgetting Factor (λ = 0.985)
   - Learns live weights w_t mapping [1, OBI, OFI, HawkesBurst, MicroShift, Momentum_1m, VPIN_Signed]
     to future realized short-horizon returns (in basis points).
   - Evaluates the previous step's prediction against the newly arrived mid_price and updates
     the covariance matrix P_t and weight vector w_t in O(d^2) time (~50 float ops).
2. 1D Price-Velocity Kalman Filter
   - Tracks smoothed fair price and instantaneous velocity (bps/sec) while filtering bid-ask bounce.
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.microstructure import MicrostructureSignal


@dataclass
class PredictionOutput:
    inst_id: str
    timestamp: float
    predicted_return_bps: float   # Expected short-horizon move in bps (e.g. +18.5 bps)
    kalman_velocity_bps: float    # Instantaneous filtered velocity in bps/step
    confidence: float             # [0.0, 1.0] model confidence based on hit-rate & directional alignment
    regime: str                   # "AGGRESSIVE_BREAKOUT" | "TOXIC_DIP_DEFENSE" | "ACTIVE_SCALP_MM" | "MEAN_REVERSION"
    recommended_buy_offset_bps: float
    recommended_sell_tp_bps: float
    allow_sniper_IOC: bool


class KalmanPriceVelocityFilter:
    """
    2-state Kalman Filter tracking [price, velocity] to separate real momentum from microstructure noise.
    """

    def __init__(self, process_var: float = 1e-5, meas_var: float = 1e-3):
        self.initialized = False
        self.price = 0.0
        self.velocity = 0.0  # relative return per second
        self.p00 = 1.0
        self.p01 = 0.0
        self.p10 = 0.0
        self.p11 = 1.0
        self.q = process_var
        self.r = meas_var
        self.last_ts = 0.0

    def update(self, obs_price: float, ts: float) -> Tuple[float, float]:
        if obs_price <= 0:
            return 0.0, 0.0
        if not self.initialized:
            self.price = obs_price
            self.velocity = 0.0
            self.last_ts = ts
            self.initialized = True
            return self.price, 0.0

        dt = max(0.05, min(60.0, ts - self.last_ts))
        self.last_ts = ts

        # Predict step
        pred_price = self.price * (1.0 + self.velocity * dt)
        p00 = self.p00 + dt * (self.p10 + self.p01) + (dt * dt) * self.p11 + self.q
        p01 = self.p01 + dt * self.p11
        p10 = self.p10 + dt * self.p11
        p11 = self.p11 + self.q

        # Innovation (normalized relative innovation)
        y = (obs_price - pred_price) / obs_price
        s = p00 + self.r
        k0 = p00 / s
        k1 = p10 / s

        self.price = pred_price + (k0 * y * obs_price)
        self.velocity = self.velocity + k1 * y

        self.p00 = (1.0 - k0) * p00
        self.p01 = (1.0 - k0) * p01
        self.p10 = -k1 * p00 + p10
        self.p11 = -k1 * p01 + p11

        velocity_bps = self.velocity * 10000.0
        return self.price, max(-150.0, min(150.0, velocity_bps))


class OnlineRLSPredictor:
    """
    Online Recursive Least Squares (RLS) with forgetting factor lambda.
    Dimension d = 6 features:
    x = [1.0, obi_top5, ofi_norm, hawkes_net_burst, composite_alpha, kalman_vel_norm]
    """

    def __init__(self, forgetting_factor: float = 0.985, delta_init: float = 10.0):
        self.d = 6
        self.lam = forgetting_factor
        # Prior weights informed by financial microstructure theory (positive impact of OBI/OFI/Hawkes)
        self.w: List[float] = [0.0, 8.0, 12.0, 9.0, 10.0, 6.0]
        # Covariance matrix P (d x d)
        self.P: List[List[float]] = [
            [delta_init if i == j else 0.0 for j in range(self.d)]
            for i in range(self.d)
        ]
        self.last_features: Optional[List[float]] = None
        self.last_price: Optional[float] = None
        self.total_updates: int = 0
        self.directional_hits: int = 0
        self.last_pred_bps: float = 0.0

    def _dot(self, a: List[float], b: List[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    def update_and_predict(self, features: List[float], current_price: float) -> Tuple[float, float]:
        # 1. If we have a previous observation, update RLS weights with realized return in bps
        if self.last_features is not None and self.last_price is not None and self.last_price > 0 and current_price > 0:
            realized_bps = ((current_price - self.last_price) / self.last_price) * 10000.0
            realized_bps = max(-200.0, min(200.0, realized_bps))

            if (self.last_pred_bps > 0.5 and realized_bps > 0) or (self.last_pred_bps < -0.5 and realized_bps < 0):
                self.directional_hits += 1
            self.total_updates += 1

            x = self.last_features
            # P * x
            Px = [sum(self.P[i][j] * x[j] for j in range(self.d)) for i in range(self.d)]
            denom = self.lam + self._dot(x, Px)
            if denom > 1e-9:
                gain = [px_i / denom for px_i in Px]
                pred_prev = self._dot(self.w, x)
                err = realized_bps - pred_prev
                # Update weights
                for i in range(self.d):
                    self.w[i] += gain[i] * err
                    # Clamp weights for numerical stability
                    self.w[i] = max(-60.0, min(60.0, self.w[i]))
                # Update P = (P - k * x^T * P) / lambda
                for i in range(self.d):
                    for j in range(self.d):
                        self.P[i][j] = (self.P[i][j] - gain[i] * Px[j]) / self.lam

        # 2. Predict next horizon return in bps
        pred_bps = self._dot(self.w, features)
        pred_bps = max(-120.0, min(120.0, pred_bps))

        self.last_features = features
        self.last_price = current_price
        self.last_pred_bps = pred_bps

        hit_rate = (self.directional_hits / self.total_updates) if self.total_updates >= 5 else 0.58
        return pred_bps, hit_rate


class PredatorPredictiveEngine:
    """
    Coordinates per-instrument Online RLS + Kalman filters and translates microstructure
    predictions into aggressive execution parameters (dynamic spread skewing & IOC breakout triggers).
    """

    def __init__(self, state_path: Optional[str] = None):
        self.rls_models: Dict[str, OnlineRLSPredictor] = {}
        self.kalman_filters: Dict[str, KalmanPriceVelocityFilter] = {}
        self.state_path = state_path
        if self.state_path and os.path.exists(self.state_path):
            self._load_state()

    def _load_state(self) -> None:
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for inst_id, mdata in data.get("models", {}).items():
                mod = OnlineRLSPredictor()
                if len(mdata.get("w", [])) == mod.d:
                    mod.w = mdata["w"]
                mod.total_updates = int(mdata.get("total_updates", 0))
                mod.directional_hits = int(mdata.get("directional_hits", 0))
                self.rls_models[inst_id] = mod
        except Exception:
            pass

    def save_state(self) -> None:
        if not self.state_path:
            return
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            payload = {
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "models": {
                    inst: {
                        "w": [round(x, 4) for x in mod.w],
                        "total_updates": mod.total_updates,
                        "directional_hits": mod.directional_hits,
                    }
                    for inst, mod in self.rls_models.items()
                },
            }
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass

    def evaluate(
        self,
        sig: MicrostructureSignal,
        inventory_weight_nav: float = 0.0,
        llm_conviction_bias: float = 0.0,
        kronos_return_1h_bps: float = 0.0,
        kronos_upside_bps: float = 0.0,
        kronos_downside_bps: float = 0.0,
        kronos_macro_2h_bps: float = 0.0,
        kronos_swing_12h_bps: float = 0.0,
        kronos_horizon_aligned: bool = False,
        btc_lead_lag_bps: float = 0.0,
    ) -> PredictionOutput:
        inst = sig.inst_id
        if inst not in self.kalman_filters:
            self.kalman_filters[inst] = KalmanPriceVelocityFilter()
        if inst not in self.rls_models:
            self.rls_models[inst] = OnlineRLSPredictor()

        _, k_vel_bps = self.kalman_filters[inst].update(sig.micro_price, sig.timestamp)
        k_vel_norm = max(-1.0, min(1.0, k_vel_bps / 25.0))

        features = [
            1.0,
            sig.obi_top5,
            sig.ofi_norm,
            sig.hawkes_net_burst,
            sig.composite_alpha,
            k_vel_norm,
        ]
        raw_pred_bps, hit_rate = self.rls_models[inst].update_and_predict(features, sig.mid_price)

        # Blend online RLS microstructure prediction (45%) + Kronos 3-Horizon (35%: 5m + 15m + 1H with Macro Trend Veto!) + LLM Council + BTC Lead-Lag (20%)
        eff_k1h = kronos_return_1h_bps
        # Macro Trend Veto: if 2h macro trend is strongly bearish (< -20 bps) or 12h swing is bearish (< -30 bps),
        # discount 5m counter-trend mean-reversion noise by 80% so it never fools us into buying a falling knife!
        if eff_k1h > 0 and (kronos_macro_2h_bps < -20.0 or kronos_swing_12h_bps < -30.0) and not kronos_horizon_aligned:
            eff_k1h = eff_k1h * 0.20

        if kronos_swing_12h_bps != 0.0:
            kronos_combo_bps = 0.50 * eff_k1h + 0.30 * kronos_macro_2h_bps + 0.20 * (kronos_swing_12h_bps * 0.35)
        elif kronos_macro_2h_bps != 0.0:
            kronos_combo_bps = 0.65 * eff_k1h + 0.35 * kronos_macro_2h_bps
        else:
            kronos_combo_bps = eff_k1h

        blended_pred_bps = (
            0.45 * raw_pred_bps
            + 0.35 * kronos_combo_bps
            + 0.12 * (llm_conviction_bias * 25.0)
            + 0.08 * btc_lead_lag_bps
        )

        # Confidence combines model hit-rate, signal magnitude, and Kronos Multi-Horizon directional agreement
        signal_strength = min(1.0, abs(sig.composite_alpha) * 1.35)
        kronos_agreement = 0.12 if (kronos_horizon_aligned and (raw_pred_bps * kronos_return_1h_bps > 0)) else (
            0.06 if (raw_pred_bps * kronos_return_1h_bps > 0) else 0.0
        )
        confidence = round(min(0.98, max(0.35, 0.50 * hit_rate + 0.40 * signal_strength + kronos_agreement)), 4)

        # Determine Regime & Dynamic Offsets (in bps; 100 bps = 1.00%)
        # Inventory skew penalty (Cartea-Jaimungal): high inventory lowers TP and widens buy offset
        inv_skew_bps = max(-15.0, min(35.0, (inventory_weight_nav - 0.10) * 180.0))
        # BTC Shock Absorber: if BTC is dumping sharply (< -12 bps), widen buy traps automatically!
        btc_shock_widen_bps = max(0.0, min(45.0, abs(btc_lead_lag_bps) * 1.8)) if btc_lead_lag_bps < -10.0 else 0.0

        allow_sniper_ioc = False
        if (
            blended_pred_bps >= 12.0
            and sig.composite_alpha >= 0.48
            and sig.vpin_toxicity < 0.72
            and confidence >= 0.60
            and inventory_weight_nav < 0.18
            and btc_lead_lag_bps >= -6.0
        ):
            regime = "AGGRESSIVE_BREAKOUT"
            buy_offset_bps = max(3.0, 7.0 + inv_skew_bps * 0.5 + btc_shock_widen_bps)
            base_tp = max(32.0, kronos_upside_bps * 0.85) if kronos_upside_bps > 0 else 48.0
            if kronos_horizon_aligned and kronos_return_1h_bps > 0:
                base_tp = min(90.0, base_tp * 1.20)  # Multi-Horizon Turbo-Scalp TP boost!
            sell_tp_bps = max(28.0, min(95.0, base_tp + blended_pred_bps * 0.8 - inv_skew_bps))
            allow_sniper_ioc = True
        elif (sig.vpin_toxicity >= 0.68 and sig.composite_alpha < -0.30) or btc_lead_lag_bps < -12.0:
            regime = "TOXIC_DIP_DEFENSE"
            k_down = max(65.0, kronos_downside_bps * 1.15) if kronos_downside_bps > 0 else 85.0
            buy_offset_bps = max(65.0, min(165.0, k_down + abs(blended_pred_bps) * 1.0 + inv_skew_bps + btc_shock_widen_bps))
            sell_tp_bps = max(18.0, 28.0 - inv_skew_bps * 0.6)
        elif abs(blended_pred_bps) <= 6.5 and sig.vpin_toxicity < 0.45:
            regime = "ACTIVE_SCALP_MM"
            k_down = max(10.0, min(26.0, kronos_downside_bps * 0.60)) if kronos_downside_bps > 0 else 15.0
            k_up = max(22.0, min(52.0, kronos_upside_bps * 0.80)) if kronos_upside_bps > 0 else 30.0
            buy_offset_bps = max(9.0, k_down - blended_pred_bps * 0.4 + inv_skew_bps + btc_shock_widen_bps)
            sell_tp_bps = max(20.0, k_up + blended_pred_bps * 0.4 - inv_skew_bps)
        else:
            regime = "MEAN_REVERSION"
            k_down = max(15.0, min(55.0, kronos_downside_bps * 0.75)) if kronos_downside_bps > 0 else 26.0
            k_up = max(24.0, min(72.0, kronos_upside_bps * 0.85)) if kronos_upside_bps > 0 else 38.0
            buy_offset_bps = max(14.0, k_down - blended_pred_bps * 0.5 + inv_skew_bps + btc_shock_widen_bps)
            sell_tp_bps = max(22.0, k_up + blended_pred_bps * 0.5 - inv_skew_bps)

        return PredictionOutput(
            inst_id=inst,
            timestamp=sig.timestamp,
            predicted_return_bps=round(blended_pred_bps, 2),
            kalman_velocity_bps=round(k_vel_bps, 2),
            confidence=confidence,
            regime=regime,
            recommended_buy_offset_bps=round(buy_offset_bps, 2),
            recommended_sell_tp_bps=round(sell_tp_bps, 2),
            allow_sniper_IOC=allow_sniper_ioc,
        )
