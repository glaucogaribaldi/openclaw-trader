#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import datetime
import subprocess

BASE_DIR = "/Users/zava/.openclaw/workspace"
DB_PATH = os.path.join(BASE_DIR, "config", "hybrid_okx_trader.db")
PLAYBOOK_PATH = os.path.join(BASE_DIR, "config", "hybrid_strategy_playbook.json")


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def get_okx_orders():
    """
    Query OKX CLI to get open orders in DEMO mode.
    """
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "--demo", "spot", "orders", "--json"],
            capture_output=True, text=True, timeout=12, check=True
        )
        data = json.loads(proc.stdout)
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"[!] Hybrid Warning: Error fetching demo orders: {e}")
        return None


def get_okx_balance():
    """
    Query OKX CLI to get demo account balance.
    """
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "--demo", "account", "balance", "--json"],
            capture_output=True, text=True, timeout=12, check=True
        )
        data = json.loads(proc.stdout)
        if isinstance(data, list) and len(data) > 0:
            if "details" in data[0]:
                return data[0]["details"]
        return data
    except Exception as e:
        print(f"[!] Hybrid Warning: Error fetching demo balance: {e}")
        return None


def get_ticker_price(inst_id):
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "--demo", "market", "ticker", inst_id, "--json"],
            capture_output=True, text=True, timeout=10, check=True
        )
        data = json.loads(proc.stdout)
        if isinstance(data, list) and len(data) > 0:
            return float(data[0].get("last", 0.0))
        return float(data.get("last", 0.0))
    except Exception:
        return 0.0


def place_limit_order(inst_id, side, sz, px):
    try:
        proc = subprocess.run([
            "okx", "--profile", "democlaw", "--demo", "spot", "place",
            "--instId", inst_id, "--side", side, "--ordType", "limit",
            "--sz", str(sz), "--px", str(px), "--tdMode", "cash", "--json"
        ], capture_output=True, text=True, timeout=12, check=True)
        data = json.loads(proc.stdout)
        ord_id = None
        if isinstance(data, list) and len(data) > 0:
            ord_id = data[0].get("ordId")
        elif isinstance(data, dict):
            ord_id = data.get("ordId")
        return ord_id
    except Exception as e:
        print(f"[-] Hybrid Error placing limit order for {inst_id}: {e}")
        return None


def bootstrap_db():
    if not os.path.exists(DB_PATH):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scalp_runs (
            inst_id TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            size REAL NOT NULL,
            price REAL NOT NULL,
            cl_ord_id TEXT,
            updated_at TEXT NOT NULL
        )
        """)
        
        # Inizializziamo i 4 token in modalità BUY_SUBMITTED all'avvio in demo
        now_str = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        initial_tokens = ["BTC-USDC", "ETH-USDC", "NEAR-USDC", "LINK-USDC"]
        for t in initial_tokens:
            cursor.execute("""
            INSERT OR IGNORE INTO scalp_runs (inst_id, state, size, price, cl_ord_id, updated_at)
            VALUES (?, 'INIT', 0.0, 0.0, NULL, ?)
            """, (t, now_str))
        conn.commit()
        conn.close()
        print(f"[+] Bootstrappato database demo ibrido: {DB_PATH}")


def main():
    print("[-] Starting Hybrid Demo Watcher Daemon (CPU-Lightweight)...")
    bootstrap_db()
    
    if not os.path.exists(PLAYBOOK_PATH):
        print(f"[-] Errore: Playbook strategico {PLAYBOOK_PATH} non trovato. Esegui prima hybrid_retro_analyzer.py!")
        return
        
    playbook = load_json(PLAYBOOK_PATH)
    
    conn = sqlite3.connect(DB_PATH, isolation_level="EXCLUSIVE")
    cursor = conn.cursor()
    
    try:
        orders = get_okx_orders()
        if orders is None:
            print("[!] Hybrid Halt: API demo orders query failed. Skipping.")
            return
            
        open_orders_map = {str(o.get("ordId")): o for o in orders}
        
        cursor.execute("SELECT inst_id, state, size, price, cl_ord_id FROM scalp_runs")
        tracked_runs = cursor.fetchall()
        
        whitelisted_tokens = {
            "BTC-USDC": {"coin": "BTC", "playbook_key": "btc_scalp", "size_usd": 100.0}, # Usiamo $100 di capitale demo!
            "ETH-USDC": {"coin": "ETH", "playbook_key": "eth_scalp", "size_usd": 100.0},
            "NEAR-USDC": {"coin": "NEAR", "playbook_key": "near_scalp", "size_usd": 100.0},
            "LINK-USDC": {"coin": "LINK", "playbook_key": "link_scalp", "size_usd": 100.0}
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
            
            # State: INIT -> Place initial BUY limit order
            if state == "INIT":
                last_price = get_ticker_price(inst_id)
                if last_price > 0.0:
                    buy_offset = playbook.get(playbook_key, {}).get("buy_offset_percentage", 0.50) / 100.0
                    buy_px = round(last_price * (1.0 - buy_offset), 1 if "BTC" in inst_id else (2 if "ETH" in inst_id else 3))
                    buy_sz = round(size_usd / buy_px, 6 if "BTC" in inst_id else (5 if "ETH" in inst_id else 3))
                    
                    new_ord_id = place_limit_order(inst_id, "buy", buy_sz, buy_px)
                    if new_ord_id:
                        cursor.execute("""
                        UPDATE scalp_runs 
                        SET state = 'BUY_SUBMITTED', size = ?, price = ?, cl_ord_id = ?, updated_at = ?
                        WHERE inst_id = ?
                        """, (buy_sz, buy_px, new_ord_id, now_str, inst_id))
                        print(f"[+] Demo Init {inst_id} -> BUY_SUBMITTED (ID: {new_ord_id})")

            # State: BUY_SUBMITTED
            elif state == "BUY_SUBMITTED":
                if cl_ord_id_str not in open_orders_map:
                    print(f"[!] Demo Buy Filled: {inst_id} (ID: {cl_ord_id_str})")
                    balances = get_okx_balance()
                    if balances is None:
                        continue
                        
                    coin_bal = next((b for b in balances if b.get("ccy") == coin), {})
                    avail = float(coin_bal.get("availBal", 0.0))
                    
                    target_pct = playbook.get(playbook_key, {}).get("target_profit_percentage", 0.50) / 100.0
                    entry_px = float(coin_bal.get("openAvgPx", 0.0))
                    if entry_px <= 0.0001:
                        entry_px = get_ticker_price(inst_id)
                        
                    if entry_px > 0.0 and avail > 0.0001:
                        sell_px = round(entry_px * (1 + target_pct), 1 if "BTC" in inst_id else (2 if "ETH" in inst_id else 3))
                        new_ord_id = place_limit_order(inst_id, "sell", avail, sell_px)
                        if new_ord_id:
                            cursor.execute("""
                            UPDATE scalp_runs 
                            SET state = 'SELL_SUBMITTED', size = ?, price = ?, cl_ord_id = ?, updated_at = ?
                            WHERE inst_id = ?
                            """, (avail, sell_px, new_ord_id, now_str, inst_id))
                            print(f"[+] State transition demo: {inst_id} -> SELL_SUBMITTED (ID: {new_ord_id})")
                            
            # State: SELL_SUBMITTED
            elif state == "SELL_SUBMITTED":
                if cl_ord_id_str not in open_orders_map:
                    print(f"[!] Demo Sell Filled (Profit!): {inst_id} (ID: {cl_ord_id_str})")
                    last_price = get_ticker_price(inst_id)
                    if last_price > 0.0:
                        buy_offset = playbook.get(playbook_key, {}).get("buy_offset_percentage", 0.50) / 100.0
                        buy_px = round(last_price * (1.0 - buy_offset), 1 if "BTC" in inst_id else (2 if "ETH" in inst_id else 3))
                        buy_sz = round(size_usd / buy_px, 6 if "BTC" in inst_id else (5 if "ETH" in inst_id else 3))
                        new_ord_id = place_limit_order(inst_id, "buy", buy_sz, buy_px)
                        if new_ord_id:
                            cursor.execute("""
                            UPDATE scalp_runs 
                            SET state = 'BUY_SUBMITTED', size = ?, price = ?, cl_ord_id = ?, updated_at = ?
                            WHERE inst_id = ?
                            """, (buy_sz, buy_px, new_ord_id, now_str, inst_id))
                            print(f"[+] State transition demo: {inst_id} -> BUY_SUBMITTED (ID: {new_ord_id})")
                            
        conn.commit()
    except Exception as e:
        print(f"[!] Hybrid Error: {e}")
        conn.rollback()
    finally:
        conn.close()
        print("=== HYBRID DEMO WATCHER DEAMON CYCLE COMPLETED ===")


if __name__ == "__main__":
    main()
