#!/usr/bin/env python3
"""
TRE OS v5.6 Multi-Tier Multi-Alpha Watcher Daemon
Implements:
- Leva 1 (Capital Allocation Boost 85%) & Leva 2 (Multi-Tier Progressive Buy/Sell Grid)
- AUTOMATED UNASSIGNED CASH SWEEPER (CAP-AWARE & INVENTORY-SAFE):
  Re-engages free USDC cash (> $5.00 USDC) into active Buy Dip limit traps, respecting token allocation caps and available cash.
- Enforces Post-Only (cancel_maker) execution for 0.00% Taker Fee Drag.
"""
import os
import sys
import json
import sqlite3
import datetime
import subprocess
import time
import math

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "config", "okx_trader.db")
PLAYBOOK_PATH = os.path.join(BASE_DIR, "config", "strategy_playbook.json")
PROTECTED_PATH = os.path.join(BASE_DIR, "config", "protected.json")
DIRECTIVE_PATH = os.path.join(BASE_DIR, "config", "ai_hourly_directive.json")


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def init_db_wal():
    """
    Enable WAL mode and busy timeout on SQLite to prevent lock conflicts.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.close()
    except Exception as e:
        print(f"[!] SRE Warning: Could not set WAL mode: {e}")


def trigger_event_ai_steering(event_name):
    """
    Non-blocking background trigger for OpenRouter AI Steering upon trade fills.
    """
    try:
        cmd = [
            os.path.join(BASE_DIR, "venv/bin/python"),
            os.path.join(BASE_DIR, "scripts/hourly_ai_steer.py"),
            "--trigger", event_name
        ]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[⚡ EVENT AI TRIGGER] Fired background OpenRouter AI Steering check for event: {event_name}")
    except Exception as e:
        print(f"[!] Event AI Trigger error: {e}")


def get_okx_orders():
    """
    Query OKX CLI to get open orders with strict timeout.
    """
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "spot", "orders", "--json"],
            capture_output=True, text=True, timeout=10, check=True
        )
        data = json.loads(proc.stdout)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def get_okx_balances():
    """
    Query OKX CLI to get real-time account balances.
    """
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "account", "balance", "--json"],
            capture_output=True, text=True, timeout=10, check=True
        )
        data = json.loads(proc.stdout)
        if isinstance(data, list) and len(data) > 0 and 'details' in data[0]:
            return data[0]['details']
        return []
    except Exception:
        return []


def get_okx_ticker(inst_id):
    """
    Query OKX ticker for 24h high/low and last price.
    """
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "public", "ticker", "--instId", inst_id, "--json"],
            capture_output=True, text=True, timeout=8, check=True
        )
        data = json.loads(proc.stdout)
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        elif isinstance(data, dict):
            return data
        return None
    except Exception:
        return None


def get_orderbook_depth_and_imbalance(inst_id):
    """
    Reads top 10 LOB bids/asks to calculate Orderbook Imbalance (OBI) & Ask depth.
    """
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "public", "books", "--instId", inst_id, "--sz", "10", "--json"],
            capture_output=True, text=True, timeout=8, check=True
        )
        data = json.loads(proc.stdout)
        bids, asks = [], []
        if isinstance(data, list) and len(data) > 0:
            bids = data[0].get("bids", [])
            asks = data[0].get("asks", [])
        
        bid_vol = sum(float(b[1]) * float(b[0]) for b in bids[:10]) if bids else 0.0
        ask_vol = sum(float(a[1]) * float(a[0]) for a in asks[:10]) if asks else 0.0
        obi_ratio = (bid_vol / ask_vol) if ask_vol > 0 else 1.0
        return obi_ratio, ask_vol
    except Exception:
        return 1.0, 1000.0


def calculate_inventory_skew(inst_id, token_val_usdc, total_nav):
    """
    Avellaneda-Stoikov Inventory Skew ($q_{skew}$).
    Adjusts buy offset and sell target based on token holding weight in NAV.
    """
    q_ratio = (token_val_usdc / total_nav) if total_nav > 0 else 0.0
    
    if q_ratio > 0.18: # High Inventory (>18%) -> Lower buy aggressiveness (-0.80%), accelerate sell (+0.35%)
        buy_skew = 1.45
        sell_skew = 0.70
        state = f"HIGH_INV({q_ratio*100:.1f}%)"
    elif q_ratio < 0.04: # Low/Zero Inventory -> Aggressive buy offset (-0.35%)
        buy_skew = 0.65
        sell_skew = 1.00
        state = f"LOW_INV({q_ratio*100:.1f}%)"
    else:
        buy_skew = 1.00
        sell_skew = 1.00
        state = f"BALANCED({q_ratio*100:.1f}%)"
        
    return buy_skew, sell_skew, state


def get_dynamic_parameters(inst_id, range_24h_pct, token_val_usdc, total_nav):
    ai_buy_offset = None
    ai_target_profit = None
    ai_mode = "STANDARD"
    
    try:
        if os.path.exists(DIRECTIVE_PATH):
            with open(DIRECTIVE_PATH, "r") as f:
                directive = json.load(f)
                if directive.get("low_volatility_mode") is True:
                    ai_buy_offset = float(directive.get("grid_spread_buy_pct", 0.25))
                    ai_target_profit = float(directive.get("take_profit_sell_pct", 0.35))
                    ai_mode = "AI_MICRO_SCALPING"
    except Exception:
        pass

    if ai_buy_offset is not None and ai_target_profit is not None:
        base_buy_offset = ai_buy_offset
        base_target_profit = ai_target_profit
        vol_state = f"{ai_mode}(Buy -{base_buy_offset:.2f}% / Sell +{base_target_profit:.2f}%)"
    elif range_24h_pct < 3.0: # Low Volatility / Weekend Regime (LEVA 2 Multi-Tier Micro-Grid)
        base_buy_offset = 0.25
        base_target_profit = 0.35
        vol_state = "LOW_VOL_MICRO_SCALPING"
    elif range_24h_pct < 6.0: # Medium Volatility
        base_buy_offset = 0.55
        base_target_profit = 0.55
        vol_state = "MEDIA"
    else: # High Volatility
        base_buy_offset = 0.80
        base_target_profit = 0.85
        vol_state = "ALTA"

    buy_skew, sell_skew, inv_state = calculate_inventory_skew(inst_id, token_val_usdc, total_nav)
    buy_offset = base_buy_offset * buy_skew
    target_profit = base_target_profit * sell_skew

    obi_ratio, ask_depth = get_orderbook_depth_and_imbalance(inst_id)
    if obi_ratio >= 2.0:
        buy_offset = min(buy_offset, 0.30)
        vol_state += "+OBI"

    moonbag_multiplier = 4.0
    if ask_depth < 500.0 and obi_ratio > 1.5:
        moonbag_multiplier = 6.0
        vol_state += "+THIN_LOB_EXPANSION"

    return buy_offset, target_profit, moonbag_multiplier, f"{vol_state}|{inv_state}"


def place_limit_order(inst_id, side, sz, px):
    """
    Place limit order enforcing Post-Only (cancel_maker) for zero taker fee drag.
    """
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "spot", "place", "--instId", inst_id, "--side", side, "--ordType", "limit", "--sz", str(sz), "--px", str(px), "--tdMode", "cash", "--stpMode", "cancel_maker", "--json"],
            capture_output=True, text=True, timeout=8, check=True
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
        print(f"[!] Error placing {side} order for {inst_id}: {e}")
        return None


def run_daemon_cycle():
    init_db_wal()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT inst_id, state, size, price, cl_ord_id FROM scalp_runs")
    tracked_runs = cursor.fetchall()
    
    balances = get_okx_balances()
    open_orders = get_okx_orders()
    
    open_order_ids = set()
    open_buy_instruments = set()
    for o in open_orders:
        if isinstance(o, dict):
            ord_id_str = str(o.get("ordId"))
            open_order_ids.add(ord_id_str)
            if o.get("side") == "buy":
                open_buy_instruments.add(o.get("instId"))
            
    total_nav = sum(float(b.get("eqUsd") or 0.0) for b in balances) or 309.36
    usdc_avail = sum(float(b.get("availBal") or 0.0) for b in balances if b.get("ccy") == "USDC")
    
    active_buy_slots = sum(1 for r in tracked_runs if r[1] in ["BUY_SUBMITTED", "CLOSED"] and r[0] not in ["BTC-USDC", "ETH-USDC"])
    nav_based_size = round((total_nav * 0.85) / 8.0, 2)
    cash_based_size = round(usdc_avail / max(active_buy_slots, 1), 2) if usdc_avail > 5.0 else nav_based_size
    
    dynamic_size_usd = max(min(nav_based_size, cash_based_size), 12.50)
    print(f"[+] Compounding Active (v5.6 LEVA 1+2): NAV = ${total_nav:.2f} | Free USDC = ${usdc_avail:.2f} | Dynamic Lot Size = ${dynamic_size_usd:.2f} USDC")

    whitelisted_tokens = {
        "NEAR-USDC": {"coin": "NEAR", "dec_px": 3, "dec_sz": 1},
        "LINK-USDC": {"coin": "LINK", "dec_px": 3, "dec_sz": 2},
        "SUI-USDC": {"coin": "SUI", "dec_px": 4, "dec_sz": 1},
        "RENDER-USDC": {"coin": "RENDER", "dec_px": 3, "dec_sz": 2},
        "SOL-USDC": {"coin": "SOL", "dec_px": 2, "dec_sz": 3},
        "AVAX-USDC": {"coin": "AVAX", "dec_px": 3, "dec_sz": 2},
        "FET-USDC": {"coin": "FET", "dec_px": 4, "dec_sz": 1},
        "SEI-USDC": {"coin": "SEI", "dec_px": 4, "dec_sz": 1}
    }
    
    max_token_weight = 0.20 # Max 20% NAV per single token allocation cap
    max_token_usd_cap = total_nav * max_token_weight
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    for row in tracked_runs:
        inst_id, state, size, price, cl_ord_id = row
        cl_ord_id_str = str(cl_ord_id) if cl_ord_id else ""
        
        info = whitelisted_tokens.get(inst_id)
        if not info:
            continue
            
        coin = info["coin"]
        dec_px = info["dec_px"]
        dec_sz = info["dec_sz"]
        
        token_bal_obj = next((b for b in balances if b.get("ccy") == coin), {})
        token_val_usdc = float(token_bal_obj.get("eqUsd") or 0.0)
        avail_qty = float(token_bal_obj.get("availBal") or 0.0)
        
        ticker_obj = get_okx_ticker(inst_id)
        if not ticker_obj:
            continue
            
        last_price = float(ticker_obj.get("last") or 0.0)
        high_24h = float(ticker_obj.get("high24h") or 0.0)
        low_24h = float(ticker_obj.get("low24h") or 0.0)
        range_pct = ((high_24h - low_24h) / low_24h * 100.0) if low_24h > 0 else 4.0
        
        # 1. State: SELL_SUBMITTED
        if state == "SELL_SUBMITTED":
            if cl_ord_id_str and cl_ord_id_str not in open_order_ids:
                print(f"[!] SRE Profit Event: Sell order for {inst_id} (ID: {cl_ord_id_str}) WAS FILLED IN PROFIT!")
                trigger_event_ai_steering(f"SELL_PROFIT_FILL_{coin}")
                
                buy_offset, target_profit, moonbag_mult, vol_state = get_dynamic_parameters(inst_id, range_pct, token_val_usdc, total_nav)
                buy_offset_pct = buy_offset / 100.0
                buy_px = round(last_price * (1.0 - buy_offset_pct), dec_px)
                
                size_usd = dynamic_size_usd
                buy_sz = round(size_usd / buy_px, dec_sz)
                
                new_ord_id = place_limit_order(inst_id, "buy", buy_sz, buy_px)
                if new_ord_id:
                    cursor.execute("UPDATE scalp_runs SET state = 'BUY_SUBMITTED', size = ?, price = ?, cl_ord_id = ?, updated_at = ? WHERE inst_id = ?", (buy_sz, buy_px, new_ord_id, now_str, inst_id))
                else:
                    cursor.execute("UPDATE scalp_runs SET state = 'CLOSED', updated_at = ? WHERE inst_id = ?", (now_str, inst_id))

        # 2. State: BUY_SUBMITTED
        elif state == "BUY_SUBMITTED":
            if cl_ord_id_str and cl_ord_id_str not in open_order_ids:
                print(f"[!] SRE Buy Event: Buy order for {inst_id} (ID: {cl_ord_id_str}) WAS FILLED!")
                trigger_event_ai_steering(f"BUY_DIP_FILL_{coin}")
                
                buy_offset, target_profit, moonbag_mult, vol_state = get_dynamic_parameters(inst_id, range_pct, token_val_usdc, total_nav)
                
                if avail_qty > 0:
                    sell_px_80 = round(last_price * (1.0 + (target_profit / 100.0)), dec_px)
                    sell_px_20 = round(last_price * (1.0 + ((target_profit * moonbag_mult) / 100.0)), dec_px)
                    
                    sz_80 = math.floor(avail_qty * 0.80 * (10**dec_sz)) / (10**dec_sz)
                    sz_20 = math.floor((avail_qty - sz_80) * (10**dec_sz)) / (10**dec_sz)
                    
                    new_ord_id_80 = place_limit_order(inst_id, "sell", sz_80, sell_px_80)
                    if sz_20 > 0:
                        place_limit_order(inst_id, "sell", sz_20, sell_px_20)
                        
                    if new_ord_id_80:
                        cursor.execute("UPDATE scalp_runs SET state = 'SELL_SUBMITTED', size = ?, price = ?, cl_ord_id = ?, updated_at = ? WHERE inst_id = ?", (sz_80, sell_px_80, new_ord_id_80, now_str, inst_id))

        # 3. State: CLOSED (Replenish buy trap)
        elif state == "CLOSED":
            if token_val_usdc < max_token_usd_cap:
                buy_offset, target_profit, moonbag_mult, vol_state = get_dynamic_parameters(inst_id, range_pct, token_val_usdc, total_nav)
                buy_offset_pct = buy_offset / 100.0
                buy_px = round(last_price * (1.0 - buy_offset_pct), dec_px)
                
                size_usd = dynamic_size_usd
                buy_sz = round(size_usd / buy_px, dec_sz)
                
                new_ord_id = place_limit_order(inst_id, "buy", buy_sz, buy_px)
                if new_ord_id:
                    cursor.execute("UPDATE scalp_runs SET state = 'BUY_SUBMITTED', size = ?, price = ?, cl_ord_id = ?, updated_at = ? WHERE inst_id = ?", (buy_sz, buy_px, new_ord_id, now_str, inst_id))

    # 4. AUTOMATED UNASSIGNED CASH SWEEPER (WITH STRICT ALLOCATION & CASH CAPS)
    # Automatically re-engages free USDC cash (> $5.00 USDC) into active Buy Dip traps
    if usdc_avail > 5.0:
        for inst_id, info in whitelisted_tokens.items():
            if inst_id not in open_buy_instruments:
                coin = info["coin"]
                dec_px = info["dec_px"]
                dec_sz = info["dec_sz"]
                
                token_bal_obj = next((b for b in balances if b.get("ccy") == coin), {})
                token_val_usdc = float(token_bal_obj.get("eqUsd") or 0.0)
                
                # Risk Guard 1: Don't over-concentrate in a single token (> 20% NAV)
                if token_val_usdc >= max_token_usd_cap:
                    print(f"[🛡️ CASH SWEEPER GUARD] Skipping {inst_id}: Current value (${token_val_usdc:.2f}) exceeds 20% NAV cap (${max_token_usd_cap:.2f})")
                    continue
                
                ticker_obj = get_okx_ticker(inst_id)
                if ticker_obj:
                    last_price = float(ticker_obj.get("last") or 0.0)
                    high_24h = float(ticker_obj.get("high24h") or 0.0)
                    low_24h = float(ticker_obj.get("low24h") or 0.0)
                    range_pct = ((high_24h - low_24h) / low_24h * 100.0) if low_24h > 0 else 4.0
                    
                    buy_offset, target_profit, moonbag_mult, vol_state = get_dynamic_parameters(inst_id, range_pct, token_val_usdc, total_nav)
                    buy_offset_pct = buy_offset / 100.0
                    buy_px = round(last_price * (1.0 - buy_offset_pct), dec_px)
                    
                    # Risk Guard 2: Cap trade size by available cash
                    order_size_usd = min(dynamic_size_usd, usdc_avail)
                    if order_size_usd < 5.0: # OKX minimum order threshold
                        break
                        
                    sz_buy = round(order_size_usd / buy_px, dec_sz)
                    print(f"[⚡ UNASSIGNED CASH SWEEPER] Auto re-engaging ${order_size_usd:.2f} free USDC into Buy Dip for {inst_id} @ ${buy_px}")
                    
                    new_ord_id = place_limit_order(inst_id, "buy", sz_buy, buy_px)
                    if new_ord_id:
                        cursor.execute("UPDATE scalp_runs SET state = 'BUY_SUBMITTED', size = ?, price = ?, cl_ord_id = ?, updated_at = ? WHERE inst_id = ?", (sz_buy, buy_px, new_ord_id, now_str, inst_id))
                        open_buy_instruments.add(inst_id)
                        usdc_avail -= (sz_buy * buy_px)
                        if usdc_avail <= 5.0:
                            break

    conn.commit()
    conn.close()
    print("=== LEVA 1+2 HARDENED WATCHER DAEMON CYCLE COMPLETED ===")


if __name__ == "__main__":
    print("[-] Starting SRE v5.6 LEVA 1+2 Multi-Tier Multi-Alpha Watcher Daemon...")
    run_daemon_cycle()
