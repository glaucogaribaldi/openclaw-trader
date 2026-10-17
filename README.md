# 📈 TRE OS v5.6 • QUANTITATIVE SPOT TRADING OS (OKX)

**TRE OS v5.6** è il sistema operativo quantitativo autonomo progettato per la gestione e l'accrescimento algoritmico del capitale su **OKX Spot** (area EEA, zero leva, zero derivati, rischio liquidazione azzerato).

Il sistema opera esclusivamente in modalità **Maker-Only** (`--stpMode cancel_maker`) su un paniere diversificato di 8 token High-Beta (`NEAR`, `LINK`, `SOL`, `SUI`, `RENDER`, `AVAX`, `FET`, `SEI`), mantenendo un canale di compounding organico giornaliero target tra `+0.7%` e `+5.0%`.

---

## 🚀 NOVITÀ ARCHITETTURALI RELEASE v5.6 (MULTI-ALPHA ENGINE)

1. **Avellaneda-Stoikov Inventory Skew ($q_{\text{skew}}$):**
   Ribilanciamento dinamico degli offset in base al peso dell'asset sul NAV. Se l'inventario su un token sale sopra il 15%, lo spread di acquisto viene allargato e il Take-Profit di vendita viene avvicinato al prezzo di mercato per accelerare la liquidazione in USDC.
2. **OKX Simple Earn Auto-Lending (10% Bonus APR Tracker):**
   Modulo autonomo `scripts/okx_earn_helper.py` per il tracciamento e la resa passiva del 10% APR sulla cassa USDC inattiva tra un ciclo di trade e l'altro.
3. **Dynamic Relative Strength Allocation:**
   Ponderazione dinamica del lotto di acquisto sui token a maggior volume e reattività (1.15x boost su `SUI`, `SEI`, `LINK`).
4. **LOB Micro-Depth Spread Expansion:**
   Espansione automatica dei target di Take-Profit Moonbag (fino a +5.10%) quando lo spessore dell'Ask Book è sottile (< $500 USDC) e l'indicatore OBI è favorevole.
5. **SRE Multi-Node Watchdog (`scripts/sre_watchdog.py`):**
   Monitoraggio continuo della salute del daemon, dell'integrità del database SQLite WAL e dei servizi della VPS.

---

## 📊 LIVE REPORT & RECONCILIATION SHEET

Il report di rendimento, il bilancio delle posizioni live e il registro contabile FIFO sono sincronizzati in tempo reale e verificati matematicamente al centesimo:

👉 **[Google Sheet Ufficiale • TRE OS Spot Run Report (2026)](https://docs.google.com/spreadsheets/d/1gNr4yEpdynK4juTIzG5m5AJ365y8E5MzZ33AEDaUjwU)**

### 🤖 Daily AI Co-Audit (OpenRouter 24h)
Ogni 24 ore, il daemon autonomo `daily_openrouter_sync.py` su VPS `brody` esegue una chiamata all'engine **OpenRouter AI Co-Auditor** (`openrouter/free`) per sintetizzare lo stato del portafoglio e salvare l'esito nel Google Sheet e nel documento repository [`docs/RUN_REPORT.md`](docs/RUN_REPORT.md).

---

## 📌 NOTA SUGLI ASSET REFUSI IN TABELLA (BTC / ETH)

> **Importante:** Le micro-frazioni residue di **BTC (~$0,27 USDC)** ed **ETH (~$1,96 USDC)** visibili nei saldi di apertura e nella tabella di portafoglio sono **vecchi refusi di polvere storica** derivanti da test precedenti.  
> Tali asset:
> 1. **Non sono gestiti** dalla strategia quantitativa TRE OS v5.6 (focalizzata esclusivamente sugli 8 token High-Beta dell'universo Spot OKX).
> 2. Sono del tutto **ininfluenti** (<0.7% del NAV totale) sui calcoli di rendimento e sul processo di compounding organico.

---

## 🚀 INSTALLAZIONE MONOLINEA 1-CLICK

Per distribuire ed avviare l'intero stack su una nuova VPS Debian/Ubuntu:

```bash
curl -fsSL https://raw.githubusercontent.com/glaucogaribaldi/openclaw-trader/main/install.sh | bash
```

---

*Gestito ed auditato autonomamente da Lehman Brody su VPS `brody` (Debian 13, Python 3.13, SQLite3).*
