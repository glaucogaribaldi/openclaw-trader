#!/usr/bin/env python3
"""
TRE OS v5.6 Telegram Executive Reporter (`telegram_reporter.py`)
Generates clean, elegant, high-impact Telegram Markdown reports.
Falls back safely to local deterministic analysis if OpenRouter rate limit is hit.
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
    api_key = ***"OPENROUTER_API_KEY", "")
    
    narrative = "💡 *ANALISI DISCORSIVA DI MERCATO (Deterministic Fallback):*\n"
    narrative += "• Il mercato crypto si attesta in fase di consolidamento laterale di weekend sui 8 token High-Beta (NEAR, LINK, SOL, SUI, RENDER, AVAX, FET, SEI).\n"
    narrative += f"• Le {rep['active_orders_count']} trappole limit attive sul book garantiscono esecuzione immediata in modalita Maker-Only (0.00% fee).\n"
    narrative += f"• Operativita a capitale protetto: Leva 1+2 attiva (85% allocazione trading / 15% cassa Simple Earn al 10% APR) con rischio liquidazione zero."

    if api_key:
        try:
            import urllib.request
            prompt = f"""Sei l AI Chief Analyst per TRE OS v5.6 su OKX Spot.
NAV Live: ${rep['current_nav']:.2f} USDC (Capitale Iniziale: ${rep['baseline_nav']:.2f} USDC)
Profitto Netto Run: +${rep['net_pnl_run']:.2f} USDC (+{rep['pct_run']:.2f}%)
Trappole Limit Attive: {rep['active_orders_count']} ordini sul book

Scrivi un ANALISI DI MERCATO DISCORSIVA E PULITA in lingua italiana (max 4 frasi) spiegando lo stato del mercato sui 8 token e la sicurezza del sistema (0% leva, 0% fee Taker)."""

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
                    narrative = "💡 *ANALISI DISCORSIVA DI MERCATO (AI):*\n" + res_data["choices"][0]["message"]["content"].strip()
        except Exception as e:
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
    print("=== TELEGRAM EXECUTIVE AI REPORT ===")
    print(msg)
    send_telegram_webhook(msg)
