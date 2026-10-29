#!/usr/bin/env python3
import os
import sys
import json
import time
import datetime
import subprocess

print("=== INIZIALIZZAZIONE LEHMAN BRODY: MOTORE DI SIMULAZIONE ===\n")

# Configuration paths
BASE_DIR = "C:\\Users\\zavat\\openclaw-trader"
PLAYBOOK_PATH = os.path.join(BASE_DIR, "config", "strategy_playbook.json")

def load_json(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def run_simulation_cycle():
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Esecuzione ciclo di simulazione e ottimizzazione dinamica...")
    
    # Ingesting configuration
    playbook = load_json(PLAYBOOK_PATH)
    btc_target = playbook.get("btc_scalp", {}).get("target_profit_percentage", 0.55)
    eth_target = playbook.get("eth_scalp", {}).get("target_profit_percentage", 0.70)
    near_target = playbook.get("near_scalp", {}).get("target_profit_percentage", 0.85)
    link_target = playbook.get("link_scalp", {}).get("target_profit_percentage", 0.65)
    
    # Query current tickers via OKX CLI on Aibox
    tokens = ["BTC-USDC", "ETH-USDC", "NEAR-USDC", "LINK-USDC", "SOL-USDC"]
    prices = {}
    
    print("\n[+] 1. Ingestione Prezzi di Mercato Real-Time (OKX Spot):")
    for token in tokens:
        try:
            proc = subprocess.run(
                ["okx", "market", "ticker", token, "--json"],
                capture_output=True, text=True, check=True
            )
            data = json.loads(proc.stdout)
            prices[token] = float(data[0].get("last")) if isinstance(data, list) else float(data.get("last"))
            print(f"    - {token}: ${prices[token]:,}")
        except Exception as e:
            prices[token] = 1.0 # fallback
            print(f"    - [!] Errore lettura {token}: {e}")
            
    print("\n[+] 2. Simulazione delle Operazioni di Scalping (Paper Trading):")
    # Simulate a buy entry now, and calculate the sell target price
    print(f"    - [BTC] Entry: ${prices['BTC-USDC']:,} | Target (+{btc_target}%): ${prices['BTC-USDC'] * (1 + btc_target/100):,.2f}")
    print(f"    - [ETH] Entry: ${prices['ETH-USDC']:,} | Target (+{eth_target}%): ${prices['ETH-USDC'] * (1 + eth_target/100):,.2f}")
    print(f"    - [NEAR] Entry: ${prices['NEAR-USDC']:,} | Target (+{near_target}%): ${prices['NEAR-USDC'] * (1 + near_target/100):,.3f}")
    print(f"    - [LINK] Entry: ${prices['LINK-USDC']:,} | Target (+{link_target}%): ${prices['LINK-USDC'] * (1 + link_target/100):,.3f}")
    
    print("\n[+] 3. Simulazione del SOL Grid Bot:")
    lower = playbook.get("sol_grid", {}).get("lower_limit", 110.0)
    upper = playbook.get("sol_grid", {}).get("upper_limit", 135.0)
    print(f"    - Range Griglia: ${lower} - ${upper}")
    print(f"    - Prezzo Attuale SOL: ${prices['SOL-USDC']:,}")
    if prices['SOL-USDC'] < lower or prices['SOL-USDC'] > upper:
        print("    - [⚠️] ATTENZIONE: Il prezzo di SOL è FUORI dal range della griglia! Il Retro-Agent ricollocherà la griglia al prossimo ciclo.")
    else:
        print("    - [✓] Prezzo SOL all'interno del range della griglia. Griglie operative attive.")
        
    print("\n=== SIMULAZIONE COMPLETATA CON SUCCESSO. LEHMAN BRODY OPERATIVO H24 ===")

if __name__ == "__main__":
    run_simulation_cycle()
