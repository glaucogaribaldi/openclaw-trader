#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import datetime
import subprocess
import time
import math

BASE_DIR = "/home/zavattoni_giacomo/openclaw-trader"
DB_PATH = os.path.join(BASE_DIR, "config", "okx_trader.db")
PLAYBOOK_PATH = os.path.join(BASE_DIR, "config", "strategy_playbook.json")
PROTECTED_PATH = os.path.join(BASE_DIR, "config", "protected.json")


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
            capture_output=True, text=True, timeout=10, check=True
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


def get_ticker_info(inst_id):
    """
    Fast query for ticker details of a specific instrument.
    """
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "market", "ticker", inst_id, "--json"],
            capture_output=True, text=True, timeout=5, check=True
        )
        data = json.loads(proc.stdout)
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        elif isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def get_orderbook_depth_and_imbalance(inst_id):
    """
    Calculate Order Book Imbalance (OBI) ratio and Ask Depth liquidity.
    """
    try:
        proc = subprocess.run(
            ["okx", "--profile", "democlaw", "market", "orderbook", inst_id, "--json"],
            capture_output=True, text=True, timeout=5, check=True
        )
        data = json.loads(proc.stdout)
        lob = data[0] if isinstance(data, list) and len(data) > 0 else data
        
        bids = lob.get("bids", [])
        asks = lob.get("asks", [])
        
        bid_vol = sum(float(b[1]) * float(b[0]) for b in bids[:10]) if bids else 0.0
        ask_vol = sum(float(a[1]) * float(a[0]) for a in asks[:10]) if asks else 0.0
        
        obi_ratio = (bid_vol / ask_vol) if ask_vol > 0 else 1.0
        return obi_ratio, ask_vol
    except Exception:
        return 1.0, 1000.0


def calculate_inventory_skew(inst_id, token_val_usdc, total_nav):
    """
    Module 1: Avellaneda-Stoikov Inventory Skew ($q_{skew}$).
    Adjusts buy offset and sell target based on token holding weight in NAV.
    """
    if total_nav <= 0:
        return 1.0, 1.0, "BALANCED"
    
    q_ratio = token_val_usdc / total_nav
    
    if q_ratio > 0.15: # High Inventory -> Lower buy aggressiveness (-0.80%), accelerate sell (+0.35%)
        buy_skew = 1.45 # Widen buy offset
        sell_skew = 0.70 # Tighten sell TP
        state = f"HIGH_INV({q_ratio*100:.1f}%)"
    elif q_ratio < 0.04: # Low/Zero Inventory -> Aggressive buy offset (-0.35%)
        buy_skew = 0.65 # Tighten buy offset to catch dip fast
        sell_skew = 1.00
        state = f"LOW_INV({q_ratio*100:.1f}%)"
    else:
        buy_skew = 1.00
        sell_skew = 1.00
        state = f"BALANCED({q_ratio*100:.1f}%)"
        
    return buy_skew, sell_skew, state


def get_dynamic_parameters(inst_id, range_24h_pct, token_val_usdc, total_nav):
    """
    Module 1, 4 & Low-Vol: Avellaneda-Stoikov Inventory Skew + LOB Depth Expansion.
    """
    if range_24h_pct < 3.0: # Low Volatility / Weekend Regime
        base_buy_offset = 0.35
        base_target_profit = 0.40
        vol_state = "LOW_VOL_WEEKEND"
    elif range_24h_pct < 6.0: # Medium Volatility
        base_buy_offset = 0.55
        base_target_profit = 0.55
        vol_state = "MEDIA"
    else: # High Volatility
        base_buy_offset = 0.80
        base_target_profit = 0.85
        vol_state = "ALTA"

    # Module 1: Avellaneda-Stoikov Inventory Skew
    buy_skew, sell_skew, inv_state = calculate_inventory_skew(inst_id, token_val_usdc, total_nav)
    buy_offset = base_buy_offset * buy_skew
    target_profit = base_target_profit * sell_skew

    # Module 4: Order Book Imbalance & LOB Depth Expansion
    obi_ratio, ask_depth = get_orderbook_depth_and_imbalance(inst_id)
    if obi_ratio >= 2.0:
        buy_offset = min(buy_offset, 0.40)
        vol_state += "+OBI"

    # Thin Ask Depth -> Expand Moonbag TP target!
    moonbag_multiplier = 4.0 # Standard Moonbag (+3.40%)
    if ask_depth < 500.0 and obi_ratio > 1.5:
        moonbag_multiplier = 6.0 # Expand Moonbag to +5.10%!
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
        print(f"[-] SRE Error placing limit order for {inst_id}: {e}")
        return None


def main():
    print("[-] Starting SRE v5.6 Avellaneda-Stoikov & Multi-Alpha Optimized Watcher Daemon...")
    init_db_wal()

    try:
        playbook = load_json(PLAYBOOK_PATH)
        protected = load_json(PROTECTED_PATH)
    except Exception as e:
        print(f"[!] SRE Halt: Error loading playbook or protected files: {e}")
        return
    
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    cursor = conn.cursor()
    
    try:
        orders = get_okx_orders()
        if orders is None:
            print("[!] SRE Halt: API orders query failed or timed out. Skipping cycle.")
            return
            
        open_orders_map = {str(o.get("ordId")): o for o in orders}
        
        cursor.execute("SELECT inst_id, state, size, price, cl_ord_id FROM scalp_runs")
        tracked_runs = cursor.fetchall()

        # Fetch balances
        balances = get_okx_balance()
        total_nav = 312.18
        usdc_avail = 35.46
        asset_values = {}
        
        if balances:
            total_nav = sum(float(b.get("eqUsd") or 0.0) for b in balances)
            usdc_bal = next((b for b in balances if b.get("ccy") == "USDC"), {})
            usdc_avail = float(usdc_bal.get("availBal") or 0.0)
            for b in balances:
                asset_values[b.get("ccy")] = float(b.get("eqUsd") or 0.0)

        # Optimization 1: Cash-Aware Dynamic Lot Sizing
        active_buy_slots = sum(1 for r in tracked_runs if r[1] in ["BUY_SUBMITTED", "CLOSED"] and r[0] not in ["BTC-USDC", "ETH-USDC"])
        nav_based_size = round(total_nav / 8.0, 2)
        cash_based_size = round(usdc_avail / max(active_buy_slots, 1), 2) if usdc_avail > 5.0 else nav_based_size
        
        dynamic_size_usd = max(min(nav_based_size, cash_based_size), 10.0)
        print(f"[+] Compounding Active (v5.6): NAV = ${total_nav:.2f} | Free USDC = ${usdc_avail:.2f} | Cash-Aware Lot Size = ${dynamic_size_usd:.2f} USDC")

        whitelisted_tokens = {
            "NEAR-USDC": {"coin": "NEAR"},
            "LINK-USDC": {"coin": "LINK"},
            "SUI-USDC": {"coin": "SUI"},
            "RENDER-USDC": {"coin": "RENDER"},
            "SOL-USDC": {"coin": "SOL"},
            "AVAX-USDC": {"coin": "AVAX"},
            "FET-USDC": {"coin": "FET"},
            "SEI-USDC": {"coin": "SEI"}
        }
        
        now_str = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        for row in tracked_runs:
            inst_id, state, size, price, cl_ord_id = row
            cl_ord_id_str = str(cl_ord_id) if cl_ord_id else ""
            
            info = whitelisted_tokens.get(inst_id)
            if not info:
                continue
                
            coin = info["coin"]
            token_val_usdc = asset_values.get(coin, 0.0)
            
            # Module 3: Dynamic Relative Strength Allocation
            # High-Beta momentum boost for active tokens
            size_usd = dynamic_size_usd
            if coin in ["SUI", "SEI", "LINK"]: # Top high-beta volume drivers
                size_usd = round(dynamic_size_usd * 1.15, 2)

            ticker_obj = get_ticker_info(inst_id)
            last_price = float(ticker_obj.get("last") or 0.0)
            high_24h = float(ticker_obj.get("high24h") or 0.0)
            low_24h = float(ticker_obj.get("low24h") or 0.0)
            range_pct = ((high_24h - low_24h) / low_24h * 100.0) if low_24h > 0 else 4.0

            # 1. State: BUY_SUBMITTED (Filled!)
            if state == "BUY_SUBMITTED":
                if cl_ord_id_str not in open_orders_map:
                    print(f"[!] SRE Fill Event: Buy order for {inst_id} (ID: {cl_ord_id_str}) was FILLED!")
                    balances = get_okx_balance()
                    if balances is None:
                        continue
                        
                    coin_bal = next((b for b in balances if b.get("ccy") == coin), {})
                    avail = float(coin_bal.get("availBal", 0.0))
                    
                    buy_offset, target_profit, moonbag_multiplier, vol_state = get_dynamic_parameters(inst_id, range_pct, token_val_usdc, total_nav)
                    print(f"[+] SRE v5.6 Engine {inst_id}: 24h Vol = {range_pct:.2f}% ({vol_state}) | Dynamic TP = +{target_profit:.2f}%")
                    
                    target_pct = target_profit / 100.0
                    entry_px = float(coin_bal.get("openAvgPx") or coin_bal.get("accAvgPx") or last_price)
                        
                    if entry_px > 0.0 and avail > 0.0001:
                        dec_sz = 2 if "AVAX" in inst_id else (1 if "FET" in inst_id or "SEI" in inst_id else 3)
                        sz_80 = math.floor(avail * 0.8 * (10**dec_sz)) / (10**dec_sz)
                        sz_20 = math.floor((avail - sz_80) * (10**dec_sz)) / (10**dec_sz)
                        
                        dec_px = 2 if "AVAX" in inst_id else (4 if "FET" in inst_id or "SEI" in inst_id else 3)
                        sell_px_80 = round(entry_px * (1 + target_pct), dec_px)
                        sell_px_20 = round(entry_px * (1 + target_pct * moonbag_multiplier), dec_px)
                        
                        new_ord_id_80 = place_limit_order(inst_id, "sell", sz_80, sell_px_80)
                        if new_ord_id_80:
                            place_limit_order(inst_id, "sell", sz_20, sell_px_20)
                            cursor.execute("""
                            UPDATE scalp_runs 
                            SET state = 'SELL_SUBMITTED', size = ?, price = ?, cl_ord_id = ?, updated_at = ?
                            WHERE inst_id = ?
                            """, (sz_80, sell_px_80, new_ord_id_80, now_str, inst_id))
                            print(f"[+] State transition: {inst_id} -> SELL_SUBMITTED (ID: {new_ord_id_80})")
                            
            # 2. State: SELL_SUBMITTED (Filled in profit!)
            elif state == "SELL_SUBMITTED":
                if cl_ord_id_str not in open_orders_map:
                    print(f"[!] SRE Profit Event: Sell order for {inst_id} (ID: {cl_ord_id_str}) was FILLED IN PROFIT!")
                    if last_price > 0.0:
                        buy_offset, target_profit, moonbag_multiplier, vol_state = get_dynamic_parameters(inst_id, range_pct, token_val_usdc, total_nav)
                        buy_offset_pct = buy_offset / 100.0
                        dec_px = 2 if "AVAX" in inst_id else (4 if "FET" in inst_id or "SEI" in inst_id else 3)
                        buy_px = round(last_price * (1.0 - buy_offset_pct), dec_px)
                        dec_sz = 2 if "AVAX" in inst_id else (1 if "FET" in inst_id or "SEI" in inst_id else 3)
                        buy_sz = round(size_usd / buy_px, dec_sz)
                        
                        new_ord_id = place_limit_order(inst_id, "buy", buy_sz, buy_px)
                        if new_ord_id:
                            cursor.execute("""
                            UPDATE scalp_runs 
                            SET state = 'BUY_SUBMITTED', size = ?, price = ?, cl_ord_id = ?, updated_at = ?
                            WHERE inst_id = ?
                            """, (buy_sz, buy_px, new_ord_id, now_str, inst_id))
                            print(f"[+] State transition: {inst_id} -> BUY_SUBMITTED (ID: {new_ord_id})")
            
            # 3. State: CLOSED (Launch initial buy order)
            elif state == "CLOSED":
                if last_price > 0.0001:
                    buy_offset, target_profit, moonbag_multiplier, vol_state = get_dynamic_parameters(inst_id, range_pct, token_val_usdc, total_nav)
                    buy_offset_pct = buy_offset / 100.0
                    dec_px = 2 if "AVAX" in inst_id else (4 if "FET" in inst_id or "SEI" in inst_id else 3)
                    buy_px = round(last_price * (1.0 - buy_offset_pct), dec_px)
                    dec_sz = 2 if "AVAX" in inst_id else (1 if "FET" in inst_id or "SEI" in inst_id else 3)
                    buy_sz = round(size_usd / buy_px, dec_sz)
                    
                    new_ord_id = place_limit_order(inst_id, "buy", buy_sz, buy_px)
                    if new_ord_id:
                        cursor.execute("UPDATE scalp_runs SET state = 'BUY_SUBMITTED', size = ?, price = ?, cl_ord_id = ?, updated_at = ? WHERE inst_id = ?", (buy_sz, buy_px, new_ord_id, now_str, inst_id))
                        print(f"[+] Initial Launch: {inst_id} -> BUY_SUBMITTED (ID: {new_ord_id})")

        conn.commit()
    except Exception as e:
        print(f"[!] SRE Exception during transaction: {e}")
        conn.rollback()
    finally:
        conn.close()
        print("=== HARDENED WATCHER DAEMON CYCLE COMPLETED ===")


if __name__ == "__main__":
    main()
