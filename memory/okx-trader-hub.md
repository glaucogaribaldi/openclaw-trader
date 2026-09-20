# 📊 OKX Aggressive Demo Trader - Memoria Consolidata

## ⚙️ Profilo e Credenziali Attive
- **Profilo di Configurazione:** `democlaw` (predefinito in `~/.okx/config.toml`).
- **Segreti Sicuri:** Gestiti tramite il gestore di segreti nativo di OpenClaw:
  - `OKX_DEMO_API_KEY_DEMOCLAW`
  - `OKX_DEMO_SECRET_KEY_DEMOCLAW`
  - `OKX_DEMO_PASSPHRASE_DEMOCLAW`
- **Ambiente:** Demo Trading (`demo = true`).
- **Autorizzazioni API:** Trasferisci / Earn / Leggi / Preleva / Trading.

---

## 💰 Stato del Capitale e Rischio
- **Capitale Demo Iniziale:** $370,00 USDT.
- **Stop-Loss Globale (Drawdown):** 15% (Soglia di arresto immediato a **$314,50**).
- **Stop-Loss Singole Strategie:** Arresto automatico della singola strategia in caso di perdite superiori al 10% del capitale assegnato.

---

## 📈 Strategie Validate e Parametri Correnti

### 1. 🎯 Grid Bot ETH (Assegnato: $150 - 40% del capitale)
- **Range Dinamico:** $2.350 - $2.620 (ottimizzato ogni 5 minuti in base alla volatilità di mercato).
- **Livelli:** 25 livelli attivi per catturare le oscillazioni.
- **Performance storica migliore:** **+14.40%** in mercato volatile.

### 2. ⚡ Scalping BTC (Assegnato: $50 - 13% del capitale)
- **Dimensione Trade:** 0.0007 BTC per singola operazione.
- **Frequenza:** Adattiva in base alla volatilità.
- **Target Profit per operazione:** 0.05%.
- **Success Rate Target:** >65%.

### ⚖️ 3. Smart Hedge Short/Long ETH (Assegnato: $50 ciascuna posizione - 13% x 2)
- **Leva:** 8x.
- **Regola d'ingaggio intelligente:**
  - Se ETH si muove <1% in 10 min → Apri **entrambe** le posizioni (Hedge classico).
  - Se ETH ha una direzione chiara (>2% in 10 min) → Apri **solo** la posizione a favore del trend.
  - Se ETH si muove >5% in 10 min → Chiudi tutto e proteggi il capitale.

---

## 🖥️ Integrazione Visiva (Strada A)
- **Stato del Browser:** Un'istanza Chromium dedicata di OpenClaw (porta CDP `18801`) è attiva sullo schermo del Mac.
- **URL di Monitoraggio:** `https://my.okx.com/it/balance/assets/unified` in modalità **Trading demo**.
- **Funzione:** Consente al trader di sincronizzare le proprie operazioni API con la visualizzazione della GUI di OKX e a Giacomo di monitorare visivamente i saldi reali (valore totale stimato corrente: **~138.538,37 EUR**).

<!-- project: path:/Users/zava/.openclaw/workspace -->