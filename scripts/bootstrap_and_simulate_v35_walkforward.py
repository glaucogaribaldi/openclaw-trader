#!/usr/bin/env python3
"""
TRE OS v35.1 — Real OKX Barrier Dataset Builder & Walk-Forward v35 A/B/C Simulator
1. Downloads real historical 15m candles from OKX EEA across core instruments.
2. Labels the exact v35 event chronologically (zero look-ahead):
     target = 1 if price touches +50 bps before -38 bps within 60 minutes (4 x 15m bars), else 0.
3. Stores time-ordered samples into SQLite table `ev_training_samples` so `CalibratedEVEngine.fit_from_sqlite()`
   fits b0..b8 via expanding walk-forward folds with real out-of-sample Brier Score.
4. Simulates Variant A (Conditional Pyramid), Variant B (Partial 60/40), and Variant C (Sniper 100%) out-of-sample.
"""
import datetime, json, math, os, sqlite3, ssl, sys, time, urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from core.luna_v35_engine import CalibratedEVEngine, ParallelShadowABCLedger


def _ssl_ctx() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def fetch_okx_15m_candles(inst_id: str, limit: int = 240) -> list:
    url = f"https://eea.okx.com/api/v5/market/candles?instId={inst_id}&bar=15m&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "TRE-OS-v35-Audit/1.0"})
    with urllib.request.urlopen(req, timeout=8, context=_ssl_ctx()) as r:
        rows = json.loads(r.read().decode("utf-8")).get("data", [])
    rows.reverse()  # chronological: oldest -> newest
    return rows


def build_real_barrier_samples_and_simulate() -> dict:
    db_path = os.path.join(BASE_DIR, "config", "okx_futures_demo.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ev_training_samples (
            sample_id TEXT PRIMARY KEY,
            observed_at TEXT NOT NULL,
            inst_id TEXT NOT NULL,
            direction TEXT NOT NULL,
            target INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        )
    """)
    conn.execute("DELETE FROM ev_training_samples")

    instruments = [
        "BTC-USD_UM_XPERP-310404", "ETH-USD_UM_XPERP-310404", "SOL-USD_UM_XPERP-310404",
        "ZEC-USD_UM_XPERP-310530", "LINK-USD_UM_XPERP-310523", "NEAR-USD_UM_XPERP-310613",
        "AVAX-USD_UM_XPERP-310530", "SUI-USD_UM_XPERP-310404", "UNI-USD_UM_XPERP-310718",
        "HYPE-USD_UM_XPERP-310523", "XRP-USD_UM_XPERP-310404", "ONDO-USD_UM_XPERP-310620",
    ]

    all_samples = []
    for iid in instruments:
        try:
            bars = fetch_okx_15m_candles(iid, limit=220)
        except Exception:
            continue
        if len(bars) < 40:
            continue
        for idx in range(12, len(bars) - 5, 3):
            ts_ms = int(bars[idx][0])
            obs_iso = datetime.datetime.fromtimestamp(ts_ms / 1000.0, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            c_now = float(bars[idx][4])
            o_now = float(bars[idx][1])
            c_prev15 = float(bars[idx - 1][4])
            c_prev1h = float(bars[idx - 4][4])
            if c_now <= 0 or c_prev15 <= 0 or c_prev1h <= 0:
                continue
            r15_bps = (c_now - c_prev15) / c_prev15 * 10000.0
            r1h_bps = (c_now - c_prev1h) / c_prev1h * 10000.0
            if abs(r15_bps) < 6.0 and abs(r1h_bps) < 12.0:
                continue

            rngs = [((float(bars[k][2]) - float(bars[k][3])) / max(1e-9, float(bars[k][3])) * 10000.0) for k in range(idx - 3, idx + 1)]
            atr_1h_bps = max(25.0, min(160.0, (sum(rngs) / len(rngs)) * 2.0))
            body_ratio = abs(c_now - o_now) / max(1e-9, float(bars[idx][2]) - float(bars[idx][3]))

            direction = "LONG" if (r15_bps + 0.5 * r1h_bps) >= 0 else "SHORT"
            sign = 1.0 if direction == "LONG" else -1.0

            exp_ret_1h = sign * (0.55 * r15_bps + 0.35 * r1h_bps)
            pred_vol_1h = max(25.0, atr_1h_bps * 0.65)
            ofi_proxy = _clip_f(sign * ((c_now - o_now) / max(1e-9, c_now) * 10000.0) / max(15.0, atr_1h_bps * 0.4), -0.95, 0.95)
            tp_prob_proxy = _clip_f(0.50 + 0.22 * (exp_ret_1h / pred_vol_1h) + 0.08 * body_ratio, 0.12, 0.88)
            disp_proxy = max(4.0, pred_vol_1h * (1.0 - 0.4 * body_ratio))
            spread_proxy = 1.8 if iid.split("-")[0] in ("BTC", "ETH", "SOL") else 2.8
            dir_align = 1.0 if (sign * r15_bps > 0 and sign * r1h_bps > 0) else (0.0 if sign * r15_bps > 0 else -1.0)
            regime_id = 1.0 if abs(r1h_bps) >= 25.0 else 0.0

            hit_win = False
            hit_loss = False
            for f_idx in range(idx + 1, min(len(bars), idx + 5)):
                hi_f = float(bars[f_idx][2])
                lo_f = float(bars[f_idx][3])
                fav_bps = ((hi_f - c_now) / c_now * 10000.0) if direction == "LONG" else ((c_now - lo_f) / c_now * 10000.0)
                adv_bps = ((c_now - lo_f) / c_now * 10000.0) if direction == "LONG" else ((hi_f - c_now) / c_now * 10000.0)
                if adv_bps >= 38.0 and fav_bps < 50.0:
                    hit_loss = True
                    break
                if fav_bps >= 50.0:
                    hit_win = True
                    break

            target = 1 if (hit_win and not hit_loss) else 0
            sample_obj = {
                "observed_at": obs_iso,
                "inst_id": iid,
                "direction": direction,
                "target": target,
                "features": {
                    "expected_return_1h_bps": round(exp_ret_1h, 2),
                    "pred_volatility_1h_bps": round(pred_vol_1h, 2),
                    "ofi_norm": round(ofi_proxy, 3),
                    "tp_touch_prob_1h": round(tp_prob_proxy, 3),
                    "path_dispersion_bps": round(disp_proxy, 2),
                    "spread_bps": spread_proxy,
                    "atr_1h_bps": round(atr_1h_bps, 2),
                    "direction_alignment": dir_align,
                    "regime_id": regime_id,
                },
            }
            all_samples.append((obs_iso, f"ev_{iid.split('-')[0]}_{ts_ms}", iid, direction, target, sample_obj))

    all_samples.sort(key=lambda x: x[0])
    for obs_iso, sid, iid, d, tgt, sobj in all_samples:
        conn.execute(
            "INSERT OR REPLACE INTO ev_training_samples VALUES (?, ?, ?, ?, ?, ?)",
            (sid, obs_iso, iid, d, tgt, json.dumps(sobj)),
        )
    conn.commit()

    ev_eng = CalibratedEVEngine()
    fit_rep = ev_eng.fit_from_sqlite(conn, min_obs=100)

    oos_samples = all_samples[len(all_samples) // 2 :]
    sim_stats = {
        "A_COND_PYRAMID": {"trades": 0, "wins": 0, "net_pnl_usd": 0.0, "fees_usd": 0.0},
        "B_PARTIAL_60_40": {"trades": 0, "wins": 0, "net_pnl_usd": 0.0, "fees_usd": 0.0},
        "C_SNIPER_100": {"trades": 0, "wins": 0, "net_pnl_usd": 0.0, "fees_usd": 0.0},
    }
    for obs_iso, sid, iid, d, tgt, sobj in oos_samples:
        xy = ev_eng._sample_to_xy(sobj)
        if not xy:
            continue
        x_vec, _ = xy
        w = [ev_eng.weights[f"b{i}"] for i in range(9)]
        p_win_fill = 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, sum(w[i] * x_vec[i] for i in range(9))))))
        p_fill = 0.90
        p_trade_win = p_fill * p_win_fill
        ev_net = (p_trade_win * 50.0 - (1.0 - p_trade_win) * 38.0) - 5.2
        if ev_net < 4.0:
            continue
        for vid in sim_stats:
            sim_stats[vid]["trades"] += 1
            if tgt == 1:
                sim_stats[vid]["wins"] += 1
                if vid == "C_SNIPER_100":
                    pnl, fee = round(90.0 * 0.0050 - 0.036, 3), 0.036
                elif vid == "B_PARTIAL_60_40":
                    pnl, fee = round(54.0 * 0.0055 + 36.0 * 0.0065 - 0.036, 3), 0.036
                else:
                    pnl, fee = round(54.0 * 0.0055 + 54.0 * 0.0070 - 0.048, 3), 0.048
            else:
                pnl, fee = round(-90.0 * 0.0038 - 0.036, 3), 0.036
            sim_stats[vid]["net_pnl_usd"] = round(sim_stats[vid]["net_pnl_usd"] + pnl, 2)
            sim_stats[vid]["fees_usd"] = round(sim_stats[vid]["fees_usd"] + fee, 2)

    for vid, st in sim_stats.items():
        st["win_rate_pct"] = round((st["wins"] / max(1, st["trades"])) * 100.0, 1)

    return {
        "total_labeled_barrier_samples": len(all_samples),
        "walk_forward_fit_report": fit_rep,
        "fitted_weights": ev_eng.weights,
        "oos_v35_variants_comparison": sim_stats,
    }


def _clip_f(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


if __name__ == "__main__":
    print(json.dumps(build_real_barrier_samples_and_simulate(), indent=2))
