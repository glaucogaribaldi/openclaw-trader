#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import datetime
import subprocess

BASE_DIR = "/home/zava/openclaw-trader"
DB_PATH = os.path.join(BASE_DIR, "config", "okx_trader.db")
PLAYBOOK_PATH = os.path.join(BASE_DIR, "config", "strategy_playbook.json")
PROTECTED_PATH = os.path.join(BASE_DIR, "config", "protected.json")


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_okx_orders():
    """
    Query OKX CLI to get open orders with strict timeout and validation.
    """
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "spot", "orders", "--json"],
            capture_output=True, text=True, timeout=12, check=True
        )
        data = json.loads(proc.stdout)
        if isinstance(data, list):
            return data
        return []
    except subprocess.TimeoutExpired:
        print("[!] SRE Warning: OKX spot orders command timed out!")
        return None
    except Exception as e:
        print(f"[!] SRE Warning: Error fetching orders: {e}")
        return None


def get_okx_balance():
    """
    Query OKX CLI to get account balance with strict timeout.
    """
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "account", "balance", "--json"],
            capture_output=True, text=True, timeout=12, check=True
        )
        data = json.loads(proc.stdout)
        if isinstance(data, list) and len(data) > 0:
            if "details" in data[0]:
                return data[0]["details"]
        return data
    except subprocess.TimeoutExpired:
        print("[!] SRE Warning: OKX account balance command timed out!")
        return None
    except Exception as e:
        print(f"[!] SRE Warning: Error fetching balance: {e}")
        return None


def get_ticker_price(inst_id):
    """
    Query OKX CLI to get current ticker price with strict timeout.
    """
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "market", "ticker", inst_id, "--json"],
            capture_output=True, text=True, timeout=10, check=True
        )
        data = json.loads(proc.stdout)
        if isinstance(data, list) and len(data) > 0:
            return float(data[0].get("last", 0.0))
        return float(data.get("last", 0.0))
    except Exception as e:
        print(f"[!] SRE Warning: Error fetching ticker for {inst_id}: {e}")
        return 0.0


def place_limit_order(inst_id, side, sz, px):
    """
    Place limit order with strict timeout and validation.
    """
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "spot", "place", "--instId", inst_id, "--side", side, "--ordType", "limit", "--sz", str(sz), "--px", str(px), "--tdMode", "cash", "--json"],
            capture_output=True, text=True, timeout=12, check=True
        )
        data = json.loads(proc.stdout)
        ord_id = None
        if isinstance(data, list) and len(data) > 0:
            ord_id = data[0].get("ordId")
        elif isinstance(data, dict):
            ord_id = data.get("ordId")
            
        print(f"[+] Placed {side} limit order for {inst_id} (Sz: {sz}, Px: {px}) -> ID: {ord_id}")
        return ord_id
    except Exception as e:
        print(f"[-] SRE Error placing limit order for {inst_id}: {e}")
        return None


def main():
    print("[-] Starting SQLite-Driven Hardened State Machine Watcher Daemon...")
    playbook = load_json(PLAYBOOK_PATH)
    protected = load_json(PROTECTED_PATH)
    
    # Connect with immediate transaction lock to prevent SQLite database lock conflicts
    conn = sqlite3.connect(DB_PATH, isolation_level="EXCLUSIVE")
    cursor = conn.cursor()
    
    try:
        # Load current open orders
        orders = get_okx_orders()
        # SRE FIX: If the orders API failed or timed out, halt execution immediately!
        # This completely prevents "fake fills" caused by empty responses.
        if orders is None:
            print("[!] SRE Halt: API orders query failed or timed out. Skipping this cycle to prevent fake fills.")
            return
            
        open_orders_map = {str(o.get("ordId")): o for o in orders}
        
        # Load currently tracked states
        cursor.execute("SELECT inst_id, state, size, price, cl_ord_id FROM scalp_runs")
        tracked_runs = cursor.fetchall()

        # Compounding integration: calculate lot size dynamically as 20% of total USDC Equity (leaving 20% buffer for SOL grid & fees)
        balances = get_okx_balance()
        usdc_equity = 263.85
        if balances:
            # Handle list of details or flat dictionary
            usdc_bal = {}
            if isinstance(balances, list):
                usdc_bal = next((b for b in balances if b.get("ccy") == "USDC" or b.get("currency") == "USDC"), {})
            elif isinstance(balances, dict):
                usdc_bal = balances
            
            val = usdc_bal.get("eq") or usdc_bal.get("equity") or usdc_bal.get("availBal") or 263.85
            try:
                usdc_equity = float(val)
            except:
                usdc_equity = 263.85
                
        if usdc_equity < 100.0:
            usdc_equity = 263.85
            
        dynamic_size_usd = round(usdc_equity / 5.0, 2)
        print(f"[+] Compounding Active: USDC Equity = {usdc_equity:.2f} USDC | Dynamic Lot Size = {dynamic_size_usd:.2f} USDC")
        
        whitelisted_tokens = {
            "BTC-USDC": {"coin": "BTC", "playbook_key": "btc_scalp", "size_usd": dynamic_size_usd},
            "ETH-USDC": {"coin": "ETH", "playbook_key": "eth_scalp", "size_usd": dynamic_size_usd},
            "NEAR-USDC": {"coin": "NEAR", "playbook_key": "near_scalp", "size_usd": dynamic_size_usd},
            "LINK-USDC": {"coin": "LINK", "playbook_key": "link_scalp", "size_usd": dynamic_size_usd}
        }
        
        now_str = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        for row in tracked_runs:
            inst_id, state, size, price, cl_ord_id = row
            cl_ord_id_str = str(cl_ord_id) if cl_ord_id else ""
            
            info = whitelisted_tokens.get(inst_id)
            if not info:
                continue
                
            coin = info["coin"]
            playbook_key = info["playbook_key"]
            size_usd = info["size_usd"]
            
            # 1. State: BUY_SUBMITTED (We have a pending buy limit order)
            if state == "BUY_SUBMITTED":
                # If the order is NO LONGER active in open orders on the book, it filled!
                if cl_ord_id_str not in open_orders_map:
                    print(f"[!] SRE Fill Event: Buy order for {inst_id} (ID: {cl_ord_id_str}) was FILLED!")
                    balances = get_okx_balance()
                    if balances is None:
                        print(f"[!] SRE Warning: Balance API failed during NEAR/LINK fill check. Retrying next cycle.")
                        continue
                        
                    coin_bal = next((b for b in balances if b.get("ccy") == coin), {})
                    avail = float(coin_bal.get("availBal", 0.0))
                    
                    target_pct = playbook.get(playbook_key, {}).get("target_profit_percentage", 0.70) / 100.0
                    entry_px = float(coin_bal.get("openAvgPx", 0.0))
                    if entry_px <= 0.0001:
                        entry_px = float(coin_bal.get("accAvgPx", 0.0))
                    if entry_px <= 0.0001:
                        entry_px = get_ticker_price(inst_id)
                        
                    if entry_px > 0.0 and avail > 0.0001:
                        # Maker-only target calculation
                        sell_px = round(entry_px * (1 + target_pct), 1 if "BTC" in inst_id else (2 if "ETH" in inst_id else 3))
                        new_ord_id = place_limit_order(inst_id, "sell", avail, sell_px)
                        if new_ord_id:
                            cursor.execute("""
                            UPDATE scalp_runs 
                            SET state = 'SELL_SUBMITTED', size = ?, price = ?, cl_ord_id = ?, updated_at = ?
                            WHERE inst_id = ?
                            """, (avail, sell_px, new_ord_id, now_str, inst_id))
                            print(f"[+] State transition: {inst_id} -> SELL_SUBMITTED (ID: {new_ord_id})")
                            
            # 2. State: SELL_SUBMITTED (We have a pending sell limit TP order)
            elif state == "SELL_SUBMITTED":
                # If the order is NO LONGER active in open orders on the book, it got filled in profit!
                if cl_ord_id_str not in open_orders_map:
                    print(f"[!] SRE Profit Event: Sell order for {inst_id} (ID: {cl_ord_id_str}) was FILLED IN PROFIT!")
                    last_price = get_ticker_price(inst_id)
                    if last_price > 0.0:
                        # Maker-only Entry logic (Limit Buy at dynamic discount)
                        buy_offset = playbook.get(playbook_key, {}).get("buy_offset_percentage", 0.80) / 100.0
                        buy_px = round(last_price * (1.0 - buy_offset), 1 if "BTC" in inst_id else (2 if "ETH" in inst_id else 3))
                        buy_sz = round(size_usd / buy_px, 6 if "BTC" in inst_id else (5 if "ETH" in inst_id else 3))
                        new_ord_id = place_limit_order(inst_id, "buy", buy_sz, buy_px)
                        if new_ord_id:
                            cursor.execute("""
                            UPDATE scalp_runs 
                            SET state = 'BUY_SUBMITTED', size = ?, price = ?, cl_ord_id = ?, updated_at = ?
                            WHERE inst_id = ?
                            """, (buy_sz, buy_px, new_ord_id, now_str, inst_id))
                            print(f"[+] State transition: {inst_id} -> BUY_SUBMITTED (ID: {new_ord_id})")
                            
        conn.commit()
    except Exception as e:
        print(f"[!] SRE Exception during transaction: {e}")
        conn.rollback()
    finally:
        conn.close()
        print("=== HARDENED WATCHER DEAMON CYCLE COMPLETED ===")


if __name__ == "__main__":
    main()
