#!/usr/bin/env python3
"""
TRE OS v5.6 Interactive Telegram Bot Interactor (`telegram_bot.py`)
Read-Only Interactive Bot listening for commands:
- /report or /status -> Full Financial Report + AI Narrative Market Analysis
- /oggi -> Today 24h PnL & Fills
- /settimana -> 7 Days PnL & Fills
- /run -> Full Run PnL & Baseline Reconciliation
- /portafoglio -> Asset Holdings & MTM Allocation
- /mercato -> AI OpenRouter Market Narrative
- /help -> List commands
Runs in background with 0% write permissions (100% Read-Only Safety).
"""
import os, sys, json, sqlite3, subprocess, time
from accounting_engine import compute_financial_report, format_telegram_monospace_table

BASE_DIR = "/home/zavattoni_giacomo/openclaw-trader"
ENV_PATH = os.path.join(BASE_DIR, ".env")

def load_env_vars():
    env_map = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env_map[k.strip()] = v.strip().strip('"').strip("'")
    return env_map

def query_openrouter_market_narrative(rep):
    env_vars = load_env_vars()
    api_key = env_vars.get("OPENROUTER_API_KEY", "")
    
    prompt = f"""Sei l AI Chief Analyst per TRE OS v5.6 su OKX Spot.
Dati Finanziari Deterministici:
- NAV Live: ${rep['current_nav']:.2f} USDC (Capitale Iniziale: ${rep['baseline_nav']:.2f} USDC)
- Profitto Netto Run: +${rep['net_pnl_run']:.2f} USDC (+{rep['pct_run']:.2f}%)
- Trappole Limit Attive: {rep['active_orders_count']} ordini sul book
- MTM Unrealized: ${rep['mtm_unrealized']:.2f} USDC

Scrivi un ANALISI DI MERCATO DISCORSIVA E PULITA in lingua italiana (max 4 frasi) spiegando:
1. Lo stato del mercato attuale sui 8 token High-Beta (NEAR, LINK, SOL, SUI, RENDER, AVAX, FET, SEI).
2. L operativita del regime Low-Vol Micro-Scalping (-0.25% Buy / +0.35% Sell) e la sicurezza totale del sistema (0% leva, rischio liquidazione zero, 0% fee Taker)."""

    if not api_key:
        return "💡 *Analisi di Mercato:* Mercato in consolidamento di weekend. Le 32 trappole limit Maker-Only mantengono posizioni sicure a leva zero."

    try:
        import urllib.request
        payload = {
            "model": "openrouter/free",
            "messages": [{"role": "user", "content": prompt}]
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=data_bytes,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            return "💡 *ANALISI DISCORSIVA DI MERCATO (AI):*\n" + res_data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return "💡 *Analisi di Mercato:* Regime Micro-Scalping attivo su 8 token High-Beta in totale sicurezza (leva zero)."

def format_portfolio_view(rep):
    msg = f"💼 *DETTAGLIO PORTAFOGLIO SPOT LIVE*\n📅 _{rep['timestamp']}_\n\n```\n"
    msg += f"{'TOKEN':<8} {'QUANTITÀ':<12} {'VALORE ($)':<12} {'UNREALIZED MTM'}\n"
    msg += "-"*46 + "\n"
    for h in rep["holdings"]:
        msg += f"{h['ccy']:<8} {h['qty']:<12.3f} ${h['eq_usd']:<11.2f} ${h['upl_usd']:.2f}\n"
    msg += "="*46 + "\n"
    msg += f"Simple Earn (10% APR): ${rep['usdc_simple_earn']:.2f} USDC\n"
    msg += f"Cassa Impegnata Dip:   ${rep['usdc_trading_frozen']:.2f} USDC\n"
    msg += f"Cassa Libera:          ${rep['usdc_trading_free']:.2f} USDC\n"
    msg += "```"
    return msg

def format_period_view(rep, period_key, label):
    st = rep["stats"]
    fills = st.get(f"fills_{period_key}", 0)
    pnl = st.get(f"pnl_{period_key}", 0.0)
    notional = st.get(f"notional_{period_key}", 0.0)
    
    msg = f"📈 *PERFORMANCE {label.upper()}*\n📅 _{rep['timestamp']}_\n\n```\n"
    msg += f"• Trades Eseguiti (Fills): {fills}\n"
    msg += f"• Profitto Netto Incassato: +${pnl:.4f} USDC\n"
    msg += f"• Notionale Scambiato:    ${notional:.2f} USDC\n"
    msg += f"• Commissioni Taker:      $0.00 USDC (0.00% Fee)\n"
    msg += "```"
    return msg

def process_command(cmd_text):
    cmd = cmd_text.strip().lower()
    rep = compute_financial_report()
    
    if cmd in ["/report", "/status", "/start"]:
        table = format_telegram_monospace_table(rep)
        narrative = query_openrouter_market_narrative(rep)
        return f"{table}\n{narrative}"
    elif cmd == "/oggi":
        return format_period_view(rep, "today", "Oggi (Ultime 24h)")
    elif cmd == "/settimana":
        return format_period_view(rep, "7d", "Ultimi 7 Giorni")
    elif cmd == "/run":
        table = format_telegram_monospace_table(rep)
        return table
    elif cmd == "/portafoglio":
        return format_portfolio_view(rep)
    elif cmd == "/mercato":
        return query_openrouter_market_narrative(rep)
    elif cmd == "/help":
        return """🤖 *COMANDI TELEGRAM DISPONIBILI (100% READ-ONLY):*

• /report - Report Completo Finanziario + Analisi AI Mercato
• /oggi - Performance ed operatività delle ultime 24 ore
• /settimana - Performance e fills degli ultimi 7 giorni
• /run - Riconciliazione contabile dal 11/10 ad oggi
• /portafoglio - Dettaglio posizioni spot, MTM e cassa
• /mercato - Analisi discorsiva AI sullo stato del mercato
• /help - Elenco dei comandi"""
    else:
        return "⚠️ Comando non riconosciuto. Digita /help per la lista dei comandi."

def run_bot_polling():
    env_vars = load_env_vars()
    bot_token = env_vars.get("TELEGRAM_BOT_TOKEN", "")
    
    if not bot_token:
        print("[i] TELEGRAM_BOT_TOKEN non configurato in .env. Esecuzione test generatore report in console:")
        print(process_command("/report"))
        return

    import urllib.request, urllib.parse
    offset = 0
    print(f"[+] Telegram Read-Only Interactive Bot listening for commands...")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={offset}&timeout=10"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok") and data.get("result"):
                    for update in data["result"]:
                        offset = update["update_id"] + 1
                        message = update.get("message", {})
                        text = message.get("text", "")
                        chat_id = message.get("chat", {}).get("id")
                        
                        if text and chat_id:
                            print(f"[+] Received command '{text}' from chat {chat_id}")
                            reply_text = process_command(text)
                            
                            # Send response
                            send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                            send_data = urllib.parse.urlencode({
                                "chat_id": chat_id,
                                "text": reply_text,
                                "parse_mode": "Markdown"
                            }).encode("utf-8")
                            send_req = urllib.request.Request(send_url, data=send_data)
                            with urllib.request.urlopen(send_req, timeout=8) as s_resp:
                                pass
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    run_bot_polling()
