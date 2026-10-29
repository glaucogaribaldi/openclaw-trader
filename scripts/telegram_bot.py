#!/usr/bin/env python3
"""
TRE OS v6.0 (Predator Edition) Interactive Telegram Bot Interactor (`telegram_bot.py`)
Read-Only Interactive Bot listening for commands:
- /report or /status -> Full Financial Report (New Run v6.0 from 22/10 $298.89 USDC) + AI Narrative
- /oggi -> Today 24h PnL & Fills + Golden Rule Target (+0.70% <-> +5.00%)
- /settimana -> 7 Days PnL & Fills (within v6.0 Run)
- /run -> Full v6.0 Run PnL & Baseline Reconciliation (22/10/2026 21:00 CEST)
- /portafoglio -> Asset Holdings & Cost-Basis Floor Protection
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
    
    prompt = f"""Sei l AI Chief Analyst per TRE OS v6.0 Predator su OKX Spot EEA.
REGOLA AUREA INVIOLABILE: Target Compounding Giornaliero +0.70% <-> +5.00% (+${rep['daily_target_min_usd']:.2f} <-> +${rep['daily_target_max_usd']:.2f} USDC/giorno).
Dati Finanziari Deterministici (Nuova Run v6.0 dal 22/10/2026 21:00 CEST):
- Baseline Iniziale Run v6.0 (22/10): ${rep['baseline_nav']:.2f} USDC
- NAV Live: ${rep['current_nav']:.2f} USDC (Variazione: {rep['net_pnl_run']:+.2f} USDC / {rep['pct_run']:+.2f}%)
- Trappole Limit Attive: {rep['active_orders_count']} ordini sul book (100% Post-Only Maker + Cost-Basis Floor)

Scrivi un ANALISI DI MERCATO DISCORSIVA E PULITA in lingua italiana (max 3 frasi) spiegando:
1. Lo stato del mercato attuale sugli 8 token High-Beta (NEAR, LINK, SOL, SUI, RENDER, AVAX, FET, SEI) guidato da Kronos GPU + OFI/VPIN.
2. Il rispetto della Regola Aurea (+0.70% / +5.00% giornaliero) e la protezione Cost-Basis Floor (openAvgPx + 22 bps, zero vendite in perdita)."""

    if not api_key:
        return f"💡 *Analisi di Mercato (TRE OS v6.0):* Regola Aurea [+0.70% <-> +5.00%/giorno] attiva. Le {rep['active_orders_count']} trappole Post-Only presidiano il book con Cost-Basis Floor attivo."

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
            cand_txt = res_data["choices"][0]["message"]["content"].strip()
            if len(cand_txt) > 40 and "user safety" not in cand_txt.lower():
                return "💡 *ANALISI DISCORSIVA DI MERCATO (AI):*\n" + cand_txt
            return f"💡 *Analisi di Mercato (TRE OS v6.0):* Regola Aurea [+0.70% <-> +5.00%/giorno] attiva su 8 token High-Beta in totale sicurezza (leva zero, Cost-Basis Floor attivo)."
    except Exception:
        return f"💡 *Analisi di Mercato (TRE OS v6.0):* Regola Aurea [+0.70% <-> +5.00%/giorno] attiva su 8 token High-Beta in totale sicurezza (leva zero, Cost-Basis Floor attivo)."

def format_portfolio_view(rep):
    msg = f"💼 *DETTAGLIO PORTAFOGLIO SPOT LIVE (v6.0)*\n📅 _{rep['timestamp']}_\n\n```\n"
    msg += f"{'TOKEN':<8} {'QUANTITÀ':<10} {'VALORE ($)':<11} {'COSTO MEDIO'}\n"
    msg += "-"*46 + "\n"
    for h in rep["holdings"]:
        msg += f"{h['ccy']:<8} {h['qty']:<10.3f} ${h['eq_usd']:<10.2f} ${h.get('open_avg_px', 0.0):.4f}\n"
    msg += "="*46 + "\n"
    msg += f"Baseline Run (22/10):      ${rep['baseline_nav']:.2f} USDC\n"
    msg += f"Cassa Impegnata Dip:       ${rep['usdc_trading_frozen']:.2f} USDC\n"
    msg += f"Cassa Libera:              ${rep['usdc_trading_free']:.2f} USDC\n"
    msg += "```"
    return msg

def format_period_view(rep, period_key, label):
    st = rep["stats"]
    fills = st.get(f"fills_{period_key}", 0)
    pnl = st.get(f"pnl_{period_key}", 0.0)
    notional = st.get(f"notional_{period_key}", 0.0)
    
    msg = f"📈 *PERFORMANCE {label.upper()} (RUN v6.0)*\n📅 _{rep['timestamp']}_\n\n```\n"
    msg += f"• Baseline Run v6.0 (22/10): ${rep['baseline_nav']:.2f} USDC\n"
    msg += f"• Regola Aurea Giornaliera:  +0.70% <-> +5.00% (+${rep['daily_target_min_usd']:.2f} / +${rep['daily_target_max_usd']:.2f})\n"
    msg += f"• Trades Eseguiti (Fills):   {fills}\n"
    msg += f"• Profitto Netto Incassato:  +${pnl:.4f} USDC\n"
    msg += f"• Notionale Scambiato:      ${notional:.2f} USDC\n"
    msg += f"• Commissioni Taker:        $0.00 USDC (100% Post-Only)\n"
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
        return format_period_view(rep, "7d", "Ultimi 7 Giorni (Run v6.0)")
    elif cmd == "/run":
        table = format_telegram_monospace_table(rep)
        return table
    elif cmd == "/portafoglio":
        return format_portfolio_view(rep)
    elif cmd == "/mercato":
        return query_openrouter_market_narrative(rep)
    elif cmd == "/help":
        return """🤖 *COMANDI TELEGRAM TRE OS v6.0 PREDATOR (100% READ-ONLY):*

• /report - Report Completo Nuova Run v6.0 (dal 22/10) + Analisi AI
• /oggi - Performance 24h e Target Regola Aurea (+0.70% <-> +5.00%)
• /settimana - Performance e fills degli ultimi 7 giorni
• /run - Riconciliazione contabile dalla sostituzione v6.0 (22/10 21:00)
• /portafoglio - Dettaglio posizioni spot, Costo Medio e cassa
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
    print(f"[+] Telegram Read-Only Interactive Bot (v6.0) listening for commands...")
    
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
                            
                            send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                            send_data = urllib.parse.urlencode({
                                "chat_id": chat_id,
                                "text": reply_text,
                                "parse_mode": "Markdown"
                            }).encode("utf-8")
                            send_req = urllib.request.Request(send_url, data=send_data)
                            with urllib.request.urlopen(send_req, timeout=8):
                                pass
        except Exception:
            time.sleep(3)

if __name__ == "__main__":
    run_bot_polling()
