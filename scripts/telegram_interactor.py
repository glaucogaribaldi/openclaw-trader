#!/usr/bin/env python3
import os
import sys
import json
import time
import urllib.request
import subprocess

TOKEN = "8912531115:AAH-fnCwBHlUAjcqkuCM58XPyz2fmgSMoos"
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

    usdc_bal = 0.0
    for coin in balance:
        if coin.get("currency") == "USDC":
            usdc_bal = float(coin.get("equity", 0.0))
            break
            
    report = f"""📊 *TRE OS: STATO PORTAFOGLIO REALE*
    
💰 *BILANCIO:*
• *Saldo Cash USDC:* `{usdc_bal:.2f}` USDC

⚡ *ORDINI IN BOOK ({len(orders)}):*"""
    
    for ord in orders:
        report += f"\n• *{ord.get('instId')}*: {ord.get('side').upper()} Limit a `{ord.get('price')}` (Sz: {ord.get('size')})"
        
    for g in grids:
        if g.get("state") == "running":
            report += f"\n\n🎯 *GRID BOT SOL-USDC (ATTIVO):*\n• *ID:* `{g.get('algoId')}`\n• *Range:* ${g.get('minPx')} - ${g.get('maxPx')}"

    return report


def handle_close():
    try:
        # Stop SOL Grid Bot
        grid_proc = subprocess.run(
            ["okx", "--profile", "democlaw", "bot", "grid", "orders", "--algoOrdType", "grid", "--json"],
            capture_output=True, text=True, check=True
        )
        grids = json.loads(grid_proc.stdout)
        for g in grids:
            if g.get("state") == "running":
                subprocess.run([
                    "okx", "--profile", "democlaw", "bot", "grid", "stop",
                    "--algoId", g.get("algoId"), "--algoOrdType", "grid",
                    "--instId", "SOL-USDC", "--stopType", "1"
                ], check=True)
                
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
            if ccy in ["BTC", "ETH", "NEAR", "LINK"] and avail > 0.00001:
                # Get minimum order sizes or simply sell available
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
• `/status` - Mostra il bilancio e gli ordini attivi sul conto reale.
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
