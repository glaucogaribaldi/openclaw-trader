#!/usr/bin/env python3
import sys
import os
import json
import urllib.request
import subprocess

def get_okx_report():
    try:
        balance_proc = subprocess.run(
            ["okx", "--profile", "democlaw", "account", "balance", "--json"],
            capture_output=True, text=True, check=True
        )
        balance_data = json.loads(balance_proc.stdout)
        
        orders_proc = subprocess.run(
            ["okx", "--profile", "democlaw", "spot", "orders", "--json"],
            capture_output=True, text=True, check=True
        )
        orders = json.loads(orders_proc.stdout)
    except Exception as e:
        return f"❌ *Errore estrazione dati OKX:* {e}"

    # Calculate USDC Equity & Balances
    usdc_bal = 0.0
    if isinstance(balance_data, list) and len(balance_data) > 0:
        details = balance_data[0].get("details", balance_data)
        if isinstance(details, list):
            usdc_info = next((b for b in details if b.get("ccy") == "USDC" or b.get("currency") == "USDC"), {})
            usdc_bal = float(usdc_info.get("eq") or usdc_info.get("equity") or usdc_info.get("availBal") or 0.0)

    # Dynamic Lot Size calculation
    lot_size = round(usdc_bal / 8.0, 2) if usdc_bal > 0 else 32.98

    report = f"""📊 *TRE OS: REPORT OPERATIVO LIVE "SRE v5.0"*
🟢 *Mercato Reale OKX • GCP Cloud Host*

💰 *BILANCIO & TARGET REALI:*
• *Capitale Iniziale:* `$325.03` USDC
• *Profitto Chiuso (Cashed):* *+$6.69 USDC (+2.06%)* 📈
• *USDC Equity Totale:* `${usdc_bal:.2f}` USDC
• *Assetto Attivo:* Compounding 80/20 Moonbag (`${lot_size:.2f}`/lotto)

🤖 *AUTOMAZIONE CRONTAB AI h24:*
• *Modello Ollama:* `qwen2.5-coder:7b` (Tesla T4 VRAM)
• *SRE Daemon:* v5.0 Volatility-Adaptive (7-Token)
• *Piano Transizione:* Attivo (Auto-Exit BTC/ETH su TP)

⚡ *ORDINI LIMIT ATTIVI SUL BOOK ({len(orders)}):*"""

    for ord in orders:
        inst = ord.get("instId", "N/A")
        side = "Vendi TP" if ord.get("side") == "sell" else "Compra Dip"
        price = ord.get("price", "N/A")
        sz = ord.get("size", "N/A")
        emoji = "🎯" if ord.get("side") == "sell" else "📥"
        report += f"\n• {emoji} *{inst}:* {side} a `${price}` (Sz: {sz})"

    report += "\n\n📲 *REATTIVITÀ REMOTE:* Scrivi `/status` o `/help` in qualsiasi momento!"
    return report

def send_telegram(text):
    token = "8996959880:AAGs_SvfR3wUu30UC1iZlvw_o9b-xZkQTnw"
    chat_id = "655481675"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return True
    except Exception as e:
        print(f"Errore Telegram: {e}")
        return False

if __name__ == "__main__":
    report_text = get_okx_report()
    send_telegram(report_text)
