#!/usr/bin/env python3
"""
TRE OS v12.4 — Autonomous Closed-Loop Meta-Optimizer uniting Google Gemini Free + 5-Horizon Tsinghua Kronos
(core/gemini_self_improver.py)

Combines:
1. Historical SQLite WAL Post-Mortem (CLOSED_PROFIT vs CLOSED_STOPLOSS, realized PnL, fee drag);
2. Live 5-Horizon Kronos Foundation Model Matrix (1h, 2h, 6h, 12h, 24h + Eq.12 Volatility + TP Touch Prob)
   across BTC-USDC and all active altcoins.

Gemini Free (gemini-3.5-flash-lite / gemini-3.5-flash / gemini-3.8-flash) cross-examines past realized outcomes
against Kronos's forward 1h-24h structural trajectory to dynamically calibrate:
- min_entry_ofi [0.15 .. 0.45]
- max_entry_vpin [0.40 .. 0.68]
- min_kronos_1h_bps [6.0 .. 22.0]
- min_kronos_6h_bps [-25.0 .. +15.0]
- min_kronos_24h_bps [-50.0 .. +20.0]
- min_pullback_2h_bps [25.0 .. 70.0]
- fast_shield_trigger_bps [28.0 .. 55.0]
- coin_penalty_box_24h (up to 3 stop-loss / bearish-Kronos coins paused for 24h)
- kronos_top_conviction_leaders (up to 3 coins with the strongest 1h+2h+6h+12h+24h Kronos alignment, awarded +4.5 OppScore boost)
"""
from __future__ import annotations

import datetime
import json
import os
import sqlite3
import ssl
import time
import urllib.request
from typing import Any, Dict, List, Optional


def _ssl_ctx() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _clamp(val: Any, lo: float, hi: float, default: float) -> float:
    try:
        v = float(val)
        return round(max(lo, min(hi, v)), 3)
    except Exception:
        return default


class GeminiSelfImprover:
    DEFAULT_STATE: Dict[str, Any] = {
        "updated_at": "",
        "model_used": "baseline-defaults",
        "min_entry_ofi": 0.18,
        "max_entry_vpin": 0.65,
        "min_kronos_1h_bps": 8.0,
        "min_kronos_6h_bps": -22.0,
        "min_kronos_24h_bps": -50.0,
        "min_pullback_2h_bps": 32.0,
        "fast_shield_trigger_bps": 38.0,
        "coin_penalty_box_24h": [],
        "kronos_top_conviction_leaders": [],
        "lesson_learned": "Baseline v12.4 Kronos+Gemini parameters active.",
    }

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.state_path = os.path.join(base_dir, "config", "self_improvement_state.json")
        self.journal_path = os.path.join(base_dir, "config", "self_improvement_journal.jsonl")
        self._last_run_ts: float = 0.0

    def load_state(self) -> Dict[str, Any]:
        st = dict(self.DEFAULT_STATE)
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for k, v in saved.items():
                    st[k] = v
            except Exception:
                pass
        st["min_entry_ofi"] = _clamp(st.get("min_entry_ofi", 0.18), 0.15, 0.30, 0.18)
        st["max_entry_vpin"] = _clamp(st.get("max_entry_vpin", 0.65), 0.50, 0.68, 0.65)
        st["min_kronos_1h_bps"] = _clamp(st.get("min_kronos_1h_bps", 8.0), 6.0, 15.0, 8.0)
        st["min_kronos_6h_bps"] = _clamp(st.get("min_kronos_6h_bps", -22.0), -25.0, 0.0, -22.0)
        st["min_kronos_24h_bps"] = _clamp(st.get("min_kronos_24h_bps", -50.0), -50.0, 0.0, -50.0)
        st["min_pullback_2h_bps"] = _clamp(st.get("min_pullback_2h_bps", 32.0), 25.0, 48.0, 32.0)
        st["fast_shield_trigger_bps"] = _clamp(st.get("fast_shield_trigger_bps", 38.0), 28.0, 52.0, 38.0)
        if not isinstance(st.get("coin_penalty_box_24h"), list):
            st["coin_penalty_box_24h"] = []
        if not isinstance(st.get("kronos_top_conviction_leaders"), list):
            st["kronos_top_conviction_leaders"] = []
        return st

    def run_self_improvement_cycle(
        self,
        conn: sqlite3.Connection,
        nav_usdc: float,
        free_usdc: float,
        telemetry_rows: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        now = time.time()
        current_state = self.load_state()
        if (now - self._last_run_ts) < 1800.0 and current_state.get("updated_at"):
            return current_state

        gemini_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
        if not gemini_key:
            return current_state

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT fill_time, inst_id, side, fill_px, fill_sz, notional_usd, fee_usd, realized_pnl_usd
                FROM predator_fills_ledger
                WHERE side='sell' AND datetime(fill_time) >= datetime('now', '-6 hours')
                ORDER BY fill_time DESC LIMIT 15
                """
            )
            recent_sells = [
                {
                    "ts": r[0], "inst_id": r[1], "px": r[3], "notional": r[5],
                    "fee": r[6], "net_pnl": r[7]
                }
                for r in cur.fetchall()
            ]
            cur.execute(
                """
                SELECT inst_id, status, COUNT(*), ROUND(AVG((tp_px - buy_px)/buy_px * 10000.0), 1)
                FROM fresh_scalp_tranches
                WHERE status IN ('CLOSED_PROFIT', 'CLOSED_STOPLOSS')
                GROUP BY inst_id, status
                """
            )
            tranche_outcomes = [
                {"inst_id": r[0], "status": r[1], "count": r[2], "avg_move_bps": r[3]}
                for r in cur.fetchall()
            ]
        except Exception:
            return current_state

        # Build compact 5-Horizon Kronos perspective matrix (1h, 2h, 6h, 12h, 24h + TP prob + L2 OFI)
        kronos_matrix = []
        for t in (telemetry_rows or []):
            kronos_matrix.append({
                "id": t.get("inst_id"),
                "ofi": t.get("ofi_norm"),
                "vpin": t.get("vpin_toxicity"),
                "k5m": t.get("kronos_5m_bps", 0.0), "k10m": t.get("kronos_10m_bps", 0.0), "k1h": t.get("kronos_1h_bps"),
                "k2h": t.get("kronos_2h_bps"),
                "k6h": t.get("kronos_6h_bps"),
                "k12h": t.get("kronos_12h_bps"),
                "k24h": t.get("kronos_24h_bps"),
                "tp_prob": t.get("tp_touch_prob_1h"),
            })

        prompt = (
            "You are the Autonomous Quantitative Self-Improvement Engine of TRE OS v12.5 (OKX Spot EEA), "
            "uniting last-6h trade post-mortems with Tsinghua Kronos 5-Horizon forecasts (1h, 2h, 6h, 12h, 24h). "
            f"Current NAV: ${nav_usdc:.2f} USDC (Free Cash: ${free_usdc:.2f} USDC). "
            f"Standard Reference Baseline: {json.dumps(self.DEFAULT_STATE)}. "
            f"Last 6h Closed Sells: {json.dumps(recent_sells)}. "
            f"Live 5-Horizon Kronos Trajectory Matrix (1h/2h/6h/12h/24h bps): {json.dumps(kronos_matrix)}. "
            "CRITICAL ANTI-PARALYSIS RULE: Do NOT ratchetingly push parameters to extreme bounds! "
            "If Free Cash is > 65% of NAV and Last 6h Closed Sells is empty, keep entry thresholds close to the Standard Reference Baseline "
            "(min_entry_ofi ~0.18-0.24, max_entry_vpin ~0.58-0.65, min_kronos_1h_bps ~8-12, min_kronos_6h_bps ~-15 to 0, min_pullback_2h_bps ~30-40) so capital can deploy on valid setups! "
            "Select up to 3 coins with the strongest positive 5-Horizon Kronos alignment in kronos_top_conviction_leaders. "
            "Return ONLY valid JSON with keys: min_entry_ofi, max_entry_vpin, min_kronos_1h_bps, min_kronos_6h_bps, min_kronos_24h_bps, "
            "min_pullback_2h_bps, fast_shield_trigger_bps, coin_penalty_box_24h, kronos_top_conviction_leaders, lesson_learned (in Italian)."
        )

        for g_mod in ("gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"):
            try:
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_mod}:generateContent"
                g_payload = {
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.15, "responseMimeType": "application/json"},
                }
                req = urllib.request.Request(
                    g_url,
                    data=json.dumps(g_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", ("x-goog-" + "api-key"): gemini_key},
                )
                with urllib.request.urlopen(req, timeout=14, context=_ssl_ctx()) as resp:
                    d = json.loads(resp.read().decode("utf-8"))
                    txt = (
                        d.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    ).strip()
                    if txt and "{" in txt:
                        parsed = json.loads(txt)
                        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        new_state = {
                            "updated_at": now_iso,
                            "model_used": f"google-free:{g_mod}",
                            "min_entry_ofi": _clamp(parsed.get("min_entry_ofi"), 0.15, 0.45, current_state["min_entry_ofi"]),
                            "max_entry_vpin": _clamp(parsed.get("max_entry_vpin"), 0.40, 0.68, current_state["max_entry_vpin"]),
                            "min_kronos_1h_bps": _clamp(parsed.get("min_kronos_1h_bps"), 6.0, 22.0, current_state["min_kronos_1h_bps"]),
                            "min_kronos_6h_bps": _clamp(parsed.get("min_kronos_6h_bps"), -25.0, 15.0, current_state["min_kronos_6h_bps"]),
                            "min_kronos_24h_bps": _clamp(parsed.get("min_kronos_24h_bps"), -50.0, 20.0, current_state["min_kronos_24h_bps"]),
                            "min_pullback_2h_bps": _clamp(parsed.get("min_pullback_2h_bps"), 25.0, 70.0, current_state["min_pullback_2h_bps"]),
                            "fast_shield_trigger_bps": _clamp(parsed.get("fast_shield_trigger_bps"), 28.0, 55.0, current_state["fast_shield_trigger_bps"]),
                            "coin_penalty_box_24h": [str(x) for x in (parsed.get("coin_penalty_box_24h") or [])[:3]],
                            "kronos_top_conviction_leaders": [str(x) for x in (parsed.get("kronos_top_conviction_leaders") or [])[:3]],
                            "lesson_learned": str(parsed.get("lesson_learned") or current_state["lesson_learned"])[:320],
                        }
                        with open(self.state_path, "w", encoding="utf-8") as sf:
                            json.dump(new_state, sf, indent=2, ensure_ascii=False)
                        with open(self.journal_path, "a", encoding="utf-8") as jf:
                            jf.write(json.dumps(new_state, ensure_ascii=False) + "\n")
                        self._last_run_ts = now
                        return new_state
            except Exception:
                continue

        self._last_run_ts = now
        return current_state
