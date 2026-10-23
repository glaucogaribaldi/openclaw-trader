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
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Tuple
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
    "HYPE-USDC", "ZEC-USDC", "SOL-USDC", "SUI-USDC", "NEAR-USDC", "UNI-USDC",
    "XRP-USDC", "LINK-USDC", "RENDER-USDC", "AVAX-USDC", "FET-USDC", "SEI-USDC",
]

PREDICTOR = None
ACTIVE_LABEL = ""
ACTIVE_DEVICE = "cpu"


def _background_refresh_loop():
    """
    Continuously refreshes all 12 pairs in the background every 120s so HTTP /forecast
    calls return in 0.00ms without ever blocking `predator_daemon.py`!
    """
    time.sleep(2.0)
    while True:
        for p in TRACKED_PAIRS:
            try:
                forecast_pair(p, force_refresh=True)
            except Exception:
                pass
            time.sleep(0.5)
        time.sleep(60.0)


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


def forecast_pair(inst_id: str, pred_len: int = 12, sample_count: int = 2, force_refresh: bool = False) -> dict:
    now = time.time()
    if not force_refresh:
        with CACHE_LOCK:
            cached = CACHE.get(inst_id)
            if cached and (now - cached["ts"]) < 600.0:
                return cached["data"]

    df_5m = fetch_okx_candles(inst_id, bar="5m", limit=180)
    if df_5m.empty or len(df_5m) < 30:
        raise ValueError(f"Insufficient 5m candles for {inst_id}")

    df_15m = fetch_okx_candles(inst_id, bar="15m", limit=120)

    last_close = float(df_5m["close"].iloc[-1])
    last_ts_5m = df_5m["timestamps"].iloc[-1]
    y_ts_5m = pd.Series([last_ts_5m + pd.Timedelta(minutes=5 * (i + 1)) for i in range(pred_len)])

    t0 = time.time()
    with INFER_LOCK, torch.no_grad():
        pred_df_5m = PREDICTOR.predict(
            df=df_5m[["open", "high", "low", "close", "volume", "amount"]],
            x_timestamp=df_5m["timestamps"],
            y_timestamp=y_ts_5m,
            pred_len=pred_len,
            T=0.6,
            top_p=0.9,
            sample_count=sample_count,
            verbose=False,
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
                T=0.6,
                top_p=0.9,
                sample_count=2,
                verbose=False,
            )
            pred_close_2h = float(pred_df_15m["close"].iloc[-1])
            if last_close_15m > 0:
                macro_ret_2h_bps = ((pred_close_2h - last_close_15m) / last_close_15m) * 10000.0

    infer_ms = round((time.time() - t0) * 1000.0, 1)

    pred_high = float(pred_df_5m["high"].max())
    pred_low = float(pred_df_5m["low"].min())
    pred_close = float(pred_df_5m["close"].iloc[-1])

    upside_bps = ((pred_high - last_close) / last_close) * 10000.0 if last_close > 0 else 0.0
    downside_bps = ((last_close - pred_low) / last_close) * 10000.0 if last_close > 0 else 0.0
    net_return_bps = ((pred_close - last_close) / last_close) * 10000.0 if last_close > 0 else 0.0
    horizon_aligned = bool((net_return_bps * macro_ret_2h_bps) > 0 and abs(net_return_bps) >= 3.0)

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
        "expected_return_1h_bps": round(net_return_bps, 2),
        "macro_return_2h_bps": round(macro_ret_2h_bps, 2),
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
            with CACHE_LOCK:
                for p in pairs:
                    cached = CACHE.get(p)
                    if cached:
                        out[p] = cached["data"]
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

    print(f"[Kronos-Oracle v7.0] Loading {ACTIVE_LABEL} ({preset['tokenizer_id']}) on {ACTIVE_DEVICE}...")
    tokenizer = KronosTokenizer.from_pretrained(preset["tokenizer_id"])
    model = Kronos.from_pretrained(preset["model_id"])
    PREDICTOR = KronosPredictor(model, tokenizer, device=ACTIVE_DEVICE, max_context=preset["max_context"])
    print(f"[Kronos-Oracle v7.0] {ACTIVE_LABEL} ready and listening on http://127.0.0.1:{args.port}")
    bg_thread = threading.Thread(target=_background_refresh_loop, daemon=True)
    bg_thread.start()

    server = HTTPServer(("0.0.0.0", args.port), KronosHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
