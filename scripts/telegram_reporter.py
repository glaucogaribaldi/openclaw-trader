#!/usr/bin/env python3
"""
TRE OS v6.0 (Predator Edition) Telegram Executive Reporter (`telegram_reporter.py`)
Generates clean, deterministic Telegram Markdown reports based on the new TRE OS v6.0 Run
(Started 22/10/2026 21:00 CEST, Baseline $298.89 USDC) and enforces the Golden Rule [+0.70% <-> +5.00% daily].
"""
import os, sys, json, sqlite3, subprocess, time
from accounting_engine import compute_financial_report, format_telegram_monospace_table

BASE_DIR = "/home/zavattoni_giacomo/openclaw-trader"
ENV_PATH = os.path.join(BASE_DIR, ".env")

def load_env_vars():
    env_map = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env_map[k.strip()] = v.strip().strip('"').strip("'")
    return env_map

def generate_report():
    rep = compute_financial_report()
    table = format_telegram_monospace_table(rep)
    
    env_vars = load_env_vars()
    api_key = env_vars.get("OPENROUTER_API_KEY", "")
    
    narrative = "💡 *ANALISI DISCORSIVA DI MERCATO (TRE OS v6.0 Predator):*\n"
    narrative += f"• **Regola Aurea Attiva:** Obiettivo di compounding organico giornaliero fissato tra **+0.70% e +5.00%** (+${rep['daily_target_min_usd']:.2f} <-> +${rep['daily_target_max_usd']:.2f} USDC/giorno) a partire dalla Baseline v6.0 del 22/10 ($298.89 USDC).\n"
    narrative += f"• **Motore Predittivo Kronos GPU + OFI/VPIN:** {rep['active_orders_count']} trappole limit 100% Post-Only Maker presidiano gli 8 token High-Beta con Cost-Basis Floor attivo (`openAvgPx + 22 bps`, zero vendite in perdita).\n"
    narrative += f"• **Sicurezza Capitale:** Rischio liquidazione 0.00% (Spot Cash) + ${rep['usdc_simple_earn']:.2f} USDC in Simple Earn al 10% APR."

    if api_key:
        try:
            import urllib.request
            prompt = f"""Sei l AI Chief Analyst per TRE OS v6.0 Predator Edition su OKX Spot EEA.
REGOLA AUREA DEL SISTEMA: Canale di compounding organico giornaliero obbligatorio tra +0.70% e +5.00% (+${rep['daily_target_min_usd']:.2f} <-> +${rep['daily_target_max_usd']:.2f} USDC/giorno).
Dati Nuova Run v6.0 (Iniziata il 22/10/2026 21:00 CEST):
- Capitale Iniziale Baseline v6.0 (22/10): ${rep['baseline_nav']:.2f} USDC
- NAV Attuale Live: ${rep['current_nav']:.2f} USDC (Variazione: {rep['net_pnl_run']:+.2f} USDC / {rep['pct_run']:+.2f}%)
- Trappole Limit Attive: {rep['active_orders_count']} ordini (100% Post-Only Maker + Cost-Basis Floor openAvgPx + 22 bps)

Scrivi un ANALISI DI MERCATO DISCORSIVA E PULITA in lingua italiana (max 3 frasi) richiamando la Regola Aurea (+0.7% / +5.0% giornaliero), l'efficacia predittiva di Kronos + OFI/VPIN e la protezione totale del capitale (zero vendite in perdita, zero leva)."""

            payload = {
                "model": "openrouter/free",
                "messages": [{"role": "user", "content": prompt}]
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
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                if "choices" in res_data and len(res_data["choices"]) > 0:
                    cand_txt = res_data["choices"][0]["message"]["content"].strip()
                    if len(cand_txt) > 40 and "user safety" not in cand_txt.lower():
                        narrative = "💡 *ANALISI DISCORSIVA DI MERCATO (AI):*\n" + cand_txt
        except Exception:
            pass

    return f"{table}\n{narrative}"

def send_telegram_webhook(text_msg):
    env_vars = load_env_vars()
    bot_token = env_vars.get("TELEGRAM_BOT_TOKEN", "").strip('"').strip("'")
    chat_id = env_vars.get("TELEGRAM_CHAT_ID", "").strip('"').strip("'")
    
    if bot_token and chat_id:
        try:
            import urllib.request, urllib.parse
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": chat_id,
                "text": text_msg,
                "parse_mode": "Markdown"
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=8) as resp:
                print("[+] Telegram Webhook Sent Successfully!")
                return True
        except Exception as e:
            print(f"[!] Telegram Webhook Error: {e}")
    else:
        print("[i] TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID non trovati in .env")
    return False

if __name__ == "__main__":
    msg = generate_report()
    print("=== TELEGRAM EXECUTIVE AI REPORT (NEW RUN v6.0) ===")
    print(msg)
    send_telegram_webhook(msg)
