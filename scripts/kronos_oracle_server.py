#!/usr/bin/env python3
"""
TRE OS v6.1 (Predator Edition) — Universal Kronos Foundation Model Oracle Server (`scripts/kronos_oracle_server.py`)
Supports:
- `NeoQuasar/Kronos-mini` (4.1M params, 2048 context, ultra-fast CPU / Apple Silicon MPS / Mini-VPS)
- `NeoQuasar/Kronos-small` (24.7M params, 512 context, GPU CUDA / MPS / CPU — Highest 5m Scalp Accuracy)

Serves real-time K-line foundation model forecasts (`pred_len=12` x 5m = 1h ahead)
with in-memory TTL caching (120s) on HTTP port 8090 (`/health` and `/forecast?pairs=SOL-USDC,NEAR-USDC`).
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
import pandas as pd
import torch

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

CACHE = {}
CACHE_LOCK = threading.Lock()
CACHE_TTL_SEC = 120.0
INFER_LOCK = threading.Lock()

PREDICTOR = None
ACTIVE_LABEL = ""
ACTIVE_DEVICE = "cpu"


def detect_best_device(requested: str = "auto") -> str:
    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda:0"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def fetch_okx_5m_candles(inst_id: str, limit: int = 240) -> pd.DataFrame:
    url = f"https://eea.okx.com/api/v5/market/candles?instId={inst_id}&bar=5m&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "TRE-OS-v6-KronosOracle/6.0"})
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


def forecast_pair(inst_id: str, pred_len: int = 12, sample_count: int = 5) -> dict:
    now = time.time()
    with CACHE_LOCK:
        cached = CACHE.get(inst_id)
        if cached and (now - cached["ts"]) < CACHE_TTL_SEC:
            return cached["data"]

    df = fetch_okx_5m_candles(inst_id, limit=240)
    if df.empty or len(df) < 30:
        raise ValueError(f"Insufficient candles for {inst_id}")

    last_close = float(df["close"].iloc[-1])
    last_ts = df["timestamps"].iloc[-1]
    y_ts = pd.Series([last_ts + pd.Timedelta(minutes=5 * (i + 1)) for i in range(pred_len)])

    t0 = time.time()
    with INFER_LOCK:
        pred_df = PREDICTOR.predict(
            df=df[["open", "high", "low", "close", "volume", "amount"]],
            x_timestamp=df["timestamps"],
            y_timestamp=y_ts,
            pred_len=pred_len,
            T=0.6,
            top_p=0.9,
            sample_count=sample_count,
            verbose=False,
        )
    infer_ms = round((time.time() - t0) * 1000.0, 1)

    pred_high = float(pred_df["high"].max())
    pred_low = float(pred_df["low"].min())
    pred_close = float(pred_df["close"].iloc[-1])

    upside_bps = ((pred_high - last_close) / last_close) * 10000.0 if last_close > 0 else 0.0
    downside_bps = ((last_close - pred_low) / last_close) * 10000.0 if last_close > 0 else 0.0
    net_return_bps = ((pred_close - last_close) / last_close) * 10000.0 if last_close > 0 else 0.0

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
            }).encode())
            return

        def _infer_pair(p: str) -> Tuple[str, Dict[str, Any]]:
            try:
                return p, forecast_pair(p)
            except Exception as e:
                return p, {"error": str(e)}

        if self.path.startswith("/forecast"):
            from concurrent.futures import ThreadPoolExecutor
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            pairs_raw = qs.get("pairs", ["SOL-USDC"])[0]
            pairs = [p.strip() for p in pairs_raw.split(",") if p.strip()]
            out = {}
            with ThreadPoolExecutor(max_workers=min(8, max(1, len(pairs)))) as pool:
                for p, res in pool.map(_infer_pair, pairs):
                    out[p] = res
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"forecasts": out}).encode())
            return

        self.send_response(404)
        self.end_headers()


def main():
    global PREDICTOR, ACTIVE_LABEL, ACTIVE_DEVICE
    parser = argparse.ArgumentParser(description="TRE OS v6.1 Kronos Foundation Model Oracle Server")
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

    print(f"[Kronos-Oracle] Loading {ACTIVE_LABEL} ({preset['tokenizer_id']}) on {ACTIVE_DEVICE}...")
    tokenizer = KronosTokenizer.from_pretrained(preset["tokenizer_id"])
    model = Kronos.from_pretrained(preset["model_id"])
    PREDICTOR = KronosPredictor(model, tokenizer, device=ACTIVE_DEVICE, max_context=preset["max_context"])
    print(f"[Kronos-Oracle] {ACTIVE_LABEL} ready and listening on http://0.0.0.0:{args.port}")

    server = HTTPServer(("0.0.0.0", args.port), KronosHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
