#!/usr/bin/env python3
import os
import sys
import json
import time
import subprocess

BASE_DIR = "/home/zava/openclaw-trader"
PLAYBOOK_PATH = os.path.join(BASE_DIR, "config", "strategy_playbook.json")
PROTECTED_PATH = os.path.join(BASE_DIR, "config", "protected.json")


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


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


def get_okx_balance():
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "account", "balance", "--json"],
            capture_output=True, text=True, check=True
        )
        data = json.loads(proc.stdout)
        if isinstance(data, list) and len(data) > 0:
            if "details" in data[0]:
                return data[0]["details"]
        return data
    except Exception as e:
        print(f"Error fetching balance: {e}")
        return []


def get_ticker_price(inst_id):
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "market", "ticker", inst_id, "--json"],
            capture_output=True, text=True, check=True
        )
        data = json.loads(proc.stdout)
        if isinstance(data, list) and len(data) > 0:
            return float(data[0].get("last", 0.0))
        return float(data.get("last", 0.0))
    except Exception as e:
        print(f"Error fetching ticker for {inst_id}: {e}")
        return 0.0


def place_limit_order(inst_id, side, sz, px):
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "spot", "place", "--instId", inst_id, "--side", side, "--ordType", "limit", "--sz", str(sz), "--px", str(px), "--tdMode", "cash", "--json"],
            capture_output=True, text=True, check=True
        )
        print(f"[+] Successfully placed {side} limit order for {inst_id} (Sz: {sz}, Px: {px})")
        return True
    except Exception as e:
        print(f"[-] Error placing limit order for {inst_id}: {e}")
        return False


def main():
    print("[-] Starting Capital Recycling Watcher Daemon...")
    playbook = load_json(PLAYBOOK_PATH)
    protected = load_json(PROTECTED_PATH)
    
    orders = get_okx_orders()
    balances = get_okx_balance()
    
    # Map assets to our whitelisted scalping tokens
    assets = {
        "BTC-USDC": {"coin": "BTC", "playbook_key": "btc_scalp", "size_usd": 50.0},
        "ETH-USDC": {"coin": "ETH", "playbook_key": "eth_scalp", "size_usd": 50.0},
        "NEAR-USDC": {"coin": "NEAR", "playbook_key": "near_scalp", "size_usd": 50.0},
        "LINK-USDC": {"coin": "LINK", "playbook_key": "link_scalp", "size_usd": 50.0}
    }
    
    # 1. Get available and frozen amounts
    open_orders_map = {o.get("instId"): o for o in orders}
    
    for inst_id, info in assets.items():
        coin = info["coin"]
        playbook_key = info["playbook_key"]
        size_usd = info["size_usd"]
        
        # Check balance with the correct JSON keys
        coin_bal = next((b for b in balances if b.get("ccy") == coin), {})
        avail = float(coin_bal.get("availBal", 0.0))
        frozen = float(coin_bal.get("frozenBal", 0.0))
        total = avail + frozen
        
        # Scenario A: We have NO open orders on the book, and we hold NO tokens.
        # This means either the Sell order got filled or we just started.
        # Action: Immediately place a Limit Buy at a discount to recycle the capital!
        if inst_id not in open_orders_map and total < 0.0001:
            print(f"[!] {inst_id} has no open orders and no balances. Placing Limit Buy...")
            last_price = get_ticker_price(inst_id)
            if last_price > 0.0:
                # Place Limit Buy at a -0.80% discount
                buy_px = round(last_price * 0.992, 1 if "BTC" in inst_id else (2 if "ETH" in inst_id else 3))
                buy_sz = round(size_usd / buy_px, 6 if "BTC" in inst_id else (5 if "ETH" in inst_id else 3))
                place_limit_order(inst_id, "buy", buy_sz, buy_px)
                
        # Scenario B: We hold tokens (available balance > 0) but we have NO Sell open order.
        # This means the Limit Buy got filled!
        # Action: Immediately place the corresponding Limit Sell TP order!
        elif inst_id not in open_orders_map and avail > 0.0001:
            print(f"[!] {inst_id} has available balance but no open sell order. Placing Limit Sell TP...")
            # Calculate target price based on playbook
            target_pct = playbook.get(playbook_key, {}).get("target_profit_percentage", 0.70) / 100.0
            # Since the Buy Limit order was filled, we want to place the Limit Sell at buy_price * (1 + target_pct).
            # To get our exact fill price (entry basis), we can read the 'openAvgPx' or 'accAvgPx' from coin_bal details!
            # On OKX live, b.get("openAvgPx") holds the exact average price of the current open spot position!
            entry_px = float(coin_bal.get("openAvgPx", 0.0))
            if entry_px <= 0.0001:
                entry_px = float(coin_bal.get("accAvgPx", 0.0))
            if entry_px <= 0.0001:
                # Fallback to current ticker price if cost basis is missing
                entry_px = get_ticker_price(inst_id)
                
            if entry_px > 0.0:
                sell_px = round(entry_px * (1 + target_pct), 1 if "BTC" in inst_id else (2 if "ETH" in inst_id else 3))
                place_limit_order(inst_id, "sell", avail, sell_px)


if __name__ == "__main__":
    main()
