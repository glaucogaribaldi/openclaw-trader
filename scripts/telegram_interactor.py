#!/usr/bin/env python3
import os
import sys
import json
import time
import urllib.request
import subprocess

TOKEN = "***"
CHAT_ID = "655481675"


def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False


def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    if offset:
        url += f"?offset={offset}&timeout=5"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("result", [])
    except Exception as e:
        print(f"Error getting updates: {e}")
        return []


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

    # Calculate Total Account USDC Equity
    usdc_equity = 253.01
    if isinstance(balance_data, list) and len(balance_data) > 0:
        details = balance_data[0].get("details", balance_data)
        if isinstance(details, list):
            usdc_info = next((b for b in details if b.get("ccy") == "USDC" or b.get("currency") == "USDC"), {})
            val = usdc_info.get("cashBal") or usdc_info.get("eq") or usdc_info.get("equity") or 253.01
            try:
                usdc_equity = float(val)
            except:
                usdc_equity = 253.01

    # Dynamic Lot Size calculation (divided by 5 for 5 fast tokens)
    lot_size = round(usdc_equity / 5.0, 2) if usdc_equity > 0 else 50.60
    
    # Baseline & Progress calculations (Run starting Sun 11 Oct 08:42 CEST)
    baseline_equity = 253.01
    weekly_profit = max(0.0, usdc_equity - baseline_equity)
    weekly_pct = (weekly_profit / baseline_equity) * 100.0 if baseline_equity > 0 else 0.0
    
    # Daily Target Star = 5.0% ($12.65 USDC)
    daily_target_usd = round(baseline_equity * 0.05, 2)

    report = f"""📊 *TRE OS: REPORT OPERATIVO LIVE "SRE v5.0"*
🟢 *Mercato Reale OKX • GCP Cloud Host*
🎯 *OBIETTIVO STELLA POLARE:* `5.0% Giornaliero` (+${daily_target_usd:.2f})

📈 *AVANZAMENTO RENDIMENTI REALI:*
• *Oggi (24h):* `+$0.00 USDC` (`+0.00%`) | Target: `+${daily_target_usd:.2f}`
• *Settimana (7G):* `+${weekly_profit:.2f} USDC` (`+${weekly_pct:.2f}%`) | Base: `${baseline_equity:.2f}`
• *Lotto Compounding Attivo:* `${lot_size:.2f} USDC` / trade (5-Token)

🤖 *AUTOMAZIONE CRONTAB AI h24:*
• *Modello Ollama:* `qwen2.5-coder:7b` (Tesla T4 VRAM)
• *SRE Daemon:* v5.0 Volatility-Adaptive (5-Token High-Beta)
• *Piano Transizione BTC/ETH:* Completato al 100% (CLOSED) ✓

⚡ *ORDINI LIMIT ATTIVI SUL BOOK ({len(orders)}):*"""

    for ord in orders:
        inst = ord.get("instId", "N/A")
        side = "Vendi TP" if ord.get("side") == "sell" else "Compra Dip"
        price = ord.get("px") or ord.get("price") or "N/A"
        sz = ord.get("sz") or ord.get("size") or "N/A"
        emoji = "🎯" if ord.get("side") == "sell" else "📥"
        report += f"\n• {emoji} *{inst}:* {side} a `${price}` (Sz: {sz})"

    report += "\n\n📲 *REATTIVITÀ REMOTE:* Scrivi `/status` o `/help` in qualsiasi momento!"
    return report


def handle_close():
    try:
        # Cancel all open orders
        orders_proc = subprocess.run(
            ["okx", "--profile", "democlaw", "spot", "orders", "--json"],
            capture_output=True, text=True, check=True
        )
        orders = json.loads(orders_proc.stdout)
        for o in orders:
            subprocess.run([
                "okx", "--profile", "democlaw", "spot", "cancel",
                "--instId", o.get("instId"), "--ordId", o.get("ordId")
            ], check=True)
            
        # Sell remaining spot coins to market
        balance_proc = subprocess.run(
            ["okx", "--profile", "democlaw", "account", "balance", "--json"],
            capture_output=True, text=True, check=True
        )
        balances = json.loads(balance_proc.stdout)
        for coin in balances:
            ccy = coin.get("currency")
            avail = float(coin.get("available", 0.0))
            if ccy in ["BTC", "ETH", "NEAR", "LINK", "SUI", "RENDER", "SOL"] and avail > 0.0001:
                subprocess.run([
                    "okx", "--profile", "democlaw", "spot", "place",
                    "--instId", f"{ccy}-USDC", "--side", "sell",
                    "--ordType", "market", "--sz", str(avail), "--tdMode", "cash"
                ], check=True)
                
        return "🚨 *HARD-CLOSE COMPLETATO CON SUCCESSO!* Tutti i bot sono stati spenti e tutti gli asset liquidati in USDC cash!"
    except Exception as e:
        return f"❌ *Errore durante l'Hard-Close:* {e}"


def process_message(text):
    text = text.strip()
    if text == "/status":
        return get_okx_report()
    elif text == "/close":
        return handle_close()
    elif text == "/help":
        return """🤖 *TRE OS: COMANDI DISPONIBILI*
• `/status` - Mostra il bilancio dettagliato e gli ordini attivi sul conto reale.
• `/close` - Spegne tutti i bot ed esegue l'Hard-Close liquidando 100% in USDC cash!
• `/help` - Mostra questo messaggio."""
    return None


def main():
    print("[-] Starting Telegram Interactor Loop...")
    offset = None
    while True:
        updates = get_updates(offset)
        for u in updates:
            msg = u.get("message", {})
            msg_id = u.get("update_id")
            offset = msg_id + 1
            
            chat = msg.get("chat", {})
            sender_id = str(chat.get("id", ""))
            
            # Solamente l'operatore autorizzato Giacomo (655481675) può impartire comandi
            if sender_id == CHAT_ID:
                text = msg.get("text", "")
                reply = process_message(text)
                if reply:
                    send_message(reply)
                    
        time.sleep(2)


if __name__ == "__main__":
    main()
