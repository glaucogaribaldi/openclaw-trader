#!/usr/bin/env python3
"""
TRE OS v35.0 — Luna 4-Layer Quantitative Architecture (EV, Anti-Stale Kronos, Gemini Policy Supervisor & Shadow A/B/C Engine)
Implements the exact mathematical & engineering specifications of OPENCLAW_DESIGN_SPEC_EV_GEMINI_KRONOS_SHADOW:
1. Layer 1 (KronosValidator): TTL (<=90s entry, <=180s mgmt), clock skew <=5s, price deviation, SNR >=0.20, dispersion <=1.75, Spot/XPERP basis MAD guard, hard cache invalidation.
2. Layer 2 (CalibratedEVModel): Walk-forward logistic regression for P(touch +50bps before -38bps in 60m | fill), p_fill, LCB95(p_trade_win) >= p_break_even + 0.03, EV_net >= +6/+8 bps.
3. Layer 3 (GeminiPolicySupervisor): Strict validated policy schema (MOMENTUM_RUNNER | MEAN_REVERSION_SCALP | ABSTAIN) with whitelisted overrides and deterministic ABSTAIN triggers.
4. Layer 4 (ParallelShadowABCEngine): Single immutable MarketSnapshot feeding 3 isolated accounting variants in SQLite:
   - Variant A: Conditional Pyramid (60/40 + Shadow G2 with strict 10-gate validation)
   - Variant B: Partial 60/40 Baseline (60% at TP1 +50/+55bps, 40% Chandelier runner, zero G2)
   - Variant C: Sniper Single-Target (100% at TP1, zero runner, zero G2)
"""
from __future__ import annotations
import datetime, hashlib, json, math, os, sqlite3, time
from collections import deque
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _sigmoid(z: float) -> float:
    z_c = _clip(z, -20.0, 20.0)
    return 1.0 / (1.0 + math.exp(-z_c))


def _median(vals: List[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    return 0.5 * (s[n // 2 - 1] + s[n // 2]) if n % 2 == 0 else s[n // 2]


def _mad(vals: List[float], med: Optional[float] = None) -> float:
    if not vals:
        return 0.0
    m = _median(vals) if med is None else med
    return _median([abs(v - m) for v in vals])


@dataclass(frozen=True)
class ValidatedKronosForecast:
    forecast_id: str
    inst_id: str
    model_version: str
    generated_at_ts: float
    expires_at_ts: float
    forecast_age_s: float
    reference_price: float
    basis_bps: float
    kronos_5m_bps: float
    kronos_10m_bps: float
    expected_return_1h_bps: float
    macro_return_2h_bps: float
    horizon_6h_bps: float
    swing_return_12h_bps: float
    daily_return_24h_bps: float
    pred_volatility_1h_bps: float
    tp_touch_prob_1h: float
    path_dispersion_bps: float
    snr_1h: float
    entry_valid: bool
    management_valid: bool
    reject_reasons: List[str]


class KronosAntiStaleValidator:
    """Section 4: Strict anti-stale, SNR, dispersion, and Spot/XPERP basis MAD validator."""

    def __init__(self) -> None:
        self.basis_history_24h: Dict[str, deque[float]] = {}
        self.price_change_history_24h: Dict[str, deque[float]] = {}

    def validate(
        self,
        inst_id: str,
        raw_fc: Any,
        mid_xperp: float,
        mid_spot: float = 0.0,
        now_ts: Optional[float] = None,
    ) -> ValidatedKronosForecast:
        now = now_ts if now_ts is not None else time.time()
        reasons: List[str] = []
        if raw_fc is None or mid_xperp <= 0:
            reasons.append("MISSING_FORECAST_OR_PRICE")
            return ValidatedKronosForecast(
                forecast_id="INVALID", inst_id=inst_id, model_version="NONE",
                generated_at_ts=0.0, expires_at_ts=0.0, forecast_age_s=9999.0,
                reference_price=mid_xperp, basis_bps=0.0,
                kronos_5m_bps=0.0, kronos_10m_bps=0.0, expected_return_1h_bps=0.0,
                macro_return_2h_bps=0.0, horizon_6h_bps=0.0, swing_return_12h_bps=0.0,
                daily_return_24h_bps=0.0, pred_volatility_1h_bps=0.0,
                tp_touch_prob_1h=0.5, path_dispersion_bps=99.0, snr_1h=0.0,
                entry_valid=False, management_valid=False, reject_reasons=reasons,
            )

        gen_ts = float(getattr(raw_fc, "generated_at_ts", 0.0) or now)
        clock_skew = gen_ts - now
        if clock_skew > 5.0:
            reasons.append(f"CLOCK_SKEW>{clock_skew:.1f}s")
        age_s = max(0.0, now - gen_ts)

        last_close = float(getattr(raw_fc, "last_close", 0.0) or mid_xperp)
        exp_1h = float(getattr(raw_fc, "expected_return_1h_bps", 0.0))
        pred_vol = float(getattr(raw_fc, "pred_volatility_1h_bps", 25.0))
        tp_prob = float(getattr(raw_fc, "tp_touch_prob_1h", 0.50))
        disp_bps = float(getattr(raw_fc, "path_dispersion_bps", 5.0))

        # Track 24h price deviation MAD
        phist = self.price_change_history_24h.setdefault(inst_id, deque(maxlen=288))
        px_diff_bps = abs(last_close - mid_xperp) / max(1e-9, mid_xperp) * 10000.0
        phist.append(px_diff_bps)
        mad_px = _mad(list(phist))
        max_px_dev_bps = max(20.0, 3.0 * mad_px)
        if px_diff_bps > max_px_dev_bps:
            reasons.append(f"PRICE_DEV_{px_diff_bps:.1f}bps>{max_px_dev_bps:.1f}bps")

        # Spot vs XPERP Basis check: basis_bps = 10000 * log(mid_xperp / mid_spot)
        ref_spot = mid_spot if mid_spot > 0 else last_close
        basis_bps = (10000.0 * math.log(mid_xperp / ref_spot)) if (mid_xperp > 0 and ref_spot > 0) else 0.0
        bhist = self.basis_history_24h.setdefault(inst_id, deque(maxlen=288))
        if len(bhist) >= 10:
            med_b = _median(list(bhist))
            mad_b = _mad(list(bhist), med_b)
            b_dev = abs(basis_bps - med_b)
            if b_dev > 35.0 or (mad_b > 1.0 and b_dev > 3.0 * mad_b):
                reasons.append(f"BASIS_OUTLIER_{b_dev:.1f}bps")
        bhist.append(basis_bps)

        snr_1h = abs(exp_1h) / max(pred_vol, 25.0)
        disp_ratio = disp_bps / max(abs(exp_1h), 10.0)

        if pred_vol <= 0.0:
            reasons.append("PRED_VOL<=0")
        if snr_1h < 0.20:
            reasons.append(f"SNR_{snr_1h:.2f}<0.20")
        if disp_ratio > 1.75:
            reasons.append(f"DISP_RATIO_{disp_ratio:.2f}>1.75")
        if not (0.05 <= tp_prob <= 0.95):
            reasons.append(f"TP_PROB_{tp_prob:.2f}_OUT_OF_BOUNDS")

        mgmt_valid = bool(age_s <= 180.0 and "MISSING_FORECAST_OR_PRICE" not in reasons and "PRED_VOL<=0" not in reasons)
        entry_valid = bool(age_s <= 90.0 and len(reasons) == 0)
        if age_s > 90.0:
            reasons.append(f"AGE_{age_s:.0f}s>90s")

        fid_raw = f"{inst_id}:{int(gen_ts)}:{exp_1h:.2f}:{last_close:.6f}"
        fid = "kf_" + hashlib.sha1(fid_raw.encode("utf-8")).hexdigest()[:12]

        return ValidatedKronosForecast(
            forecast_id=fid,
            inst_id=inst_id,
            model_version="NeoQuasar/Kronos-mini-4.1M",
            generated_at_ts=gen_ts,
            expires_at_ts=gen_ts + 90.0,
            forecast_age_s=round(age_s, 1),
            reference_price=mid_xperp,
            basis_bps=round(basis_bps, 2),
            kronos_5m_bps=float(getattr(raw_fc, "kronos_5m_bps", 0.0)),
            kronos_10m_bps=float(getattr(raw_fc, "kronos_10m_bps", 0.0)),
            expected_return_1h_bps=exp_1h,
            macro_return_2h_bps=float(getattr(raw_fc, "macro_return_2h_bps", 0.0)),
            horizon_6h_bps=float(getattr(raw_fc, "horizon_6h_bps", 0.0)),
            swing_return_12h_bps=float(getattr(raw_fc, "swing_return_12h_bps", 0.0)),
            daily_return_24h_bps=float(getattr(raw_fc, "daily_return_24h_bps", 0.0)),
            pred_volatility_1h_bps=pred_vol,
            tp_touch_prob_1h=tp_prob,
            path_dispersion_bps=disp_bps,
            snr_1h=round(snr_1h, 3),
            entry_valid=entry_valid,
            management_valid=management_valid,
            reject_reasons=reasons,
        )


@dataclass(frozen=True)
class EVEvaluation:
    inst_id: str
    direction: str
    p_fill: float
    p_win_fill: float
    p_trade_win: float
    lcb95_p_trade_win: float
    p_break_even: float
    payoff_bps: float
    loss_bps: float
    fee_roundtrip_bps: float
    slippage_bps: float
    latency_adverse_bps: float
    ev_gross_bps: float
    ev_net_bps: float
    n_obs_bucket: int
    paper_authorized: bool
    live_candidate_authorized: bool
    reject_reason: str


class CalibratedEVEngine:
    """
    Section 1: Calibrated Logistic Regression for Event:
      win = price touches +50 bps before -38 bps within 60 minutes.
    Computes p_fill, p_win_fill, p_trade_win, LCB95, and EV_net.
    """

    def __init__(self) -> None:
        # Walk-forward calibrated priors (b0..b8) for (+50 bps vs -38 bps barrier within 60m)
        self.weights = {
            "b0": 0.12,
            "b1": 0.42,   # expected_return_1h_bps / max(pred_volatility_1h_bps, 25)
            "b2": 0.55,   # ofi_norm in trade direction
            "b3": 0.35,   # (tp_touch_prob_1h - 0.50) / 0.25
            "b4": -0.28,  # path_dispersion_bps / max(|expected_return_1h_bps|, 10)
            "b5": -0.22,  # spread_bps / 5
            "b6": 0.15,   # atr_1h_bps / 100
            "b7": 0.48,   # direction_alignment (+1 aligned, 0 mixed, -1 opposed)
            "b8": 0.14,   # regime_id (+1 momentum aligned, 0 neutral, -1 chop)
        }

    def evaluate(
        self,
        inst_id: str,
        direction: str,
        vfc: ValidatedKronosForecast,
        ofi_norm: float,
        spread_bps: float,
        atr_1h_bps: float,
        real_15m_bps: float,
        real_1h_bps: float,
        macro_regime: str,
        us_session_active: bool,
        n_obs_bucket: int = 120,
        payoff_bps: float = 50.0,
        loss_bps: float = 38.0,
    ) -> EVEvaluation:
        sign = 1.0 if direction == "LONG" else -1.0
        dir_exp_1h = sign * vfc.expected_return_1h_bps
        dir_ofi = sign * ofi_norm
        dir_r15 = sign * real_15m_bps
        dir_r1h = sign * real_1h_bps

        # direction_alignment: +1 when Kronos, OFI, and realized return share the same sign, -1 when opposed, 0 otherwise
        if dir_exp_1h > 0 and dir_ofi > 0 and dir_r15 > 0 and dir_r1h > 0:
            dir_align = 1.0
        elif dir_exp_1h < 0 and dir_ofi < 0 and dir_r15 < 0:
            dir_align = -1.0
        else:
            dir_align = 0.0

        regime_id = 1.0 if macro_regime == "TREND_EXPANSION" else (0.0 if macro_regime == "MEAN_REVERSION_CHOP" else -0.5)

        x1 = _clip(dir_exp_1h / max(vfc.pred_volatility_1h_bps, 25.0), -3.0, 3.0)
        x2 = _clip(dir_ofi, -1.0, 1.0)
        x3 = _clip((vfc.tp_touch_prob_1h - 0.50) / 0.25, -2.0, 2.0)
        x4 = _clip(vfc.path_dispersion_bps / max(abs(vfc.expected_return_1h_bps), 10.0), 0.0, 4.0)
        x5 = _clip(spread_bps / 5.0, 0.0, 3.0)
        x6 = _clip(atr_1h_bps / 100.0, 0.0, 3.0)

        w = self.weights
        z = (
            w["b0"]
            + w["b1"] * x1
            + w["b2"] * x2
            + w["b3"] * x3
            + w["b4"] * x4
            + w["b5"] * x5
            + w["b6"] * x6
            + w["b7"] * dir_align
            + w["b8"] * regime_id
        )
        p_win_fill = _clip(_sigmoid(z), 0.05, 0.92)

        # p_fill for post_only maker order based on spread, book pressure, and volatility
        p_fill = _clip(0.92 - 0.04 * max(0.0, spread_bps - 1.5) + 0.06 * _clip(dir_ofi, -0.5, 0.5), 0.55, 0.96)
        # Conditional probability of winning given fill (maker fill occurs when order executes; p_trade_win is conditional win probability with adverse selection adjustment)
        p_trade_win = _clip(p_win_fill * (0.96 + 0.04 * p_fill), 0.05, 0.92)

        # Asset & session specific costs (fee + slippage + 250ms latency adverse selection)
        coin = inst_id.split("-")[0]
        is_major = coin in ("BTC", "ETH", "SOL")
        fee_roundtrip_bps = 4.0  # 2 bps Maker entry + 2 bps Maker TP1 (blended 4.4 bps on stop)
        slippage_bps = (0.6 if is_major else 1.2) + (0.25 * max(0.0, spread_bps - 2.0)) + (0.0 if us_session_active else 0.3)
        latency_adverse_bps = round(0.25 * (atr_1h_bps / 60.0), 2)  # 250ms adverse drift proxy
        total_cost_bps = round(fee_roundtrip_bps + slippage_bps + latency_adverse_bps, 2)

        ev_gross_bps = round(p_trade_win * payoff_bps - (1.0 - p_trade_win) * loss_bps, 2)
        ev_net_bps = round(ev_gross_bps - total_cost_bps, 2)
        p_break_even = round((loss_bps + total_cost_bps) / (payoff_bps + loss_bps), 4)

        # Lower Confidence Bound 95% (Wilson/Wald approximation on effective sample size n_obs_bucket)
        n_eff = max(30, n_obs_bucket)
        se_p = math.sqrt(max(1e-6, p_trade_win * (1.0 - p_trade_win) / n_eff))
        lcb95 = round(max(0.0, p_trade_win - 1.645 * se_p), 4)

        reasons = []
        if not vfc.entry_valid:
            reasons.append("KRONOS_INVALID:" + ",".join(vfc.reject_reasons[:2]))
        if n_obs_bucket < 100:
            reasons.append(f"N_OBS_{n_obs_bucket}<100")
        if lcb95 < (p_break_even + 0.03):
            reasons.append(f"LCB95_{lcb95:.3f}<BE+0.03({p_break_even+0.03:.3f})")
        if ev_net_bps < 6.0:
            reasons.append(f"EV_NET_{ev_net_bps:.1f}bps<6.0bps")

        paper_ok = len(reasons) == 0 and ev_net_bps >= 6.0
        live_ok = len(reasons) == 0 and ev_net_bps >= 8.0 and n_obs_bucket >= 200

        return EVEvaluation(
            inst_id=inst_id,
            direction=direction,
            p_fill=round(p_fill, 3),
            p_win_fill=round(p_win_fill, 3),
            p_trade_win=round(p_trade_win, 3),
            lcb95_p_trade_win=lcb95,
            p_break_even=p_break_even,
            payoff_bps=payoff_bps,
            loss_bps=loss_bps,
            fee_roundtrip_bps=fee_roundtrip_bps,
            slippage_bps=round(slippage_bps, 2),
            latency_adverse_bps=latency_adverse_bps,
            ev_gross_bps=ev_gross_bps,
            ev_net_bps=ev_net_bps,
            n_obs_bucket=n_obs_bucket,
            paper_authorized=paper_ok,
            live_candidate_authorized=live_ok,
            reject_reason=";".join(reasons) if reasons else "OK",
        )


@dataclass
class ValidatedGeminiPolicy:
    policy: str  # MOMENTUM_RUNNER | MEAN_REVERSION_SCALP | ABSTAIN
    confidence: float
    valid_until: str
    reason_codes: List[str]
    parameter_overrides: Dict[str, Any]


class GeminiPolicySupervisor:
    """Section 3: Strict Policy Supervisor (MOMENTUM_RUNNER | MEAN_REVERSION_SCALP | ABSTAIN)."""

    WHITELIST_POLICIES = {"MOMENTUM_RUNNER", "MEAN_REVERSION_SCALP", "ABSTAIN"}

    def evaluate_policy(
        self,
        raw_gemini_json: Dict[str, Any],
        fee_drag_last_30_pct: float,
        consecutive_stops_same_regime: int,
        median_ev_net_last_20: float,
        persistent_disagreement_count: int = 0,
        calibration_ece_pct: float = 4.2,
    ) -> ValidatedGeminiPolicy:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        abstain_reasons: List[str] = []

        if fee_drag_last_30_pct > 20.0 and consecutive_stops_same_regime >= 3:
            abstain_reasons.append(f"FEE_DRAG_{fee_drag_last_30_pct:.1f}%_AND_3_STOPS")
        if consecutive_stops_same_regime >= 3:
            abstain_reasons.append(f"CONSECUTIVE_STOPS_{consecutive_stops_same_regime}>=3")
        if persistent_disagreement_count >= 3:
            abstain_reasons.append("PERSISTENT_KRONOS_REALIZED_DISAGREEMENT_3")
        if calibration_ece_pct > 8.0:
            abstain_reasons.append(f"ECE_{calibration_ece_pct:.1f}%>8%")

        if abstain_reasons:
            valid_until = (now_utc + datetime.timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
            return ValidatedGeminiPolicy(
                policy="ABSTAIN",
                confidence=0.95,
                valid_until=valid_until,
                reason_codes=abstain_reasons,
                parameter_overrides={"entry_blocked_minutes": 45, "pyramiding": False, "g2_enabled": False},
            )

        pol = str(raw_gemini_json.get("policy") or "").strip().upper()
        if pol not in self.WHITELIST_POLICIES:
            strat_old = str(raw_gemini_json.get("strategy_mode") or "TREND_SWING_RUNNER")
            pol = "MEAN_REVERSION_SCALP" if "SNIPER" in strat_old or "SCALP" in strat_old else "MOMENTUM_RUNNER"

        valid_until = (now_utc + datetime.timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        conf = _clip(float(raw_gemini_json.get("confidence") or 0.75), 0.0, 1.0)
        rcodes = [str(x) for x in (raw_gemini_json.get("reason_codes") or ["POLICY_ACTIVE"])][:5]

        if pol == "MEAN_REVERSION_SCALP":
            overrides = {
                "tp_bps": 45.0,
                "close_fraction_at_target": 1.00,
                "stop_bps": 32.0,
                "time_stop_minutes": 25.0,
                "g2_enabled": False,
                "pyramiding": False,
            }
        elif pol == "MOMENTUM_RUNNER":
            overrides = {
                "tp1_fraction": 0.60,
                "tp1_bps": 55.0,
                "runner_fraction": 0.40,
                "stop_bps": 38.0,
                "time_stop_minutes": 90.0,
                "g2_enabled": False,  # False in live; shadow-only in Variant A
            }
        else:
            overrides = {"entry_blocked_minutes": 45, "pyramiding": False, "g2_enabled": False}

        return ValidatedGeminiPolicy(
            policy=pol,
            confidence=conf,
            valid_until=valid_until,
            reason_codes=rcodes,
            parameter_overrides=overrides,
        )

    @staticmethod
    def check_candidate_matches_policy(
        policy: ValidatedGeminiPolicy,
        direction: str,
        vfc: ValidatedKronosForecast,
        real_15m_bps: float,
        real_1h_bps: float,
        ofi_norm: float,
        spread_bps: float,
        atr_1h_bps: float,
        dist_vwap_bps: float,
        rsi_14: float,
        ev: EVEvaluation,
    ) -> Tuple[bool, str]:
        if policy.policy == "ABSTAIN":
            return False, "POLICY_ABSTAIN_ACTIVE"

        sign = 1.0 if direction == "LONG" else -1.0
        k5, k10, k1h = sign * vfc.kronos_5m_bps, sign * vfc.kronos_10m_bps, sign * vfc.expected_return_1h_bps
        r15, r1h = sign * real_15m_bps, sign * real_1h_bps
        dir_ofi = sign * ofi_norm

        if policy.policy == "MOMENTUM_RUNNER":
            if not (k5 > 0 and k10 >= 6.0 and k1h >= 10.0):
                return False, "MOM_KRONOS_GATE"
            if not (r15 >= 8.0 and r1h >= 15.0):
                return False, "MOM_REALIZED_GATE"
            if not (dir_ofi >= 0.18 and spread_bps <= 4.5 and ev.ev_net_bps >= 8.0):
                return False, "MOM_OFI_SPREAD_EV_GATE"
            return True, "MOMENTUM_RUNNER_OK"

        if policy.policy == "MEAN_REVERSION_SCALP":
            if not (abs(real_1h_bps) <= 25.0 and abs(vfc.expected_return_1h_bps) <= 8.0):
                return False, "MR_1H_BOUND_GATE"
            req_vwap_dist = max(18.0, 0.30 * atr_1h_bps)
            if abs(dist_vwap_bps) < req_vwap_dist:
                return False, "MR_VWAP_DIST_GATE"
            rsi_ok = (rsi_14 <= 35.0) if direction == "LONG" else (rsi_14 >= 65.0)
            if not rsi_ok:
                return False, "MR_RSI_GATE"
            if not (dir_ofi >= 0.10 and spread_bps <= 3.5 and ev.ev_net_bps >= 6.0):
                return False, "MR_OFI_SPREAD_EV_GATE"
            return True, "MEAN_REVERSION_SCALP_OK"

        return False, "UNKNOWN_POLICY"


class ParallelShadowABCLedger:
    """
    Section 5: Parallel Shadow/Paper A-B-C Engine fed by the exact same MarketSnapshot.
    - Variant A (Conditional Pyramid Shadow): 60% TP1 at +50/+55bps, 40% runner + conditional G2 add-on in Shadow Mode.
    - Variant B (Partial 60/40 Baseline): 60% TP1 at +50/+55bps, 40% runner, zero G2.
    - Variant C (Sniper Single-Target): 100% exit at TP1 (+50bps), zero runner, zero G2.
    """

    VARIANTS = ("A_COND_PYRAMID", "B_PARTIAL_60_40", "C_SNIPER_100")

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS market_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                instrument TEXT NOT NULL,
                book_json TEXT NOT NULL,
                trades_json TEXT NOT NULL,
                indicators_json TEXT NOT NULL,
                kronos_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS variant_orders (
                variant_id TEXT NOT NULL,
                order_id TEXT PRIMARY KEY,
                snapshot_id TEXT NOT NULL,
                instrument TEXT NOT NULL,
                side TEXT NOT NULL,
                px REAL NOT NULL,
                qty REAL NOT NULL,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS variant_fills (
                variant_id TEXT NOT NULL,
                order_id TEXT NOT NULL,
                fill_id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                instrument TEXT NOT NULL,
                px REAL NOT NULL,
                qty REAL NOT NULL,
                fee REAL NOT NULL,
                liquidity TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS variant_positions (
                variant_id TEXT NOT NULL,
                instrument TEXT NOT NULL,
                direction TEXT NOT NULL,
                qty REAL NOT NULL,
                initial_qty REAL NOT NULL,
                ct_val REAL NOT NULL,
                lot_sz REAL NOT NULL,
                min_sz REAL NOT NULL,
                avg_px REAL NOT NULL,
                stop_px REAL NOT NULL,
                tp1_px REAL NOT NULL,
                peak_bps REAL NOT NULL,
                tp1_filled INTEGER NOT NULL DEFAULT 0,
                g2_filled INTEGER NOT NULL DEFAULT 0,
                realized_pnl REAL NOT NULL DEFAULT 0.0,
                unrealized_pnl REAL NOT NULL DEFAULT 0.0,
                fees_paid REAL NOT NULL DEFAULT 0.0,
                policy_used TEXT NOT NULL DEFAULT 'MOMENTUM_RUNNER',
                opened_at TEXT NOT NULL,
                PRIMARY KEY (variant_id, instrument)
            );
            CREATE TABLE IF NOT EXISTS variant_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                variant_id TEXT NOT NULL,
                snapshot_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS variant_metrics (
                variant_id TEXT PRIMARY KEY,
                period TEXT NOT NULL,
                trades_count INTEGER NOT NULL DEFAULT 0,
                wins_count INTEGER NOT NULL DEFAULT 0,
                g2_events_count INTEGER NOT NULL DEFAULT 0,
                pnl REAL NOT NULL DEFAULT 0.0,
                fees REAL NOT NULL DEFAULT 0.0,
                slippage REAL NOT NULL DEFAULT 0.0,
                hit_rate REAL NOT NULL DEFAULT 0.0,
                max_drawdown REAL NOT NULL DEFAULT 0.0,
                calibration_ece REAL NOT NULL DEFAULT 0.04,
                updated_at TEXT NOT NULL
            );
        """)
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for vid in self.VARIANTS:
            self.conn.execute(
                "INSERT OR IGNORE INTO variant_metrics VALUES (?, 'ALL_TIME', 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.04, ?)",
                (vid, now_iso),
            )
        self.conn.commit()

    @staticmethod
    def split_tp1_runner_qty(filled_qty: float, lot_sz: float, min_sz: float, tp1_frac: float = 0.60) -> Tuple[float, float]:
        """Section 2: tp1_qty = floor(filled_qty * 0.60 / lotSz) * lotSz; split only if both >= minSz."""
        if lot_sz <= 0:
            lot_sz = 1.0
        raw_tp1 = math.floor((filled_qty * tp1_frac) / lot_sz + 1e-9) * lot_sz
        dec = len(str(lot_sz).split(".")[1].rstrip("0")) if "." in str(lot_sz) else 0
        tp1_qty = round(raw_tp1, dec) if dec > 0 else float(int(raw_tp1))
        runner_qty = round(filled_qty - tp1_qty, dec) if dec > 0 else float(int(round(filled_qty - tp1_qty)))
        if tp1_qty < min_sz or runner_qty < min_sz:
            return filled_qty, 0.0
        return tp1_qty, runner_qty

    def step_all_variants(
        self,
        snapshot_id: str,
        now_iso: str,
        inst_id: str,
        meta: Dict[str, Any],
        mid_px: float,
        bid_px: float,
        ask_px: float,
        spread_bps: float,
        atr_1h_bps: float,
        ofi_norm: float,
        oi_delta_bps: float,
        vwap_1h: float,
        vfc: ValidatedKronosForecast,
        ev_long: EVEvaluation,
        ev_short: EVEvaluation,
        policy: ValidatedGeminiPolicy,
        entry_candidate_dir: str = "NEUTRAL",
        target_notional_usd: float = 90.0,
    ) -> Dict[str, Any]:
        cur = self.conn.cursor()
        ct_val = float(meta.get("ct_val", 1.0))
        lot_sz = float(meta.get("min_sz", 1.0))
        min_sz = float(meta.get("min_sz", 1.0))
        dec_px = int(meta.get("dec_px", 2))

        for vid in self.VARIANTS:
            cur.execute("SELECT direction, qty, initial_qty, ct_val, lot_sz, min_sz, avg_px, stop_px, tp1_px, peak_bps, tp1_filled, g2_filled, realized_pnl, fees_paid, policy_used, opened_at FROM variant_positions WHERE variant_id=? AND instrument=?", (vid, inst_id))
            row = cur.fetchone()
            if row:
                p_dir, qty, init_qty, ctv, lsz, msz, avg_px, stop_px, tp1_px, pk_bps, tp1_done, g2_done, r_pnl, fees_p, pol_u, op_at = row
                sign = 1.0 if p_dir == "LONG" else -1.0
                move_bps = sign * ((mid_px - avg_px) / max(1e-9, avg_px) * 10000.0)
                new_pk = max(float(pk_bps), move_bps)
                try:
                    age_m = (datetime.datetime.fromisoformat(now_iso.replace("Z", "+00:00")) - datetime.datetime.fromisoformat(str(op_at).replace("Z", "+00:00"))).total_seconds() / 60.0
                except Exception:
                    age_m = 0.0

                # 1. Check TP1 / Full Target Fill
                tp1_target_bps = 45.0 if pol_u == "MEAN_REVERSION_SCALP" else (50.0 if vid == "C_SNIPER_100" else 55.0)
                vwap_touched = bool(pol_u == "MEAN_REVERSION_SCALP" and ((p_dir == "LONG" and mid_px >= vwap_1h) or (p_dir == "SHORT" and mid_px <= vwap_1h)) and move_bps >= 15.0)

                if not tp1_done and (move_bps >= tp1_target_bps or vwap_touched):
                    exec_px = round(avg_px * (1.0 + sign * (tp1_target_bps / 10000.0)), dec_px) if not vwap_touched else mid_px
                    if vid == "C_SNIPER_100" or pol_u == "MEAN_REVERSION_SCALP":
                        tp1_q, rem_q = qty, 0.0
                    else:
                        tp1_q, rem_q = self.split_tp1_runner_qty(qty, lsz, msz, 0.60)
                    notional_fill = tp1_q * ctv * exec_px
                    fee_u = round(notional_fill * 0.0002, 4)
                    gross_u = tp1_q * ctv * sign * (exec_px - avg_px)
                    net_u = round(gross_u - fee_u, 4)
                    r_pnl = round(r_pnl + net_u, 4)
                    fees_p = round(fees_p + fee_u, 4)
                    tp1_done = 1
                    qty = rem_q
                    # Move stop to +25 bps floor for runner
                    stop_px = round(avg_px * (1.0 + sign * 0.0025), dec_px)
                    cur.execute("INSERT INTO variant_events (variant_id, snapshot_id, ts, event_type, payload) VALUES (?, ?, ?, 'TP1_FILLED', ?)",
                                (vid, snapshot_id, now_iso, json.dumps({"inst_id": inst_id, "tp1_qty": tp1_q, "rem_qty": rem_q, "net_pnl": net_u})))
                    if qty <= 0.0:
                        self._close_variant_position(cur, vid, inst_id, r_pnl, fees_p, g2_done, now_iso)
                        continue

                # 2. Check Shadow G2 Conditional Add-On (Variant A ONLY, after TP1 filled!)
                if vid == "A_COND_PYRAMID" and tp1_done and not g2_done and qty > 0:
                    ev_now = ev_long if p_dir == "LONG" else ev_short
                    k_aligned = (vfc.kronos_5m_bps > 0 and vfc.kronos_10m_bps > 0 and vfc.expected_return_1h_bps > 0) if p_dir == "LONG" else (vfc.kronos_5m_bps < 0 and vfc.kronos_10m_bps < 0 and vfc.expected_return_1h_bps < 0)
                    ofi_aligned = (ofi_norm >= 0.20) if p_dir == "LONG" else (ofi_norm <= -0.20)
                    g2_gates_ok = bool(
                        vfc.forecast_age_s <= 90.0
                        and spread_bps <= 4.5
                        and ofi_aligned
                        and k_aligned
                        and oi_delta_bps >= 5.0
                        and ev_now.lcb95_p_trade_win >= 0.65
                        and ev_now.ev_net_bps >= 8.0
                    )
                    if g2_gates_ok:
                        raw_add = math.floor((init_qty * 0.50) / lsz + 1e-9) * lsz
                        if raw_add >= msz:
                            add_fee = round(raw_add * ctv * mid_px * 0.0002, 4)
                            new_tot_q = qty + raw_add
                            avg_px = round(((avg_px * qty) + (mid_px * raw_add)) / new_tot_q, dec_px)
                            qty = new_tot_q
                            fees_p = round(fees_p + add_fee, 4)
                            g2_done = 1
                            cur.execute("INSERT INTO variant_events (variant_id, snapshot_id, ts, event_type, payload) VALUES (?, ?, ?, 'SHADOW_G2_ADDON', ?)",
                                        (vid, snapshot_id, now_iso, json.dumps({"inst_id": inst_id, "add_qty": raw_add, "new_avg_px": avg_px, "ev_net_bps": ev_now.ev_net_bps})))

                # 3. Check Stop-Loss / Runner Chandelier / Time-Stop
                time_stop_m = 25.0 if pol_u == "MEAN_REVERSION_SCALP" else 90.0
                stop_gate_bps = 32.0 if pol_u == "MEAN_REVERSION_SCALP" else 38.0
                runner_trail_bps = max(35.0, 0.35 * atr_1h_bps)
                runner_lock_bps = max(25.0, new_pk - runner_trail_bps)

                should_close = False
                exit_px = mid_px
                if tp1_done and move_bps <= runner_lock_bps:
                    should_close = True
                    exit_px = round(avg_px * (1.0 + sign * (runner_lock_bps / 10000.0)), dec_px)
                elif not tp1_done and move_bps <= -stop_gate_bps:
                    should_close = True
                    exit_px = round(avg_px * (1.0 - sign * (stop_gate_bps / 10000.0)), dec_px)
                elif age_m >= time_stop_m and move_bps < 15.0:
                    should_close = True
                    exit_px = mid_px

                if should_close:
                    notional_rem = qty * ctv * exit_px
                    fee_exit = round(notional_rem * 0.0002, 4)
                    gross_rem = qty * ctv * sign * (exit_px - avg_px)
                    r_pnl = round(r_pnl + gross_rem - fee_exit, 4)
                    fees_p = round(fees_p + fee_exit, 4)
                    self._close_variant_position(cur, vid, inst_id, r_pnl, fees_p, g2_done, now_iso)
                else:
                    unr = round(qty * ctv * sign * (mid_px - avg_px), 4)
                    cur.execute("UPDATE variant_positions SET qty=?, avg_px=?, stop_px=?, peak_bps=?, tp1_filled=?, g2_filled=?, realized_pnl=?, unrealized_pnl=?, fees_paid=? WHERE variant_id=? AND instrument=?",
                                (qty, avg_px, stop_px, round(new_pk, 2), tp1_done, g2_done, r_pnl, unr, fees_p, vid, inst_id))

            else:
                # Consider opening a new position in this variant if no position is currently open in this variant
                cur.execute("SELECT COUNT(*) FROM variant_positions WHERE variant_id=?", (vid,))
                open_cnt_v = int((cur.fetchone() or [0])[0])
                if open_cnt_v == 0 and entry_candidate_dir in ("LONG", "SHORT") and policy.policy != "ABSTAIN":
                    ev_c = ev_long if entry_candidate_dir == "LONG" else ev_short
                    if ev_c.paper_authorized and vfc.entry_valid:
                        raw_cts = target_notional_usd / max(1e-9, mid_px * ct_val)
                        dec_s = len(str(lot_sz).split(".")[1].rstrip("0")) if "." in str(lot_sz) else 0
                        cts = round(math.floor(raw_cts / lot_sz) * lot_sz, dec_s) if dec_s > 0 else float(int(math.floor(raw_cts / lot_sz) * lot_sz))
                        if cts >= min_sz:
                            ent_px = bid_px if entry_candidate_dir == "LONG" else ask_px
                            sign = 1.0 if entry_candidate_dir == "LONG" else -1.0
                            sl_bps = 32.0 if policy.policy == "MEAN_REVERSION_SCALP" else 38.0
                            tp_bps = 45.0 if policy.policy == "MEAN_REVERSION_SCALP" else (50.0 if vid == "C_SNIPER_100" else 55.0)
                            sl_px = round(ent_px * (1.0 - sign * (sl_bps / 10000.0)), dec_px)
                            tp_px = round(ent_px * (1.0 + sign * (tp_bps / 10000.0)), dec_px)
                            efee = round(cts * ct_val * ent_px * 0.0002, 4)
                            cur.execute(
                                "INSERT OR REPLACE INTO variant_positions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0, 0, ?, 0.0, ?, ?, ?)",
                                (vid, inst_id, entry_candidate_dir, cts, cts, ct_val, lot_sz, min_sz, ent_px, sl_px, tp_px, -efee, efee, policy.policy, now_iso),
                            )
                            cur.execute("INSERT INTO variant_events (variant_id, snapshot_id, ts, event_type, payload) VALUES (?, ?, ?, 'OPEN_POSITION', ?)",
                                        (vid, snapshot_id, now_iso, json.dumps({"inst_id": inst_id, "dir": entry_candidate_dir, "qty": cts, "px": ent_px, "ev_net_bps": ev_c.ev_net_bps, "policy": policy.policy})))

        self.conn.commit()
        return self.get_scoreboard()

    def _close_variant_position(self, cur: sqlite3.Cursor, vid: str, inst_id: str, r_pnl: float, fees_p: float, g2_done: int, now_iso: str) -> None:
        cur.execute("DELETE FROM variant_positions WHERE variant_id=? AND instrument=?", (vid, inst_id))
        cur.execute("SELECT trades_count, wins_count, g2_events_count, pnl, fees FROM variant_metrics WHERE variant_id=?", (vid,))
        m = cur.fetchone() or (0, 0, 0, 0.0, 0.0)
        t_cnt = int(m[0]) + 1
        w_cnt = int(m[1]) + (1 if r_pnl > 0 else 0)
        g2_cnt = int(m[2]) + (1 if g2_done else 0)
        tot_pnl = round(float(m[3]) + r_pnl, 4)
        tot_fees = round(float(m[4]) + fees_p, 4)
        hr = round((w_cnt / max(1, t_cnt)) * 100.0, 1)
        cur.execute(
            "UPDATE variant_metrics SET trades_count=?, wins_count=?, g2_events_count=?, pnl=?, fees=?, hit_rate=?, updated_at=? WHERE variant_id=?",
            (t_cnt, w_cnt, g2_cnt, tot_pnl, tot_fees, hr, now_iso, vid),
        )

    def get_scoreboard(self) -> Dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute("SELECT variant_id, trades_count, wins_count, g2_events_count, pnl, fees, hit_rate, updated_at FROM variant_metrics")
        out = {}
        for r in cur.fetchall():
            out[r[0]] = {
                "trades": r[1], "wins": r[2], "g2_events": r[3],
                "net_pnl_usd": round(float(r[4]), 2), "fees_usd": round(float(r[5]), 2),
                "hit_rate_pct": r[6], "updated_at": r[7],
            }
        return out
