# Contesto di Sistema degli Agenti e della Conversazione

## 🤖 1. Gli Agenti Coinvolti (La Mappa del Flusso)

Nel nostro progetto di trading algoritmico OKX, abbiamo consolidato un'architettura multimerlato e multiagente che opera su tre livelli perfettamente coordinati:

```
                  ┌────────────────────────────────────────┐
                  │          Giacomo (MacBook Air)         │
                  │   Console di Controllo Master (Client) │
                  └───────────────────┬────────────────────┘
                                      │ (openclaw pair via Tailscale)
                                      ▼
                  ┌────────────────────────────────────────┐
                  │       openclaw-trader-box (Cloud)      │
                  │   Braccio Operativo Persistente (Node) │
                  │   - Ollama locale: Qwen 2.5 Coder 7B   │
                  └───────────────────┬────────────────────┘
                                      │ (API OKX private e pubbliche)
                                      ▼
                  ┌────────────────────────────────────────┐
                  │              OKX Exchange              │
                  │   Demo/Live Spot Trading Platform      │
                  └────────────────────────────────────────┘
```

1.  **Agente Master (MacBook Air locale):**
    *   *Modello:* `google/gemini-3.5-flash` per la chat conversazionale ad altissima velocità e la renderizzazione visiva della GUI del browser.
    *   *Ruolo:* Funge da client di monitoraggio, orchestratore ad alto livello e console di comando centrale per Giacomo.
2.  **Agente Esecutivo (openclaw-trader-box su Cloud VPS):**
    *   *Modello:* **`qwen2.5-coder:7b`** caricato interamente in VRAM sulla GPU Tesla T4 (Ollama locale).
    *   *Ruolo:* È l'ufficio distaccato cloud-native che gira h24 autonomamente. Interroga le API di OKX, gestisce le griglie su SOL, esegue lo scalping su BTC/ETH, e applica rigorosamente le regole di stop-loss senza alcuna dipendenza da API esterne.
3.  **Telegram Bot Bridge (`@beato_zava`):**
    *   *Ruolo:* Interfaccia mobile cifrata e sicura. Permette a Giacomo di inviare il comando `/report` dal suo cellulare per interrogare lo stato e i profitti del server cloud ovunque si trovi.

---

## 📈 2. Sintesi della Strategia Attiva ($370 Baseline)
Abbiamo configurato ed avviato la **nuova strategia diversificata al 100% del capitale** con il sistema di sicurezza avanzato a due livelli:

*   **SOL-USDC Grid Bot:** `$170,00` allocati su 18 griglie aritmetiche (range `$100 - $125`).
*   **BTC-USDC Scalping:** `$100,00` ad operazione (Target profit ottimizzato a **`+0,50%`**).
*   **ETH-USDC Scalping:** `$100,00` ad operazione (Target profit ottimizzato a **`+0,60%`**).
*   **Two-Tiered Risk Manager:**
    *   *Livello 1 (Allarme -15% / $314,50):* Pausa della griglia SOL, blocco nuovi acquisti scalping, mantenimento ordini Limit Sell.
    *   *Livello 2 (Kill-Switch -20% / $296,00):* Chiusura totale, cancellazione e vendita a mercato di tutte le crypto in USDC.

---

## 🗺️ 3. Unificazione dei Modelli Ollama (La Soluzione)
Abbiamo analizzato la dislocazione delle tue VPS e dei tuoi modelli Ollama attivi sulla rete Tailscale:
*   `macbook-air-di-mac` (`100.81.83.95`)
*   `geneticai-nemotron-spark` (`100.125.189.103`) ➔ Ollama attivo con `nemotron-3.5-lightning:latest` (25GB) e `nemotron:latest` (42GB).
*   `openclaw-trader-box` (`100.119.233.95`) ➔ Ollama attivo con GPU T4 e `qwen2.5-coder:7b`.

*Soluzione per unificarli:* Per controllare e centralizzare tutti i tuoi modelli da un'unica comoda dashboard web, ti propongo di installare **Open WebUI** sul tuo Mac o su una VM centrale, e configurarlo per aggregare le porte `11434` dei vari nodi della tua rete privata Tailscale.
