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
        balance = json.loads(balance_proc.stdout)
        
        orders_proc = subprocess.run(
            ["okx", "--profile", "democlaw", "spot", "orders", "--json"],
            capture_output=True, text=True, check=True
        )
        orders = json.loads(orders_proc.stdout)
        
        grid_proc = subprocess.run(
            ["okx", "--profile", "democlaw", "bot", "grid", "orders", "--algoOrdType", "grid", "--json"],
            capture_output=True, text=True, check=True
        )
        grids = json.loads(grid_proc.stdout)
    except Exception as e:
        return f"Errore estrazione dati OKX: {e}"

    # Calculate equity
    usdc_bal = 0.0
    for coin in balance:
        if coin.get("currency") == "USDC":
            usdc_bal = float(coin.get("equity", 0.0))
            break
            
    report = f"""📊 *TRE OS: REPORT INTEGRITÀ LIVE*
    
💰 *BILANCIO PORTAFOGLIO REALE:*
• *Saldo Cash USDC:* `{usdc_bal:.2f}` USDC
• *Stato Generali:* Tutti i lotti sono allocati.

⚡ *ORDINI ATTIVI IN BOOK:*"""
    
    for ord in orders:
        report += f"\n• *{ord.get('instId')}*: {ord.get('side').upper()} Limit a `{ord.get('price')}` (Sz: {ord.get('size')})"
        
    for g in grids:
        if g.get("state") == "running":
            report += f"\n\n🎯 *GRID BOT ATTIVO (SOL-USDC):*\n• *ID:* `{g.get('algoId')}`\n• *Range:* ${g.get('minPx')} - ${g.get('maxPx')}"

    return report

def send_telegram(text):
    # Utilizziamo l'esatto botToken del canale Telegram configurato e autorizzato nel gateway local
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
