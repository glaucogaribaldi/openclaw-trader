# 📈 TRE OS v5.5 • QUANTITATIVE SPOT TRADING OS (OKX)

**TRE OS v5.5** è il sistema operativo quantitativo autonomo progettato per la gestione e l'accrescimento algoritmico del capitale su **OKX Spot** (area EEA, zero leva, zero derivati, rischio liquidazione azzerato).

Il sistema opera esclusivamente in modalità **Maker-Only** (`--stpMode cancel_maker`) su un paniere diversificato di 8 token High-Beta (`NEAR`, `LINK`, `SOL`, `SUI`, `RENDER`, `AVAX`, `FET`, `SEI`), mantenendo un canale di rendimento compounding giornaliero target tra `+0.7%` e `+5.0%`.

---

## 📊 LIVE REPORT & RECONCILIATION SHEET

Il report di rendimento, il bilancio delle posizioni live e il registro contabile FIFO sono sincronizzati in tempo reale e verificati matematicamente al centesimo:

👉 **[Google Sheet Ufficiale • TRE OS Spot Run Report (2026)](https://docs.google.com/spreadsheets/d/1gNr4yEpdynK4juTIzG5m5AJ365y8E5MzZ33AEDaUjwU)**

### 🤖 Daily AI Co-Audit (OpenRouter 24h)
Ogni 24 ore, il daemon autonomo `daily_openrouter_sync.py` su VPS `brody` esegue una chiamata all'engine **OpenRouter AI Co-Auditor** (`openrouter/free`) per sintetizzare lo stato del portafoglio, la gestione del rischio e la stabilità del compounding organico.
L'esito dell'audit viene scritto direttamente nel Google Sheet e salvato nel file di repository [`docs/RUN_REPORT.md`](docs/RUN_REPORT.md).

---

## 📌 NOTA SUGLI ASSET REFUSI IN TABELLA (BTC / ETH)

> **Importante:** Le micro-frazioni residue di **BTC (~$0,27 USDC)** ed **ETH (~$1,96 USDC)** visibili nei saldi di apertura e nella tabella di portafoglio sono **vecchi refusi di polvere storica** derivanti da test precedenti.  
> Tali asset:
> 1. **Non sono gestiti** dalla strategia quantitativa TRE OS v5.5 (focalizzata esclusivamente sugli 8 token High-Beta dell'universo Spot OKX).
> 2. Sono del tutto **ininfluenti** (<0.7% del NAV totale) sui calcoli di rendimento e sul processo di compounding organico.

---

## 🚀 INSTALLAZIONE MONOLINEA 1-CLICK

Per distribuire ed avviare l'intero stack su una nuova VPS Debian/Ubuntu:

```bash
curl -fsSL https://raw.githubusercontent.com/glaucogaribaldi/openclaw-trader/main/install.sh | bash
```

### Componenti dello Stack:
- **Watcher Daemon:** Cron ad alta frequenza (`* * * * *`) su `brody` (`34.28.19.242`).
- **Web Terminal Dashboard:** Servizio HTTP attivo su `http://100.106.15.28:8080/` con auto-refresh a 20m ed export CSV (`/api/export/summary.csv`, `/api/export/ledger.csv`).
- **OpenClaw AgentSkill:** Skill nativa integrata in `skills/openclaw-trader/SKILL.md`.

---

*Gestito ed auditato autonomamente da Lehman Brody su VPS `brody` (Debian 13, Python 3.13, SQLite3).*
