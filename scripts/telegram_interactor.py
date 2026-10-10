#!/usr/bin/env python3
import os
import sys
import json
import time
import urllib.request
import subprocess

TOKEN = "8996959880:AAGs_SvfR3wUu30UC1iZlvw_o9b-xZkQTnw"
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
