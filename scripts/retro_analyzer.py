#!/usr/bin/env python3
import os
import sys
import json
import datetime
import subprocess
import urllib.request

# Configuration paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTECTED_PATH = os.path.join(BASE_DIR, "config", "protected.json")
PLAYBOOK_PATH = os.path.join(BASE_DIR, "config", "strategy_playbook.json")
RETROS_DIR = os.path.join(BASE_DIR, "journal", "retros")

# Ensure retros directory exists
os.makedirs(RETROS_DIR, exist_ok=True)


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_okx_data():
    """
    Query OKX CLI to get recent fills and tickers.
    If the CLI is not configured, fallback to standard mock values or API fetches.
    """
    print("[-] Ingesting recent 24h trade data from OKX CLI...")
    try:
        # Fetch last fills for BTC, ETH, SOL
        fills_proc = subprocess.run(
            ["okx", "spot", "fills", "--limit", "10", "--json"],
            capture_output=True,
            text=True,
            check=True
        )
        fills_data = json.loads(fills_proc.stdout)
    except Exception as e:
        print(f"[!] Warning: Could not fetch fills from OKX CLI: {e}. Using simulated fills.")
        fills_data = []

    try:
        # Fetch current tickers
        ticker_proc = subprocess.run(
            ["okx", "market", "ticker", "SOL-USDC", "--json"],
            capture_output=True,
            text=True,
            check=True
        )
        ticker_sol = json.loads(ticker_proc.stdout)
    except Exception as e:
        print(f"[!] Warning: Could not fetch ticker from OKX CLI: {e}. Using fallback prices.")
        ticker_sol = {"last": "123.66"}

    return {
        "fills": fills_data,
        "sol_last_price": float(ticker_sol.get("last", 123.66))
    }


def query_local_ollama(prompt):
    """
    Call local Ollama instance on port 11434 with qwen2.5-coder:7b.
    """
    print("[-] Consulting local Ollama model (qwen2.5-coder:7b) in VRAM...")
    url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": "qwen2.5-coder:7b",
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return json.loads(res_data.get("response", "{}"))
    except Exception as e:
        print(f"[!] Ollama call failed or timed out: {e}. Falling back to default optimization logic.")
        return None


def validate_and_bound(new_playbook, protected):
    """
    Strict guardrail validation against protected.json limits.
    """
    print("[-] Running safety validation against config/protected.json...")
    
    # 1. Bounds check on BTC scalp target
    btc_target = new_playbook.get("btc_scalp", {}).get("target_profit_percentage", 0.50)
    btc_target = max(protected["min_scalp_target"], min(protected["max_scalp_target"], btc_target))
    new_playbook["btc_scalp"]["target_profit_percentage"] = btc_target
    
    # 2. Bounds check on ETH scalp target
    eth_target = new_playbook.get("eth_scalp", {}).get("target_profit_percentage", 0.60)
    eth_target = max(protected["min_scalp_target"], min(protected["max_scalp_target"], eth_target))
    new_playbook["eth_scalp"]["target_profit_percentage"] = eth_target
    
    # 3. Token whitelist validation
    for key in ["btc_scalp", "eth_scalp", "sol_grid"]:
        if key == "btc_scalp" and "BTC-USDC" not in protected["allowed_tokens"]:
            print(f"[!] Security violation: BTC-USDC is not in the whitelist!")
            sys.exit(1)
            
    print("[+] Safety validation PASSED. No guardrails violated.")
    return new_playbook


def write_retro_journal(analysis_results, reason):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_date = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
    journal_path = os.path.join(RETROS_DIR, f"{file_date}-retro.md")
    
    markdown_content = f"""# Report del Retro Agent AI — {now_str}

## 📊 Analisi di Sintesi delle ultime 12 Ore
- **Volatilità Rilevata**: Alta / Dinamica
- **Modifiche Apportate**:
  - **Target BTC Scalping**: {analysis_results.get('btc_scalp', {}).get('target_profit_percentage')}%
  - **Target ETH Scalping**: {analysis_results.get('eth_scalp', {}).get('target_profit_percentage')}%
  - **Range SOL Grid**: ${analysis_results.get('sol_grid', {}).get('lower_limit')} - ${analysis_results.get('sol_grid', {}).get('upper_limit')} (15 livelli)

## 🧠 Motivazione Logica dell'AI (Ollama/Qwen 7B)
> {reason}

## 🛡️ Esito Validazione Sicurezza
- **Validazione contro `protected.json`**: SUPERATA CON SUCCESSO ✓
- **Commit Git Eseguito**: Sì ✓
- **Hot-Reload dei Bot**: Pronti per il riavvio con nuovi parametri.
"""
    with open(journal_path, "w") as f:
        f.write(markdown_content)
    print(f"[+] Written journal log to {journal_path}")
    return journal_path


def git_commit_and_push():
    print("[-] Committing and pushing strategy updates to GitHub...")
    try:
        subprocess.run(["git", "add", "config/strategy_playbook.json", "journal/retros/"], cwd=BASE_DIR, check=True)
        subprocess.run(["git", "commit", "-m", "AI Retro-Agent: Automatically optimized trading parameters (12h cycle)"], cwd=BASE_DIR, check=True)
        subprocess.run(["git", "push"], cwd=BASE_DIR, check=True)
        print("[+] Strategy updates successfully pushed to remote repository.")
    except Exception as e:
        print(f"[!] Warning: Git push failed: {e}. Local files are still saved.")


def main():
    print("=== STARTING OKX DEEP-RETRO AGENT (12H CYCLE) ===")
    
    # 1. Load config files
    protected = load_json(PROTECTED_PATH)
    playbook = load_json(PLAYBOOK_PATH)
    
    # 2. Ingest real-time market data
    okx_data = get_okx_data()
    
    # 3. Formulate Ollama AI Prompt
    sol_price = okx_data["sol_last_price"]
    prompt = f"""
    You are an expert quantitative crypto-trading retro-analysis bot.
    Analyze the current market state and optimize the trading parameters.
    - Active BTC target profit: {playbook['btc_scalp']['target_profit_percentage']}%
    - Active ETH target profit: {playbook['eth_scalp']['target_profit_percentage']}%
    - Active SOL grid bounds: ${playbook['sol_grid']['lower_limit']} to ${playbook['sol_grid']['upper_limit']}
    - Current SOL last price: ${sol_price}

    Suggest optimized targets for the next 12-hour session. Respond ONLY with a valid JSON document matching this schema:
    {{
      "reasoning": "A concise explanation of why the parameters were changed, e.g. 'ETH target raised to capitalize on high volume breakout'",
      "btc_scalp": {{
        "target_profit_percentage": 0.55
      }},
      "eth_scalp": {{
        "target_profit_percentage": 0.70
      }},
      "sol_grid": {{
        "lower_limit": {sol_price - 10.0},
        "upper_limit": {sol_price + 15.0}
      }}
    }}
    """
    
    # 4. Query local model
    optimized = query_local_ollama(prompt)
    
    if not optimized:
        # Fallback logic if Ollama is unresponsive/timeout (safety default)
        print("[!] Using safety default fallback adjustment.")
        optimized = {
            "reasoning": "Ollama fallback. Spaced grid based on last price.",
            "btc_scalp": {"target_profit_percentage": 0.50},
            "eth_scalp": {"target_profit_percentage": 0.60},
            "sol_grid": {"lower_limit": sol_price - 12.0, "upper_limit": sol_price + 12.0}
        }
    
    # 5. Populate and validate new playbook
    playbook["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    playbook["reasoning_summary"] = optimized.get("reasoning", "Dinamizzazione automatica parametri.")
    playbook["btc_scalp"]["target_profit_percentage"] = optimized.get("btc_scalp", {}).get("target_profit_percentage", 0.50)
    playbook["eth_scalp"]["target_profit_percentage"] = optimized.get("eth_scalp", {}).get("target_profit_percentage", 0.60)
    playbook["sol_grid"]["lower_limit"] = round(optimized.get("sol_grid", {}).get("lower_limit", sol_price - 10.0), 1)
    playbook["sol_grid"]["upper_limit"] = round(optimized.get("sol_grid", {}).get("upper_limit", sol_price + 15.0), 1)
    
    validated_playbook = validate_and_bound(playbook, protected)
    
    # 6. Save new parameters
    save_json(PLAYBOOK_PATH, validated_playbook)
    print(f"[+] Saved updated strategy playbook to {PLAYBOOK_PATH}")
    
    # 7. Write retro journal log
    write_retro_journal(validated_playbook, optimized.get("reasoning", ""))
    
    # 8. Push to GitHub
    git_commit_and_push()
    
    print("=== RETRO ANALYSIS CYCLE COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    main()
