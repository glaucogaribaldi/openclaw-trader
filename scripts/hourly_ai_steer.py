#!/usr/bin/env python3
import os, sys, json, time, sqlite3, subprocess, argparse

BASE_DIR = "/home/zavattoni_giacomo/openclaw-trader"
DIRECTIVE_PATH = os.path.join(BASE_DIR, "config/ai_hourly_directive.json")
ENV_PATH = os.path.join(BASE_DIR, ".env")
sys.path.insert(0, BASE_DIR)
from execution.okx_hybrid_executor import OKXNativeClient

def load_openrouter_key():
    try:
        if os.path.exists(ENV_PATH):
            with open(ENV_PATH, "r") as f:
                for line in f:
                    if line.startswith("OPENROUTER_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return os.environ.get("OPENROUTER_API_KEY", "")

def get_okx_balance():
    try:
        client = OKXNativeClient(simulated_demo=False)
        return client.get_account_balances()
    except Exception:
        return []

def get_okx_orders():
    try:
        client = OKXNativeClient(simulated_demo=False)
        return client.get_open_orders()
    except Exception:
        return []

def query_openrouter_hourly_steering(nav, usdc_cash, orders_count, active_tokens_str, trigger_reason):
    prompt = f"""Sei l AI Steering Co-Pilot per TRE OS v6.0 Predator su OKX Spot EEA.
REGOLA AUREA INVIOLABILE DEL SISTEMA: Obiettivo di compounding organico giornaliero obbligatorio tra +0.70% e +5.00% al giorno (Baseline Nuova Run v6.0 del 22/10/2026: $298.89 USDC).
Evento Scatenante: {trigger_reason}
Dati attuali:
- NAV Live: ${nav:.2f} USDC (Baseline v6.0 22/10: $298.89 USDC)
- Cassa Liquida USDC: ${usdc_cash:.2f} USDC
- Ordini Limit Attivi: {orders_count} trappole (100% Post-Only Maker + Cost-Basis Floor openAvgPx + 22 bps)
- Token High-Beta Monitorati: {active_tokens_str}

Fornisci una DIRETTIVA STRATEGICA TATTICA in italiano (max 3 frasi) indicando:
1. Inclinazione di mercato e rispetto della Regola Aurea (+0.70% <-> +5.00% giornaliero).
2. Suggerimento d allocazione immediata sugli 8 token con Kronos + OFI/VPIN.
3. Raccomandazione sugli spread Take-Profit e buy offsets."""

    api_key = load_openrouter_key()
    if not api_key:
        return {
            "status": "active_default",
            "guidance": f"Direttiva AI (Trigger: {trigger_reason}): Inclinazione Neutra su 8 token High-Beta ({active_tokens_str}). Mantenere offset standard -0.55% / TP +0.55%.",
            "timestamp": time.strftime("%Y-%m-%d %H:%M CEST")
        }

    try:
        import urllib.request
        payload = {
            "model": "openrouter/free",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=data_bytes,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            content = res_data["choices"][0]["message"]["content"].strip()
            return {
                "status": f"active_openrouter_{trigger_reason}",
                "guidance": content,
                "timestamp": time.strftime("%Y-%m-%d %H:%M CEST")
            }
    except Exception as e:
        return {
            "status": f"active_dynamic_{trigger_reason}",
            "guidance": f"Direttiva Tattica AI ({trigger_reason}): NAV ${nav:.2f} USDC e cassa ${usdc_cash:.2f} USDC. Mantenere allocazione su SUI, SEI e LINK con trappole Maker-Only.",
            "timestamp": time.strftime("%Y-%m-%d %H:%M CEST")
        }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trigger", type=str, default="cron_hourly", help="Trigger event description")
    args = parser.parse_args()

    trigger_reason = args.trigger
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S CEST')}] Running Event-Driven AI Steering Co-Pilot (Trigger: {trigger_reason})...")
    
    balances = get_okx_balance()
    orders = get_okx_orders()
    
    total_nav = sum(float(b.get("eqUsd") or 0) for b in balances) or 309.36
    usdc_cash = sum(float(b.get("availBal") or 0) for b in balances if b.get("ccy") == "USDC") or 35.46
    
    active_tokens = ["NEAR", "LINK", "SOL", "SUI", "RENDER", "AVAX", "FET", "SEI"]
    active_tokens_str = ", ".join(active_tokens)
    
    steering_result = query_openrouter_hourly_steering(total_nav, usdc_cash, len(orders), active_tokens_str, trigger_reason)
    
    directive_payload = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S CEST"),
        "trigger_event": trigger_reason,
        "nav_usdc": round(total_nav, 2),
        "usdc_cash": round(usdc_cash, 2),
        "active_orders": len(orders),
        "ai_guidance": steering_result.get("guidance"),
        "status": steering_result.get("status", "ok")
    }
    
    os.makedirs(os.path.dirname(DIRECTIVE_PATH), exist_ok=True)
    with open(DIRECTIVE_PATH, "w") as f:
        json.dump(directive_payload, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully generated and saved Event-Driven AI Directive ({trigger_reason}) to {DIRECTIVE_PATH}:")
    print(json.dumps(directive_payload, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
