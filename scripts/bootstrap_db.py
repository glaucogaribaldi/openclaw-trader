#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import datetime
import subprocess

BASE_DIR = "/home/zava/openclaw-trader"
DB_PATH = os.path.join(BASE_DIR, "config", "okx_trader.db")


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def get_okx_orders():
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "spot", "orders", "--json"],
            capture_output=True, text=True, check=True
        )
        return json.loads(proc.stdout)
    except Exception as e:
        print(f"Error fetching orders: {e}")
        return []


def setup_database():
    print(f"[-] Initializing SQLite Database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create the scalp runs state table
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
    
    conn.commit()
    return conn


def main():
    # Ensure config directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = setup_database()
    cursor = conn.cursor()
    
    orders = get_okx_orders()
    now_str = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    whitelisted_tokens = ["BTC-USDC", "ETH-USDC", "NEAR-USDC", "LINK-USDC"]
    active_inst_ids = []
    
    print("[-] Bootstrapping live states from current OKX book...")
    for o in orders:
        inst_id = o.get("instId")
        if inst_id not in whitelisted_tokens:
            continue
            
        side = o.get("side")
        ord_id = o.get("ordId")
        size = float(o.get("size", 0.0))
        price = float(o.get("price", 0.0))
        
        # Deduce state from active order side
        state = "BUY_SUBMITTED" if side == "buy" else "SELL_SUBMITTED"
        
        cursor.execute("""
        INSERT OR REPLACE INTO scalp_runs (inst_id, state, size, price, cl_ord_id, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (inst_id, state, size, price, ord_id, now_str))
        
        active_inst_ids.append(inst_id)
        print(f"[+] Bootstrapped {inst_id} into state '{state}' (Size: {size}, Price: {price}, ID: {ord_id})")
        
    # For any whitelisted token that has no active open orders on the book, mark as CLOSED
    for inst_id in whitelisted_tokens:
        if inst_id not in active_inst_ids:
            cursor.execute("""
            INSERT OR IGNORE INTO scalp_runs (inst_id, state, size, price, cl_ord_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (inst_id, "CLOSED", 0.0, 0.0, None, now_str))
            print(f"[+] Bootstrapped {inst_id} into state 'CLOSED' (waiting for next trigger)")
            
    conn.commit()
    conn.close()
    print("=== DATABASE BOOTSTRAP COMPLETED ===")


if __name__ == "__main__":
    main()
