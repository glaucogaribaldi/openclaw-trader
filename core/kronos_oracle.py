#!/usr/bin/env python3
"""
TRE OS v7.0 (Sovereign Predator Edition) — Local Kronos-mini (4.1M) Multi-Horizon Client (`core/kronos_oracle.py`)
Connects locally to `kronos-oracle.service` running on `quant-node` (`http://127.0.0.1:8090/forecast`),
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
import time
import urllib.parse
import urllib.request
import datetime
import hashlib
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
    kronos_5m_bps: float = 0.0
    kronos_10m_bps: float = 0.0
    macro_return_2h_bps: float = 0.0
    horizon_6h_bps: float = 0.0
    swing_return_12h_bps: float = 0.0
    daily_return_24h_bps: float = 0.0
    pred_volatility_1h_bps: float = 25.0
    tp_touch_prob_1h: float = 0.50
    path_dispersion_bps: float = 5.0
    kronos_zscore_1h: float = 0.0
    pred_volume_surge_ratio: float = 1.0
    horizon_aligned: bool = False
    infer_ms: float = 0.0
    generated_at_ts: float = 0.0
    source_now_ts: float = 0.0
    sample_count: int = 0
    forecast_id: str = ""


class KronosOracleClient:
    def __init__(self, endpoint_url: str = "http://127.0.0.1:8090", max_cache_age_sec: float = 300.0):
        self.endpoint_url = (os.environ.get("KRONOS_ORACLE_URL") or endpoint_url).rstrip("/")
        self.max_cache_age_sec = max_cache_age_sec
        self._last_cache: Dict[str, KronosForecast] = {}
        self._last_cache_ts: float = 0.0

    @staticmethod
    def _parse_timestamp(value: object) -> float:
        """Parse Kronos ISO-8601/epoch timestamps without inventing freshness."""
        if value is None or value == "":
            return 0.0
        try:
            number = float(value)
            return number / 1000.0 if number > 10_000_000_000 else number
        except (TypeError, ValueError):
            pass
        try:
            text = str(value).strip().replace("Z", "+00:00")
            return datetime.datetime.fromisoformat(text).timestamp()
        except (TypeError, ValueError, OverflowError):
            return 0.0

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
            if not isinstance(raw_map, dict):
                raw_map = {}
            updated_ids = set()
            for inst_id, item in raw_map.items():
                if isinstance(item, dict) and "expected_return_1h_bps" in item:
                    generated_at_ts = self._parse_timestamp(
                        item.get("generated_at_ts")
                        or item.get("generated_at")
                        or item.get("timestamp")
                        or payload.get("generated_at_ts")
                        or payload.get("timestamp")
                    )
                    source_now_ts = self._parse_timestamp(
                        item.get("source_now_ts")
                        or item.get("server_time_ts")
                        or item.get("server_timestamp")
                        or item.get("server_time")
                        or payload.get("source_now_ts")
                        or payload.get("server_time_ts")
                        or payload.get("server_timestamp")
                        or payload.get("server_time")
                    )
                    sample_count = int(item.get("sample_count") or 0)
                    forecast_id = str(item.get("forecast_id") or "")
                    if not forecast_id:
                        fid_raw = f"{inst_id}:{generated_at_ts}:{item.get('expected_return_1h_bps')}:{item.get('last_close')}"
                        forecast_id = "kf_" + hashlib.sha1(fid_raw.encode("utf-8")).hexdigest()[:12]
                    updated_ids.add(str(inst_id))
                    self._last_cache[inst_id] = KronosForecast(
                        inst_id=inst_id,
                        last_close=float(item.get("last_close", 0.0)),
                        pred_1h_high=float(item.get("pred_1h_high", 0.0)),
                        pred_1h_low=float(item.get("pred_1h_low", 0.0)),
                        pred_1h_close=float(item.get("pred_1h_close", 0.0)),
                        upside_high_bps=float(item.get("upside_high_bps", 25.0)),
                        downside_low_bps=float(item.get("downside_low_bps", 25.0)),
                        expected_return_1h_bps=float(item.get("expected_return_1h_bps", 0.0)),
                        kronos_5m_bps=float(item.get("kronos_5m_bps", 0.0)),
                        kronos_10m_bps=float(item.get("kronos_10m_bps", 0.0)),
                        macro_return_2h_bps=float(item.get("macro_return_2h_bps", 0.0)),
                        horizon_6h_bps=float(item.get("horizon_6h_bps", 0.0)),
                        swing_return_12h_bps=float(item.get("swing_return_12h_bps", 0.0)),
                        daily_return_24h_bps=float(item.get("daily_return_24h_bps", 0.0)),
                        pred_volatility_1h_bps=float(item.get("pred_volatility_1h_bps", 25.0)),
                        tp_touch_prob_1h=float(item.get("tp_touch_prob_1h", 0.50)),
                        path_dispersion_bps=float(item.get("path_dispersion_bps", 5.0)),
                        kronos_zscore_1h=float(item.get("kronos_zscore_1h", 0.0)),
                        pred_volume_surge_ratio=float(item.get("pred_volume_surge_ratio", 1.0)),
                        horizon_aligned=bool(item.get("horizon_aligned", False)),
                        infer_ms=float(item.get("infer_ms", 0.0)),
                        generated_at_ts=generated_at_ts,
                        source_now_ts=source_now_ts,
                        sample_count=sample_count,
                        forecast_id=forecast_id,
                    )
            # A successful empty response is a hard invalidation event. Do not let
            # an old forecast survive merely because the HTTP request succeeded.
            if not updated_ids:
                self._last_cache.clear()
                self._last_cache_ts = 0.0
                return {}
            for inst_id in list(self._last_cache):
                if inst_id in pairs and inst_id not in updated_ids:
                    self._last_cache.pop(inst_id, None)
            self._last_cache_ts = time.time()
        except Exception:
            if (time.time() - self._last_cache_ts) > self.max_cache_age_sec:
                self._last_cache.clear()
                return {}
        return self._last_cache
