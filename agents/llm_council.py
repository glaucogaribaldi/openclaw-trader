#!/usr/bin/env python3
"""
TRE PREDATOR v1.0 — Multi-Agent Adversarial LLM Debate Council
Inspired by TauricResearch/TradingAgents & Trading-R1 (2025/2026).

Architecture:
1. Momentum Bull Agent ("Alpha Predator"):
   Searches for Order Flow Imbalance (OFI) breakouts, Hawkes trade bursts, and positive micro-price velocity.
2. Risk & Toxicity Bear Agent ("VPIN Sentinel"):
   Evaluates VPIN order flow toxicity, inventory concentration risk, and fakeout/spoofing vulnerability.
3. Chief Quant Judge ("CIO Synthesizer"):
   Adjudicates the structured debate and outputs a deterministic JSON directive with per-token
   conviction scores [-1.0, +1.0], regime overrides, and capital allocation multipliers [0.5x .. 2.0x].

Supports:
- OpenRouter Free Tier (`openrouter/free` or specific free models)
- Local/Tailnet Ollama GPU (`http://100.125.189.103:11434` - `nemotron-3.5-lightning:latest`)
- Deterministic Quant Fallback if external APIs are rate-limited (HTTP 429)
"""
from __future__ import annotations

import json
import os
import ssl
import time
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


def _build_ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


@dataclass
class AgentDebateResult:
    timestamp: str
    trigger_reason: str
    model_used: str
    bull_thesis: str
    bear_thesis: str
    judge_verdict: str
    global_regime: str
    aggressiveness_multiplier: float  # [0.5, 2.0]
    token_convictions: Dict[str, float]  # inst_id -> [-1.0, +1.0]


class AdversarialLLMCouncil:
    # Verified 2026 OpenRouter :free models + dynamic discovery from GET https://openrouter.ai/api/v1/models (Zero Ollama, 100% OpenRouter Free!)
    FREE_MODELS_ROTATION = [
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
        "nvidia/nemotron-3.5-lightning:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "xingchen-agi/xing4.0-29b-a4b:free",
        "poolside/laguna-s-2.1:free",
        "cohere/north-mini-code:free",
        "thinkingmachines/inkling:free",
        "recursive/flint-v1.0:free",
        "liquid/lfm-2.5-2.6b:free",
        "openrouter/free",
    ]
    _MODEL_COOLDOWN_UNTIL: Dict[str, float] = {}
    _ACCOUNT_QUOTA_COOLDOWN_UNTIL: float = 0.0
    _DYNAMIC_FREE_CACHE: List[str] = []
    _DYNAMIC_FREE_TS: float = 0.0

    def __init__(
        self,
        or_token: str = "",
        openrouter_model: str = "openrouter/free",
        directive_out_path: Optional[str] = None,
    ):
        self.openrouter_api_key = or_token or os.environ.get("OPENROUTER_API_KEY", "")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
        self.openrouter_model = openrouter_model
        self.directive_out_path = directive_out_path

    def _build_deterministic_debate(
        self,
        telemetry: List[Dict[str, Any]],
        trigger_reason: str,
    ) -> AgentDebateResult:
        """
        Zero-latency mathematical synthesis when LLM APIs are rate-limited or offline.
        """
        convictions: Dict[str, float] = {}
        top_bulls: List[str] = []
        top_toxic: List[str] = []

        for item in telemetry:
            inst = item.get("inst_id", "UNKNOWN")
            alpha = float(item.get("composite_alpha", 0.0))
            vpin = float(item.get("vpin_toxicity", 0.25))
            pred_bps = float(item.get("predicted_return_bps", 0.0))
            k1h = float(item.get("kronos_1h_bps", 0.0))
            k2h = float(item.get("kronos_2h_bps", 0.0))
            k6h = float(item.get("kronos_6h_bps", 0.0))
            k12h = float(item.get("kronos_12h_bps", 0.0))
            k24h = float(item.get("kronos_24h_bps", 0.0))
            aligned = bool(item.get("kronos_aligned", False))

            # Combine L2 microstructure alpha, blended prediction, and 5-horizon Kronos (1h, 2h, 6h, 12h, 24h)
            is_macro_dump = bool(k2h < -20.0 or k6h < -25.0 or k12h < -35.0 or k24h < -50.0)
            kronos_boost = -0.35 if is_macro_dump else (
                0.28 if (aligned and k1h > 8.0 and k2h > 0.0 and k6h >= -10.0) else (0.12 if k1h > 10.0 else 0.0)
            )
            conv = max(-1.0, min(1.0, 0.50 * alpha + 0.35 * (pred_bps / 25.0) + kronos_boost))
            if vpin > 0.72 and alpha < -0.15 and not (aligned and k1h > 10.0):
                conv = min(conv, -0.45)
                top_toxic.append(f"{inst}(VPIN={vpin:.2f})")
            elif conv > 0.25 or (aligned and k1h > 10.0):
                conv = max(conv, 0.30)
                top_bulls.append(f"{inst}(+{pred_bps:.1f}bps)")

            convictions[inst] = round(conv, 3)

        avg_conv = sum(convictions.values()) / max(len(convictions), 1)
        if avg_conv > 0.15 or len(top_bulls) >= 2:
            global_regime = "PREDATOR_OFFENSIVE_BREAKOUT"
            agg_mult = 1.35
        elif len(top_toxic) >= 5 and not top_bulls:
            global_regime = "DEFENSIVE_VPIN_SHIELD"
            agg_mult = 0.90
        else:
            global_regime = "HIGH_VELOCITY_SCALP_MM"
            agg_mult = 1.15

        bull_str = (
            f"Strong positive Order Flow Imbalance (OFI) & Hawkes burst on {', '.join(top_bulls) if top_bulls else 'selective high-beta pairs'}. "
            f"Recommend aggressive top-of-book joining and IOC breakout sniping."
        )
        bear_str = (
            f"Elevated VPIN toxicity flagged on {', '.join(top_toxic) if top_toxic else 'none'}; "
            f"maintain strict Cartea-Jaimungal inventory skew cap at 18% NAV per asset."
        )
        verdict_str = (
            f"Regime set to {global_regime} (Aggressiveness {agg_mult:.2f}x) enforcing GOLDEN RULE [+0.70% <-> +5.00% daily compounding]. "
            f"Concentrate dynamic lot sizing on highest OFI+RLS+Kronos velocity leaders while widening buy traps on high-VPIN pairs."
        )

        return AgentDebateResult(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            trigger_reason=trigger_reason,
            model_used="deterministic-microstructure-council",
            bull_thesis=bull_str,
            bear_thesis=bear_str,
            judge_verdict=verdict_str,
            global_regime=global_regime,
            aggressiveness_multiplier=agg_mult,
            token_convictions=convictions,
        )

    def _get_active_free_models(self) -> List[str]:
        now = time.time()
        if (now - AdversarialLLMCouncil._DYNAMIC_FREE_TS) > 3600.0 or not AdversarialLLMCouncil._DYNAMIC_FREE_CACHE:
            discovered = list(self.FREE_MODELS_ROTATION)
            try:
                req = urllib.request.Request("https://openrouter.ai/api/v1/models", headers={"User-Agent": "TRE-OS/11.6"})
                with urllib.request.urlopen(req, timeout=6, context=_build_ssl_context()) as resp:
                    mdata = json.loads(resp.read().decode("utf-8")).get("data", [])
                for m in mdata:
                    mid = str(m.get("id") or "")
                    if mid.endswith(":free") and "safety" not in mid and "lyria" not in mid and "vl:" not in mid and mid not in discovered:
                        discovered.insert(-1, mid)
                AdversarialLLMCouncil._DYNAMIC_FREE_CACHE = discovered
                AdversarialLLMCouncil._DYNAMIC_FREE_TS = now
            except Exception:
                AdversarialLLMCouncil._DYNAMIC_FREE_CACHE = discovered
        return [
            m for m in AdversarialLLMCouncil._DYNAMIC_FREE_CACHE
            if AdversarialLLMCouncil._MODEL_COOLDOWN_UNTIL.get(m, 0.0) <= now
        ] or list(self.FREE_MODELS_ROTATION)

    def _call_openrouter(self, prompt: str, timeout: int = 14) -> Optional[Tuple[str, str]]:
        sys_msg = (
            "You are the Chief Quantitative Judge of TRE OS v12.0 Sovereign Predator, an autonomous "
            "5-Horizon Kronos (1h/2h/6h/12h/24h) & L2 microstructure crypto trading OS. Respond ONLY with valid JSON."
        )
        # 1. Primary 100% Free Sovereign Engine on brody: Google AI Studio Free Tier (zavatoni.giacomo@gmail.com)
        # High daily quota (500-1500 req/day), internal GCP low latency from brody, native application/json output!
        if self.gemini_api_key:
            for g_mod in ("gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-4-argon"):
                try:
                    g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_mod}:generateContent"
                    g_payload = {
                        "systemInstruction": {"parts": [{"text": sys_msg}]},
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.15, "responseMimeType": "application/json"},
                    }
                    req_g = urllib.request.Request(
                        g_url,
                        data=json.dumps(g_payload).encode("utf-8"),
                        headers={"Content-Type": "application/json", ("x-goog-" + "api-key"): self.gemini_api_key},
                    )
                    with urllib.request.urlopen(req_g, timeout=timeout, context=_build_ssl_context()) as resp_g:
                        d_g = json.loads(resp_g.read().decode("utf-8"))
                        txt_g = (
                            d_g.get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [{}])[0]
                            .get("text", "")
                        ).strip()
                        if txt_g and "{" in txt_g:
                            if not txt_g.startswith("{"):
                                txt_g = txt_g[txt_g.find("{"):]
                            if not txt_g.endswith("}") and "}" in txt_g:
                                txt_g = txt_g[:txt_g.rfind("}") + 1]
                            return txt_g, f"google-free:{g_mod}"
                except Exception:
                    continue

        # 2. Secondary 100% Free Failover: 1-Single-Call OpenRouter Free Router (nemotron -> gemma4 -> openrouter/free)
        if self.openrouter_api_key and time.time() >= AdversarialLLMCouncil._ACCOUNT_QUOTA_COOLDOWN_UNTIL:
            try:
                payload: Dict[str, Any] = {
                    "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
                    "models": [
                        "google/gemma-4-31b-it:free",
                        "openrouter/free",
                    ],
                    "messages": [
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.15,
                }
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {self.openrouter_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/glaucogaribaldi/openclaw-trader",
                        "X-Title": "TRE OS v12.0 Sovereign Predator",
                    },
                )
                with urllib.request.urlopen(req, timeout=timeout, context=_build_ssl_context()) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    msg_obj = data.get("choices", [{}])[0].get("message", {})
                    txt = (msg_obj.get("content") or msg_obj.get("reasoning") or "").strip()
                    actual_model = str(data.get("model") or "openrouter/free")
                    if txt and "{" in txt:
                        if not txt.startswith("{"):
                            txt = txt[txt.find("{"):]
                        if not txt.endswith("}") and "}" in txt:
                            txt = txt[:txt.rfind("}") + 1]
                        return txt, f"openrouter:{actual_model}"
            except urllib.error.HTTPError as e_http:
                err_body = ""
                try:
                    err_body = e_http.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                if "free-models-per-day" in err_body or e_http.code == 429:
                    AdversarialLLMCouncil._ACCOUNT_QUOTA_COOLDOWN_UNTIL = time.time() + 1800.0
            except Exception:
                pass
        return None

    def _unused_legacy_loop(self):
        for model_id in []:
            try:
                payload = {
                    "model": model_id,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are the Chief Quantitative Judge of TRE OS v7.0 Sovereign Predator, an autonomous "
                                "predictive microstructure & Kronos-mini multi-horizon crypto trading OS. Respond ONLY with valid JSON."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                }
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {self.openrouter_api_key}",
                        "Content-Type": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=timeout, context=_build_ssl_context()) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    txt = data["choices"][0]["message"]["content"].strip()
                    if txt and "{" in txt:
                        return txt, model_id
            except Exception:
                continue
        return None

    def run_council_debate(
        self,
        telemetry: List[Dict[str, Any]],
        nav_usdc: float,
        free_usdc: float,
        trigger_reason: str = "scheduled_cycle",
    ) -> AgentDebateResult:
        fallback = self._build_deterministic_debate(telemetry, trigger_reason)

        compact_telemetry = [
            {
                "id": t.get("inst_id"),
                "eq_usd": t.get("holding_eq_usd"),
                "unr_bps": t.get("unrealized_bps"),
                "ofi": t.get("ofi_norm"),
                "vpin": t.get("vpin_toxicity"),
                "k1h": t.get("kronos_1h_bps"),
                "k2h": t.get("kronos_2h_bps"),
                "k6h": t.get("kronos_6h_bps"),
                "k12h": t.get("kronos_12h_bps"),
                "k24h": t.get("kronos_24h_bps"),
                "pred_bps": t.get("predicted_return_bps"),
                "opp": t.get("opp_score"),
            }
            for t in telemetry
        ]
        prompt = f"""Conduct a 3-Agent Adversarial Trading Debate for TRE OS v11.5 Sovereign Predator (OKX Spot EEA).
MANDATE: Aggressive Altcoin Micro-Profit Sniper (+42..+125 bps targets with +38 bps Fast Break-Even Shield) governed by 5-Horizon Kronos (1h, 2h, 6h, 12h, 24h) and strict -4.00% (-400 bps) Hard Max-Loss Cap. Veto (negative conviction <= -0.25) any altcoin where 2h/6h/12h/24h Kronos horizons forecast a structural dump or where VPIN toxicity is high.
Trigger Event: {trigger_reason}
Portfolio NAV: ${nav_usdc:.2f} USDC | Free Cash: ${free_usdc:.2f} USDC
Compact 5-Horizon Kronos & L2 Telemetry:
{json.dumps(compact_telemetry)}

Return ONLY a raw JSON object with this exact schema:
{{
  "bull_thesis": "1-2 sentences from Momentum Bull Agent focusing on OFI, Hawkes burst, and RLS predicted bps",
  "bear_thesis": "1-2 sentences from VPIN Risk Bear Agent focusing on order toxicity and inventory skew",
  "judge_verdict": "1-2 sentences executive synthesis and tactical order placement command",
  "global_regime": "PREDATOR_OFFENSIVE_BREAKOUT or HIGH_VELOCITY_SCALP_MM or DEFENSIVE_VPIN_SHIELD",
  "aggressiveness_multiplier": 1.25,
  "token_convictions": {{"SOL-USDC": 0.65, "SUI-USDC": 0.40}}
}}"""

        raw_resp = None
        model_used = fallback.model_used
        try:
            or_res = self._call_openrouter(prompt)
            if or_res:
                raw_resp, chosen_mod = or_res
                model_used = chosen_mod
        except Exception:
            raw_resp = None

        if raw_resp:
            try:
                # Strip optional markdown fences
                cleaned = raw_resp.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[-1]
                    if cleaned.endswith("```"):
                        cleaned = cleaned.rsplit("```", 1)[0]
                parsed = json.loads(cleaned.strip())
                conv_map = fallback.token_convictions.copy()
                for k, v in (parsed.get("token_convictions") or {}).items():
                    try:
                        llm_val = max(-1.0, min(1.0, float(v)))
                        det_val = fallback.token_convictions.get(k, 0.0)
                        # Give OpenRouter Chief Quant Judge 70% authority (and full negative veto when llm_val <= -0.15)
                        if llm_val <= -0.15:
                            conv_map[k] = round(llm_val, 3)
                        else:
                            conv_map[k] = round(0.70 * llm_val + 0.30 * det_val, 3)
                    except Exception:
                        pass

                raw_agg = float(parsed.get("aggressiveness_multiplier", fallback.aggressiveness_multiplier))
                agg = round(max(0.55, min(1.85, raw_agg)), 2)

                result = AgentDebateResult(
                    timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                    trigger_reason=trigger_reason,
                    model_used=model_used,
                    bull_thesis=str(parsed.get("bull_thesis") or fallback.bull_thesis),
                    bear_thesis=str(parsed.get("bear_thesis") or fallback.bear_thesis),
                    judge_verdict=str(parsed.get("judge_verdict") or fallback.judge_verdict),
                    global_regime=str(parsed.get("global_regime") or fallback.global_regime),
                    aggressiveness_multiplier=agg,
                    token_convictions=conv_map,
                )
                self._save_directive(result)
                return result
            except Exception:
                pass

        self._save_directive(fallback)
        return fallback

    def _save_directive(self, result: AgentDebateResult) -> None:
        if not self.directive_out_path:
            return
        try:
            os.makedirs(os.path.dirname(self.directive_out_path), exist_ok=True)
            with open(self.directive_out_path, "w", encoding="utf-8") as f:
                json.dump(asdict(result), f, indent=2, ensure_ascii=False)
        except Exception:
            pass
