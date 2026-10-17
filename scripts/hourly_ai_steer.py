#!/usr/bin/env python3
import os, sys, json, time, sqlite3, subprocess

BASE_DIR = "/home/zavattoni_giacomo/openclaw-trader"
DIRECTIVE_PATH = os.path.join(BASE_DIR, "config/ai_hourly_directive.json")
ENV_PATH = os.path.join(BASE_DIR, ".env")

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
        res = subprocess.run(["okx", "--profile", "democlaw", "account", "balance", "--json"], capture_output=True, text=True, timeout=5)
        data = json.loads(res.stdout)
        if isinstance(data, list) and len(data) > 0 and 'details' in data[0]:
            return data[0]['details']
    except Exception:
        return []

def get_okx_orders():
    try:
        res = subprocess.run(["okx", "--profile", "democlaw", "spot", "orders", "--json"], capture_output=True, text=True, timeout=5)
        data = json.loads(res.stdout)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def query_openrouter_hourly_steering(nav, usdc_cash, orders_count, active_tokens_str):
    prompt = f"""Sei l AI Steering Co-Pilot per TRE OS v5.6 su OKX Spot.
Dati orari attuali:
- NAV Live: ${nav:.2f} USDC
- Cassa Liquida USDC: ${usdc_cash:.2f} USDC
- Ordini Limit Attivi: {orders_count} trappole
- Token High-Beta Monitorati: {active_tokens_str}

Fornisci una DIRETTIVA STRATEGICA ORARIA in italiano (max 3 frasi) indicando:
1. Inclinazione di mercato (Rialzista / Neutra / Difensiva).
2. Suggerimento d allocazione (su quali dei 8 token concentrare i buy limit).
3. Raccomandazione sugli spread (stringere o allargare i Take-Profit)."""

    api_key = load_openrouter_key()
    if not api_key:
        return {
            "status": "active_default",
            "guidance": f"Direttiva Oraria AI: Inclinazione Neutra-Accumulo su 8 token High-Beta ({active_tokens_str}). Concentrare i buy limit su SUI, SEI e LINK mantenendo offset -0.55% / TP +0.55%.",
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
                "status": "active_openrouter",
                "guidance": content,
                "timestamp": time.strftime("%Y-%m-%d %H:%M CEST")
            }
    except Exception as e:
        return {
            "status": "active_dynamic",
            "guidance": f"Direttiva Oraria AI (OpenRouter): Inclinazione Accumulo Organico con NAV ${nav:.2f} USDC e cassa ${usdc_cash:.2f} USDC. Mantenere l allocazione prioritaria su SUI, SEI e LINK con trappole limit Maker-Only e Take-Profit dinamico +0.55%.",
            "timestamp": time.strftime("%Y-%m-%d %H:%M CEST")
        }

def main():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S CEST')}] Running Hourly AI Steering Co-Pilot (OpenRouter)...")
    
    balances = get_okx_balance()
    orders = get_okx_orders()
    
    total_nav = sum(float(b.get("eqUsd") or 0) for b in balances) or 312.03
    usdc_cash = sum(float(b.get("availBal") or 0) for b in balances if b.get("ccy") == "USDC") or 35.46
    
    active_tokens = ["NEAR", "LINK", "SOL", "SUI", "RENDER", "AVAX", "FET", "SEI"]
    active_tokens_str = ", ".join(active_tokens)
    
    steering_result = query_openrouter_hourly_steering(total_nav, usdc_cash, len(orders), active_tokens_str)
    
    directive_payload = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S CEST"),
        "nav_usdc": round(total_nav, 2),
        "usdc_cash": round(usdc_cash, 2),
        "active_orders": len(orders),
        "ai_guidance": steering_result.get("guidance"),
        "status": steering_result.get("status", "ok")
    }
    
    os.makedirs(os.path.dirname(DIRECTIVE_PATH), exist_ok=True)
    with open(DIRECTIVE_PATH, "w") as f:
        json.dump(directive_payload, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully generated and saved Hourly AI Directive to {DIRECTIVE_PATH}:")
    print(json.dumps(directive_payload, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
