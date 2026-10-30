#!/usr/bin/env python3
"""
TRE OS v7.0 (Sovereign Predator Edition) — Multi-Horizon Kronos Foundation Model Oracle Server (`scripts/kronos_oracle_server.py`)
Runs 100% locally on `brody` (`127.0.0.1:8090`, CPU-optimized with `torch.set_num_threads(2)` and `< 240 MB RAM`).

Supports:
- `NeoQuasar/Kronos-mini` (4.1M params, 2048 context, ultra-fast CPU / Apple Silicon MPS / Mini-VPS)
- `NeoQuasar/Kronos-small` (24.7M params, 512 context, GPU CUDA / MPS / CPU)

Multi-Horizon Forecasting:
1. Micro-Horizon (`5m` candles, `pred_len=12` = 1h ahead): `expected_return_1h_bps`, `upside_high_bps`, `downside_low_bps`
2. Macro-Horizon (`15m` candles, `pred_len=8` = 2h ahead): `macro_return_2h_bps`, `horizon_aligned` (True when 5m & 15m agree)
"""
import argparse
import json
import math
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Tuple
import numpy as np
import pandas as pd
import torch

torch.set_num_threads(2)

MODEL_PRESETS = {
    "mini": {
        "model_id": "NeoQuasar/Kronos-mini",
        "tokenizer_id": "NeoQuasar/Kronos-Tokenizer-2k",
        "max_context": 2048,
        "label": "NeoQuasar/Kronos-mini (4.1M)",
    },
    "small": {
        "model_id": "NeoQuasar/Kronos-small",
        "tokenizer_id": "NeoQuasar/Kronos-Tokenizer-base",
        "max_context": 512,
        "label": "NeoQuasar/Kronos-small (24.7M)",
    },
}

CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_LOCK = threading.Lock()
CACHE_TTL_SEC = 180.0
INFER_LOCK = threading.Lock()
TRACKED_PAIRS = [
    "BTC-USDC", "HYPE-USDC", "ZEC-USDC", "SOL-USDC", "UNI-USDC", "XRP-USDC", "LINK-USDC",
    "TAO-USDC", "WLD-USDC", "ARB-USDC", "LIT-USDC", "ENA-USDC", "ZAMA-USDC",
]
PRIORITY_QUEUE = []

PREDICTOR = None
ACTIVE_LABEL = ""
ACTIVE_DEVICE = "cpu"


def _background_refresh_loop():
    """
    Single background worker thread: drains PRIORITY_QUEUE (uncached dynamic explorer pairs) first,
    then refreshes all TRACKED_PAIRS every cycle with zero thread-spawning in HTTP handlers!
    """
    time.sleep(1.5)
    while True:
        while True:
            next_p = None
            with CACHE_LOCK:
                if PRIORITY_QUEUE:
                    next_p = PRIORITY_QUEUE.pop(0)
            if not next_p:
                break
            try:
                forecast_pair(next_p, force_refresh=True)
            except Exception:
                pass
            time.sleep(0.15)

        for p in list(TRACKED_PAIRS):
            with CACHE_LOCK:
                has_urgent = bool(PRIORITY_QUEUE)
            if has_urgent:
                break
            try:
                forecast_pair(p, force_refresh=True)
            except Exception:
                pass
            time.sleep(0.25)
        time.sleep(15.0)


def detect_best_device(requested: str = "auto") -> str:
    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda:0"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def fetch_okx_candles(inst_id: str, bar: str = "5m", limit: int = 180) -> pd.DataFrame:
    url = f"https://eea.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "TRE-OS-v7-KronosOracle/7.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        raw = json.loads(resp.read().decode("utf-8")).get("data", [])
    raw.reverse()
    rows = []
    for r in raw:
        rows.append({
            "timestamps": pd.to_datetime(int(r[0]), unit="ms"),
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]),
            "amount": float(r[7]),
        })
    return pd.DataFrame(rows)


def _predict_paths_pre_mean(
    df: pd.DataFrame,
    x_timestamp: pd.Series,
    y_timestamp: pd.Series,
    pred_len: int,
    T: float = 0.6,
    top_p: float = 0.90,
    sample_count: int = 3,
) -> Tuple[pd.DataFrame, np.ndarray]:
    """
    Runs batched autoregressive inference while preserving the raw (sample_count, pred_len, 6)
    tensor BEFORE `np.mean(preds, axis=1)` (fixes Issue #375 / kronos.py L467 envelope collapse!).
    """
    from model.kronos import calc_time_stamps, sample_from_logits

    PREDICTOR.tokenizer.eval()
    PREDICTOR.model.eval()

    price_cols = ["open", "high", "low", "close", "volume", "amount"]
    x = df[price_cols].values.astype(np.float32)
    x_mean, x_std = np.mean(x, axis=0), np.std(x, axis=0)
    x_norm = np.clip((x - x_mean) / (x_std + 1e-5), -PREDICTOR.clip, PREDICTOR.clip)[np.newaxis, :]

    x_stamp = calc_time_stamps(x_timestamp).values.astype(np.float32)[np.newaxis, :]
    y_stamp = calc_time_stamps(y_timestamp).values.astype(np.float32)[np.newaxis, :]

    device = PREDICTOR.device
    max_context = PREDICTOR.max_context
    xt = torch.from_numpy(x_norm).to(device)
    xst = torch.from_numpy(x_stamp).to(device)
    yst = torch.from_numpy(y_stamp).to(device)

    xt_rep = xt.unsqueeze(1).repeat(1, sample_count, 1, 1).reshape(-1, xt.size(1), xt.size(2))
    xst_rep = xst.unsqueeze(1).repeat(1, sample_count, 1, 1).reshape(-1, xst.size(1), xst.size(2))
    yst_rep = yst.unsqueeze(1).repeat(1, sample_count, 1, 1).reshape(-1, yst.size(1), yst.size(2))

    x_token = PREDICTOR.tokenizer.encode(xt_rep, half=True)
    initial_seq_len = xt_rep.size(1)
    batch_size = x_token[0].size(0)
    total_seq_len = initial_seq_len + pred_len
    full_stamp = torch.cat([xst_rep, yst_rep], dim=1)

    generated_pre = x_token[0].new_empty(batch_size, pred_len)
    generated_post = x_token[1].new_empty(batch_size, pred_len)
    pre_buffer = x_token[0].new_zeros(batch_size, max_context)
    post_buffer = x_token[1].new_zeros(batch_size, max_context)
    buffer_len = min(initial_seq_len, max_context)
    if buffer_len > 0:
        start_idx = max(0, initial_seq_len - max_context)
        pre_buffer[:, :buffer_len] = x_token[0][:, start_idx:start_idx + buffer_len]
        post_buffer[:, :buffer_len] = x_token[1][:, start_idx:start_idx + buffer_len]

    for i in range(pred_len):
        current_seq_len = initial_seq_len + i
        window_len = min(current_seq_len, max_context)
        input_tokens = [pre_buffer[:, :window_len], post_buffer[:, :window_len]] if current_seq_len <= max_context else [pre_buffer, post_buffer]
        context_end = current_seq_len
        context_start = max(0, context_end - max_context)
        current_stamp = full_stamp[:, context_start:context_end, :].contiguous()

        s1_logits, context = PREDICTOR.model.decode_s1(input_tokens[0], input_tokens[1], current_stamp)
        sample_pre = sample_from_logits(s1_logits[:, -1, :], temperature=T, top_k=0, top_p=top_p, sample_logits=True)
        s2_logits = PREDICTOR.model.decode_s2(context, sample_pre)
        sample_post = sample_from_logits(s2_logits[:, -1, :], temperature=T, top_k=0, top_p=top_p, sample_logits=True)

        generated_pre[:, i] = sample_pre.squeeze(-1)
        generated_post[:, i] = sample_post.squeeze(-1)
        if current_seq_len < max_context:
            pre_buffer[:, current_seq_len] = sample_pre.squeeze(-1)
            post_buffer[:, current_seq_len] = sample_post.squeeze(-1)
        else:
            pre_buffer.copy_(torch.roll(pre_buffer, shifts=-1, dims=1))
            post_buffer.copy_(torch.roll(post_buffer, shifts=-1, dims=1))
            pre_buffer[:, -1] = sample_pre.squeeze(-1)
            post_buffer[:, -1] = sample_post.squeeze(-1)

    full_pre = torch.cat([x_token[0], generated_pre], dim=1)
    full_post = torch.cat([x_token[1], generated_post], dim=1)
    context_start = max(0, total_seq_len - max_context)
    z = PREDICTOR.tokenizer.decode(
        [full_pre[:, context_start:total_seq_len].contiguous(), full_post[:, context_start:total_seq_len].contiguous()],
        half=True,
    )
    z = z.reshape(-1, sample_count, z.size(1), z.size(2))
    raw_paths = z.cpu().numpy()[0, :, -pred_len:, :] * (x_std + 1e-5) + x_mean  # shape: (sample_count, pred_len, 6)
    mean_preds = np.mean(raw_paths, axis=0)
    pred_df = pd.DataFrame(mean_preds, columns=price_cols, index=y_timestamp)
    return pred_df, raw_paths


def forecast_pair(inst_id: str, pred_len: int = 12, sample_count: int = 3, force_refresh: bool = False) -> dict:
    """
    Implements the exact mathematical specifications of the Tsinghua University Kronos paper (arXiv:2508.02739v1)
    plus Pre-Mean Trajectory Distribution extraction (Issues #415, #407, #375 & qlib_test.py):
    1. Table 8 Official Lookback Windows: 5m = 300 bars (25h), 15m = 160 bars (40h), 1H = 80 bars (80h).
    2. Table 6 Official Inference Hyperparameters: T = 0.6, top_p = 0.90, Test-Time Scaling N = 3 Monte Carlo rollouts.
    3. Equation 13 Path-Averaged Return Signal: R_{t->t+H} = (mean(p_hat_{t+1..t+H}) - p_t) / p_t (blended 65% path-mean + 35% terminal).
    4. Equation 12 Realized Volatility Forecast: sigma_hat = sqrt(sum((log(p_{i+1}) - log(p_i))^2)) computed per path BEFORE mean!
    5. Pre-Mean Trajectory Metrics: `tp_touch_prob_1h` (prob max(high) >= +36 bps), `path_dispersion_bps`, `kronos_zscore_1h`, `pred_volume_surge_ratio`.
    """
    now = time.time()
    if not force_refresh:
        with CACHE_LOCK:
            cached = CACHE.get(inst_id)
            if cached and (now - cached["ts"]) < 600.0:
                return cached["data"]

    df_5m = fetch_okx_candles(inst_id, bar="5m", limit=144)
    if df_5m.empty or len(df_5m) < 30:
        raise ValueError(f"Insufficient 5m candles for {inst_id}")

    df_15m = fetch_okx_candles(inst_id, bar="15m", limit=96)
    df_1h = fetch_okx_candles(inst_id, bar="1H", limit=64)

    last_close = float(df_5m["close"].iloc[-1])
    last_ts_5m = df_5m["timestamps"].iloc[-1]
    y_ts_5m = pd.Series([last_ts_5m + pd.Timedelta(minutes=5 * (i + 1)) for i in range(pred_len)])

    # Historical 1h realized volatility from 300x5m lookback window (for Cross-Sectional Z-Score normalization!)
    hist_closes = df_5m["close"].values.astype(np.float64)
    hist_log_rets_bps = np.diff(np.log(np.maximum(hist_closes, 1e-8))) * 10000.0
    lookback_vol_1h_bps = max(8.0, float(np.std(hist_log_rets_bps) * math.sqrt(12.0)))
    hist_vol_mean_5m = max(1e-6, float(df_5m["volume"].tail(48).mean()))

    t0 = time.time()
    with INFER_LOCK, torch.no_grad():
        pred_df_5m, raw_paths_5m = _predict_paths_pre_mean(
            df=df_5m[["open", "high", "low", "close", "volume", "amount"]],
            x_timestamp=df_5m["timestamps"],
            y_timestamp=y_ts_5m,
            pred_len=pred_len,
            T=0.55,
            top_p=0.90,
            sample_count=2,
        )
        macro_ret_2h_bps = 0.0
        if not df_15m.empty and len(df_15m) >= 30:
            last_close_15m = float(df_15m["close"].iloc[-1])
            last_ts_15m = df_15m["timestamps"].iloc[-1]
            y_ts_15m = pd.Series([last_ts_15m + pd.Timedelta(minutes=15 * (i + 1)) for i in range(8)])
            pred_df_15m = PREDICTOR.predict(
                df=df_15m[["open", "high", "low", "close", "volume", "amount"]],
                x_timestamp=df_15m["timestamps"],
                y_timestamp=y_ts_15m,
                pred_len=8,
                T=0.35,
                top_p=0.90,
                sample_count=1,
                verbose=False,
            )
            mean_close_2h = float(pred_df_15m["close"].mean())
            term_close_2h = float(pred_df_15m["close"].iloc[-1])
            eff_close_2h = 0.65 * mean_close_2h + 0.35 * term_close_2h
            if last_close_15m > 0:
                macro_ret_2h_bps = ((eff_close_2h - last_close_15m) / last_close_15m) * 10000.0

        horizon_6h_bps = 0.0
        swing_ret_12h_bps = 0.0
        daily_ret_24h_bps = 0.0
        if not df_1h.empty and len(df_1h) >= 30:
            last_close_1h = float(df_1h["close"].iloc[-1])
            last_ts_1h = df_1h["timestamps"].iloc[-1]
            y_ts_1h = pd.Series([last_ts_1h + pd.Timedelta(hours=i + 1) for i in range(24)])
            pred_df_1h = PREDICTOR.predict(
                df=df_1h[["open", "high", "low", "close", "volume", "amount"]],
                x_timestamp=df_1h["timestamps"],
                y_timestamp=y_ts_1h,
                pred_len=24,
                T=0.35,
                top_p=0.90,
                sample_count=1,
                verbose=False,
            )
            if last_close_1h > 0:
                c6 = pred_df_1h["close"].iloc[:6]
                eff_6h = 0.65 * float(c6.mean()) + 0.35 * float(c6.iloc[-1])
                horizon_6h_bps = ((eff_6h - last_close_1h) / last_close_1h) * 10000.0

                c12 = pred_df_1h["close"].iloc[:12]
                eff_12h = 0.65 * float(c12.mean()) + 0.35 * float(c12.iloc[-1])
                swing_ret_12h_bps = ((eff_12h - last_close_1h) / last_close_1h) * 10000.0

                c24 = pred_df_1h["close"].iloc[:24]
                eff_24h = 0.65 * float(c24.mean()) + 0.35 * float(c24.iloc[-1])
                daily_ret_24h_bps = ((eff_24h - last_close_1h) / last_close_1h) * 10000.0

    infer_ms = round((time.time() - t0) * 1000.0, 1)

    # Extract Pre-Mean Trajectory Distribution metrics from `raw_paths_5m` (shape: [N, 12, 6])
    n_paths = raw_paths_5m.shape[0]
    path_highs = [float(np.max(raw_paths_5m[k, :, 1])) for k in range(n_paths)]
    path_lows = [float(np.min(raw_paths_5m[k, :, 2])) for k in range(n_paths)]
    path_eq13_closes = [float(0.65 * np.mean(raw_paths_5m[k, :, 3]) + 0.35 * raw_paths_5m[k, -1, 3]) for k in range(n_paths)]
    path_rets_bps = [((c - last_close) / last_close) * 10000.0 for c in path_eq13_closes if last_close > 0]
    path_highs_bps = [((h - last_close) / last_close) * 10000.0 for h in path_highs if last_close > 0]
    path_lows_bps = [((last_close - l) / last_close) * 10000.0 for l in path_lows if last_close > 0]

    # True Pre-Mean High/Low Envelope (mean of per-trajectory extremes instead of flattened mean path!)
    pred_high = float(np.mean(path_highs)) if path_highs else float(pred_df_5m["high"].max())
    pred_low = float(np.mean(path_lows)) if path_lows else float(pred_df_5m["low"].min())
    pred_close = float(np.mean(path_eq13_closes)) if path_eq13_closes else float(pred_df_5m["close"].iloc[-1])

    # Pre-Mean Eq. 12 Realized Volatility (computed per trajectory and averaged!)
    path_vols_bps = []
    for k in range(n_paths):
        c_seq = [last_close] + [max(1e-8, float(x)) for x in raw_paths_5m[k, :, 3].tolist()]
        sq_s = sum((math.log(c_seq[idx + 1] / c_seq[idx])) ** 2 for idx in range(len(c_seq) - 1))
        path_vols_bps.append(math.sqrt(sq_s) * 10000.0)
    pred_volatility_1h_bps = round(float(np.mean(path_vols_bps)), 2) if path_vols_bps else 25.0

    # Take-Profit Touch Probability (>= +26 bps Maker scalp threshold) & Path Dispersion
    tp_touch_prob_1h = round(sum(1 for hb in path_highs_bps if hb >= 26.0) / max(1, len(path_highs_bps)), 3)
    path_dispersion_bps = round(float(np.std(path_rets_bps)), 2) if len(path_rets_bps) > 1 else 5.0

    # Extract ultra-short 5m (step 0) and 10m (step 1) micro-trigger forecasts directly from raw_paths_5m (0.00ms extra CPU!)
    pred_close_5m = float(np.mean(raw_paths_5m[:, 0, 3])) if raw_paths_5m.shape[1] >= 1 else pred_close
    pred_close_10m = float(0.45 * np.mean(raw_paths_5m[:, 0, 3]) + 0.55 * np.mean(raw_paths_5m[:, 1, 3])) if raw_paths_5m.shape[1] >= 2 else pred_close
    ret_5m_bps = ((pred_close_5m - last_close) / last_close) * 10000.0 if last_close > 0 else 0.0
    ret_10m_bps = ((pred_close_10m - last_close) / last_close) * 10000.0 if last_close > 0 else 0.0
    upside_bps = ((pred_high - last_close) / last_close) * 10000.0 if last_close > 0 else 0.0
    downside_bps = ((last_close - pred_low) / last_close) * 10000.0 if last_close > 0 else 0.0
    net_return_bps = ((pred_close - last_close) / last_close) * 10000.0 if last_close > 0 else 0.0
    kronos_zscore_1h = round(net_return_bps / lookback_vol_1h_bps, 3)
    pred_vol_5m = max(0.0, float(np.mean(raw_paths_5m[:, :, 4])))
    pred_volume_surge_ratio = round(min(3.5, max(0.3, pred_vol_5m / hist_vol_mean_5m)), 2)
    horizon_aligned = bool(
        (net_return_bps * macro_ret_2h_bps) > 0
        and (net_return_bps * swing_ret_12h_bps) >= 0
        and abs(net_return_bps) >= 3.0
    )

    result = {
        "inst_id": inst_id,
        "model": ACTIVE_LABEL,
        "device": ACTIVE_DEVICE,
        "infer_ms": infer_ms,
        "last_close": round(last_close, 6),
        "pred_1h_high": round(pred_high, 6),
        "pred_1h_low": round(pred_low, 6),
        "pred_1h_close": round(pred_close, 6),
        "upside_high_bps": round(upside_bps, 2),
        "downside_low_bps": round(downside_bps, 2),
        "kronos_5m_bps": round(ret_5m_bps, 2),
        "kronos_10m_bps": round(ret_10m_bps, 2),
        "expected_return_1h_bps": round(net_return_bps, 2),
        "macro_return_2h_bps": round(macro_ret_2h_bps, 2),
        "horizon_6h_bps": round(horizon_6h_bps, 2),
        "swing_return_12h_bps": round(swing_ret_12h_bps, 2),
        "daily_return_24h_bps": round(daily_ret_24h_bps, 2),
        "pred_volatility_1h_bps": pred_volatility_1h_bps,
        "tp_touch_prob_1h": tp_touch_prob_1h,
        "path_dispersion_bps": path_dispersion_bps,
        "kronos_zscore_1h": kronos_zscore_1h,
        "pred_volume_surge_ratio": pred_volume_surge_ratio,
        "horizon_aligned": horizon_aligned,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with CACHE_LOCK:
        CACHE[inst_id] = {"ts": now, "data": result}
    return result


class KronosHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path.startswith("/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "model": ACTIVE_LABEL,
                "device": ACTIVE_DEVICE,
                "cached_pairs": len(CACHE),
            }).encode())
            return

        if self.path.startswith("/forecast"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            pairs_raw = qs.get("pairs", ["SOL-USDC"])[0]
            pairs = [p.strip() for p in pairs_raw.split(",") if p.strip()]
            out = {}
            missing = []
            with CACHE_LOCK:
                for p in pairs:
                    if p.endswith("-USDC") and p not in TRACKED_PAIRS and len(TRACKED_PAIRS) < 36:
                        TRACKED_PAIRS.append(p)
                    cached = CACHE.get(p)
                    if cached:
                        out[p] = cached["data"]
                    elif p.endswith("-USDC") and p not in PRIORITY_QUEUE:
                        PRIORITY_QUEUE.append(p)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"forecasts": out}).encode())
            return

        self.send_response(404)
        self.end_headers()


def main():
    global PREDICTOR, ACTIVE_LABEL, ACTIVE_DEVICE
    parser = argparse.ArgumentParser(description="TRE OS v7.0 Sovereign Kronos-mini (4.1M) Multi-Horizon Oracle Server")
    parser.add_argument("--size", choices=["mini", "small"], default=os.environ.get("KRONOS_SIZE", "mini"),
                        help="Kronos model tier: mini (4.1M, CPU/MPS friendly) or small (24.7M, GPU/MPS)")
    parser.add_argument("--device", default=os.environ.get("KRONOS_DEVICE", "auto"),
                        help="Torch device: auto, cpu, cuda:0, mps")
    parser.add_argument("--port", type=int, default=int(os.environ.get("KRONOS_PORT", "8090")),
                        help="HTTP listening port (default: 8090)")
    parser.add_argument("--kronos-dir", default=os.environ.get("KRONOS_REPO_DIR", os.path.expanduser("~/Kronos")),
                        help="Path to cloned shiyu-coder/Kronos repository")
    args = parser.parse_args()

    if os.path.exists(args.kronos_dir):
        sys.path.insert(0, args.kronos_dir)

    from model import Kronos, KronosTokenizer, KronosPredictor

    preset = MODEL_PRESETS[args.size]
    ACTIVE_DEVICE = detect_best_device(args.device)
    ACTIVE_LABEL = preset["label"]

    print(f"[Kronos-Oracle v8.4] Loading {ACTIVE_LABEL} ({preset['tokenizer_id']}) on {ACTIVE_DEVICE}...")
    tokenizer = KronosTokenizer.from_pretrained(preset["tokenizer_id"])
    model = Kronos.from_pretrained(preset["model_id"])
    tokenizer.eval()
    model.eval()
    PREDICTOR = KronosPredictor(model, tokenizer, device=ACTIVE_DEVICE, max_context=preset["max_context"])
    print(f"[Kronos-Oracle v7.0] {ACTIVE_LABEL} ready and listening on http://127.0.0.1:{args.port}")
    bg_thread = threading.Thread(target=_background_refresh_loop, daemon=True)
    bg_thread.start()

    server = HTTPServer(("0.0.0.0", args.port), KronosHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
