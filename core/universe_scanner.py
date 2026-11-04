#!/usr/bin/env python3
"""
TRE OS v10.1 (Sovereign Predator) — Autonomous Dynamic Universe Explorer & Alpha Radar (core/universe_scanner.py)

Scans the entire OKX EEA Spot *-USDC market to discover new high-volatility, high-volume altcoin movers
in real time without being restricted to a static hardcoded list.
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Set

EXCLUDED_BASES: Set[str] = {
    "USDT", "USDC", "USDG", "EUR", "DAI", "FDUSD", "PYUSD", "USTC", "TUSD", "USDE",
    # Exclude synthetic tokenized equities with market-hours gaps
    "XINTC", "XCRCL", "XSKHY", "XMSTR", "XSPCX", "XNVDA", "XTSLA", "XAAPL", "XCOIN", "XMETA", "XGOOG", "XAMZN", "XMSFT",
}


def _decimals_from_step(step_str: str, default_dec: int = 3, max_dec: int = 5) -> int:
    s = str(step_str or "").strip()
    if not s or "." not in s:
        return 0
    frac = s.split(".", 1)[1].rstrip("0")
    return min(max_dec, max(0, len(frac))) if frac else 0


class PredatorUniverseScanner:
    """
    Periodically scans all OKX EEA *-USDC Spot pairs (cached every 600s -> 0.00ms loop overhead)
    and dynamically promotes the highest-alpha movers (volatility + volume + tight spread) into the active hunting universe.
    """

    def __init__(self, ttl_sec: float = 600.0, max_dynamic_explorers: int = 6):
        self.ttl_sec = ttl_sec
        self.max_dynamic_explorers = max_dynamic_explorers
        self._last_scan_ts: float = 0.0
        self._cached_explorers: Dict[str, Dict[str, Any]] = {}
        self._cached_radar_top: List[Dict[str, Any]] = []

    def scan_okx_usdc_universe(
        self,
        client: Any,
        base_universe: Dict[str, Dict[str, Any]],
        held_coins: Set[str],
    ) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
        now = time.time()
        if (now - self._last_scan_ts) < self.ttl_sec and self._cached_explorers:
            merged = dict(base_universe)
            for k, v in self._cached_explorers.items():
                if k not in merged:
                    merged[k] = v
            return merged, self._cached_radar_top

        try:
            t_res = client._request("GET", "/api/v5/market/tickers", params={"instType": "SPOT"}, auth=False, timeout=5)
            i_res = client._request("GET", "/api/v5/public/instruments", params={"instType": "SPOT"}, auth=False, timeout=5)
            tickers = t_res.get("data", []) if isinstance(t_res, dict) else []
            inst_map = {
                str(x.get("instId")): x
                for x in (i_res.get("data", []) if isinstance(i_res, dict) else [])
                if x.get("instId")
            }

            candidates: List[Dict[str, Any]] = []
            for t in tickers:
                iid = str(t.get("instId") or "")
                if not iid.endswith("-USDC"):
                    continue
                coin = iid.split("-")[0]
                if coin in EXCLUDED_BASES or (coin.startswith("X") and coin not in ("XRP", "XLM", "XTZ")):
                    continue
                vol_usd = float(t.get("volCcy24h") or 0.0)
                high = float(t.get("high24h") or 0.0)
                low = float(t.get("low24h") or 0.0)
                last = float(t.get("last") or 0.0)
                open24 = float(t.get("open24h") or last)
                bid = float(t.get("bidPx") or 0.0)
                ask = float(t.get("askPx") or 0.0)
                if low <= 0 or bid <= 0 or ask <= 0:
                    continue
                spread_bps = ((ask - bid) / ((ask + bid) * 0.5)) * 10000.0
                range_pct = ((high - low) / low) * 100.0
                chg_pct = ((last - open24) / open24) * 100.0 if open24 > 0 else 0.0
                is_currently_held = coin in held_coins
                # Block 1 Structural Fix: reject thin/erratic pump-and-dump coins (vol < $500k, spread > 5.8 bps, or 24h range > 16.5%)
                if not is_currently_held and (vol_usd < 500000.0 or spread_bps > 5.8 or range_pct > 16.5):
                    continue
                # Reward deep liquidity + healthy controlled volatility (3%-12%) + tight spread
                liq_score = min(16.0, math.log10(max(100000.0, vol_usd)) * 2.5 - 10.0)
                controlled_vol = min(range_pct, 11.5)
                pred_rank = round((controlled_vol * 1.4) + (liq_score * 2.2) - (spread_bps * 2.6), 2)

                meta = inst_map.get(iid, {})
                dec_px = _decimals_from_step(str(meta.get("tickSz") or "0.001"), default_dec=3, max_dec=6)
                dec_sz = _decimals_from_step(str(meta.get("lotSz") or "0.01"), default_dec=2, max_dec=4)
                candidates.append({
                    "inst_id": iid,
                    "coin": coin,
                    "last": last,
                    "vol_usd_24h": round(vol_usd, 0),
                    "range_24h_pct": round(range_pct, 2),
                    "chg_24h_pct": round(chg_pct, 2),
                    "spread_bps": round(spread_bps, 2),
                    "pred_rank": pred_rank,
                    "dec_px": dec_px,
                    "dec_sz": dec_sz,
                })

            candidates.sort(key=lambda x: x["pred_rank"], reverse=True)
            self._cached_radar_top = candidates[:18]

            new_explorers: Dict[str, Dict[str, Any]] = {}
            for cand in candidates:
                iid = cand["inst_id"]
                if iid in base_universe:
                    base_universe[iid]["chg_24h_pct"] = cand["chg_24h_pct"]
                    base_universe[iid]["range_24h_pct"] = cand["range_24h_pct"]
                    continue
                if len(new_explorers) >= self.max_dynamic_explorers and cand["coin"] not in held_coins:
                    continue
                # Dynamic Explorer Coin promoted to active hunting!
                new_explorers[iid] = {
                    "coin": cand["coin"],
                    "dec_px": cand["dec_px"],
                    "dec_sz": cand["dec_sz"],
                    "harvest_only": False,
                    "liq_bonus": round(min(8.5, max(2.0, cand["pred_rank"] * 0.45)), 2),
                    "is_dynamic_explorer": True,
                    "range_24h_pct": cand["range_24h_pct"],
                    "chg_24h_pct": cand["chg_24h_pct"],
                    "vol_usd_24h": cand["vol_usd_24h"],
                }

            self._cached_explorers = new_explorers
            self._last_scan_ts = now
        except Exception:
            pass

        merged = dict(base_universe)
        for k, v in self._cached_explorers.items():
            if k not in merged:
                merged[k] = v
        return merged, self._cached_radar_top
