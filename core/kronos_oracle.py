#!/usr/bin/env python3
"""
TRE OS v7.0 (Sovereign Predator Edition) — Local Kronos-mini (4.1M) Multi-Horizon Client (`core/kronos_oracle.py`)
Connects locally to `kronos-oracle.service` running on `brody` (`http://127.0.0.1:8090/forecast`),
zero external VPS dependency!

Provides:
- `expected_return_1h_bps`: Autoregressive 12x5m K-line Close forecast in basis points
- `macro_return_2h_bps`: Autoregressive 8x15m K-line Close forecast in basis points
- `horizon_aligned`: True when both 5m and 15m horizons agree directionally
- `upside_high_bps`: Predicted 1h High envelope in bps (calibrates dynamic Take-Profit)
- `downside_low_bps`: Predicted 1h Low envelope in bps (calibrates dynamic Buy Trap depth)
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class KronosForecast:
    inst_id: str
    last_close: float
    pred_1h_high: float
    pred_1h_low: float
    pred_1h_close: float
    upside_high_bps: float
    downside_low_bps: float
    expected_return_1h_bps: float
    macro_return_2h_bps: float = 0.0
    horizon_aligned: bool = False
    infer_ms: float = 0.0


class KronosOracleClient:
    def __init__(self, endpoint_url: str = "http://127.0.0.1:8090"):
        self.endpoint_url = (os.environ.get("KRONOS_ORACLE_URL") or endpoint_url).rstrip("/")
        self._last_cache: Dict[str, KronosForecast] = {}

    def fetch_forecasts(self, pairs: List[str], timeout: float = 14.0) -> Dict[str, KronosForecast]:
        if not pairs:
            return {}
        try:
            qs = urllib.parse.urlencode({"pairs": ",".join(pairs)})
            url = f"{self.endpoint_url}/forecast?{qs}"
            req = urllib.request.Request(url, headers={"User-Agent": "TRE-OS-v7-KronosClient/7.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            raw_map = payload.get("forecasts", {})
            for inst_id, item in raw_map.items():
                if isinstance(item, dict) and "expected_return_1h_bps" in item:
                    self._last_cache[inst_id] = KronosForecast(
                        inst_id=inst_id,
                        last_close=float(item.get("last_close", 0.0)),
                        pred_1h_high=float(item.get("pred_1h_high", 0.0)),
                        pred_1h_low=float(item.get("pred_1h_low", 0.0)),
                        pred_1h_close=float(item.get("pred_1h_close", 0.0)),
                        upside_high_bps=float(item.get("upside_high_bps", 25.0)),
                        downside_low_bps=float(item.get("downside_low_bps", 25.0)),
                        expected_return_1h_bps=float(item.get("expected_return_1h_bps", 0.0)),
                        macro_return_2h_bps=float(item.get("macro_return_2h_bps", 0.0)),
                        horizon_aligned=bool(item.get("horizon_aligned", False)),
                        infer_ms=float(item.get("infer_ms", 0.0)),
                    )
        except Exception:
            pass
        return self._last_cache
