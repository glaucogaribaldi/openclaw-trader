#!/usr/bin/env python3
import os
import sys
import json
import urllib.request

OLLAMA_URL = "http://35.188.199.164:11434/api/generate"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHER_PATH = os.path.join(BASE_DIR, "scripts", "watcher_daemon.py")
BOOTSTRAP_PATH = os.path.join(BASE_DIR, "scripts", "bootstrap_db.py")
PLAYBOOK_PATH = os.path.join(BASE_DIR, "config", "strategy_playbook.json")
PROTECTED_PATH = os.path.join(BASE_DIR, "config", "protected.json")


def load_file(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return f"File non trovato: {path}"


def query_ollama(model, prompt):
    print(f"[-] Richiesta audit a {model} su VPS remota (attendi)...", flush=True)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(OLLAMA_URL, data=json.dumps(payload).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data.get("response", "Nessuna risposta.")
    except Exception as e:
        return f"Errore chiamata Ollama ({model}): {e}"


def main():
    print("=== COMINCIANDO MULTI-AUDIT CON DUE MODELLI OLLAMA REALI ===", flush=True)
    
    # 1. Carica i sorgenti reali del progetto
    watcher_code = load_file(WATCHER_PATH)
    bootstrap_code = load_file(BOOTSTRAP_PATH)
    playbook_code = load_file(PLAYBOOK_PATH)
    protected_code = load_file(PROTECTED_PATH)
    
    # 2. Costruisci il prompt dell'audit
    prompt = f"""
    Sei un Lead Cybersecurity Auditor e Senior Quantitative Architect.
    Esegui un audit tecnico spietato, rigoroso e costruttivo sulla nostra nuova architettura a "Macchina a Stati SQLite" per il trading h24 su OKX.
    
    Ecco i sorgenti attuali dell'applicazione:
    
    --- FILE: scripts/watcher_daemon.py ---
    {watcher_code}
    
    --- FILE: scripts/bootstrap_db.py ---
    {bootstrap_code}
    
    --- FILE: config/strategy_playbook.json ---
    {playbook_code}
    
    --- FILE: config/protected.json ---
    {protected_code}
    
    Analizza i sorgenti concentrandoti su:
    1. Robustezza della gestione degli stati in SQLite (transizioni corrette da BUY_SUBMITTED a SELL_SUBMITTED e CLOSED).
    2. Gestione dei timeout API OKX e delle eccezioni (cosa succede se un ordine fallisce o se l'API va in timeout?).
    3. Protezione contro doppie aperture (idempotenza).
    4. Sostegno matematico della gestione del rischio e del drawdown.
    
    Fornisci il tuo verdetto di audit strutturato in Italiano con voti da 1 a 10 per ciascuna sezione, e suggerisci modifiche di codice pratiche.
    """
    
    # 3. Interroga il primo modello: nemotron-3.5-lightning:latest
    audit_nemotron_lightning = query_ollama("nemotron-3.5-lightning:latest", prompt)
    print("[+] Ricevuto audit da nemotron-3.5-lightning:latest", flush=True)
    
    # 4. Interroga il secondo modello: nemotron:latest
    audit_nemotron_dense = query_ollama("nemotron:latest", prompt)
    print("[+] Ricevuto audit da nemotron:latest", flush=True)
    
    # 5. Scrivi il report combinato in Markdown
    report_path = os.path.join(BASE_DIR, "ai_multi_audit_report.md")
    
    combined_report = f"""# 🛡️ CO-AUDIT AI MULTI-MODELLO SUL MOTORE REALE TRE-OS
> **Modelli interrogati (Ollama VPS remota)**: `nemotron-3.5-lightning:latest` & `nemotron:latest`
> **Data di Audit**: 3 Ottobre 2026

---

## 🟥 MODELLO 1: nemotron-3.5-lightning:latest (L'Analista SRE & Sistemista)
{audit_nemotron_lightning}

---

## 🟦 MODELLO 2: nemotron:latest (Il Critico Quantitativo Massivo)
{audit_nemotron_dense}

---
TRE OS • Multi-Model Verification System • Sincronizzato con GitHub
"""
    
    with open(report_path, "w") as f:
        f.write(combined_report)
        
    print(f"[+] Multi-Audit completato con successo! Report scritto in: {report_path}", flush=True)


if __name__ == "__main__":
    main()
