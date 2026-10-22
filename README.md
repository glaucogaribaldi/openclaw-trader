# ⚡ TRE OS v6.0 (PREDATOR EDITION) • PREDICTIVE MICROSTRUCTURE & KRONOS FOUNDATION MODEL QUANT OS (OKX SPOT EEA)

**TRE OS v6.0 — Predator Edition** (`openclaw-trader`) è la nuova generazione del sistema operativo quantitativo autonomo progettato per **OKX Spot (Area EEA, Zero Leva, `tdMode: cash`, Rischio Liquidazione Zero, Esecuzione 100% Post-Only Maker `0.00% Fee`)**.

Rispetto alla precedente generazione v5.6 basata su griglie reattive a 24 ore, **TRE OS v6.0 Predator** integra un'architettura nativa REST HMAC-SHA256 ad alta frequenza (ciclo ogni 15 secondi, `< 25 MB RAM`) che fonde **Fisica Microstrutturale del Libro Ordini L2**, **Apprendimento Online Streaming (RLS + Filtro di Kalman)**, il modello Foundation finanziario **NeoQuasar/Kronos (`Kronos-mini` 4.1M / `Kronos-small` 24.7M)** e **Salvaguardie Matematiche Anti-Perdita (`Cost-Basis Floor` & `Dynamic Profit-Lock`)**.

---

## 🏆 PERCHÉ TRE OS v6.0 (PREDATOR) SOSTITUISCE LA v5.6

| Caratteristica | 🐢 Precedente TRE OS v5.6 | ⚡ Nuovo TRE OS v6.0 (Predator Edition) |
| :--- | :--- | :--- |
| **Connettore Exchange** | Dipendente da CLI Node.js esterna (`okx`) | **Client Python Nativo HMAC-SHA256 (`execution/okx_hybrid_executor.py`)** |
| **Motore di Segnale** | Range statico 24h High/Low | **50% Microstruttura L2 (Cont-Stoikov OFI + VPIN + Hawkes + RLS) + 30% Kronos K-Line Oracle + 20% 3-Agent LLM Council** |
| **Protezione Costo di Carico** | Assente (rischio vendite sotto `openAvgPx`) | **Cost-Basis Floor Inviolabile (`openAvgPx × 1.0022`): ZERO vendite in perdita** |
| **Cattura Profitti Rapidi** | Attesa passiva su target fisso | **Dynamic Profit-Lock Re-Pegging (`+28/+85/+180 bps`) + Fresh Tranche Quick-Scalp Sub-Ledger** |
| **Difesa dai Crolli (Flash Crash)** | Offset statico | **Asymmetric VPIN Toxicity Shield (con deduplicazione esatta del tape trade)** |
| **Gestione Cassa & Yield** | Rischio stallo se CLI fallisce | **Opportunity-Ranked Cash Sweeper (classifica Alpha/VPIN/Kronos, Cap 20% NAV) + OKX Simple Earn 10% APR** |

---

## 🧠 GUIDA COMPLETA PER L'UTENTE: COME INSTALLARE IL MODELLO KRONOS (`Kronos-mini` 4.1M o `Kronos-small` 24.7M)

**TRE OS v6.0** utilizza il primo Foundation Model open-source pre-addestrato specificamente sulle candele finanziarie (**[shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)** su HuggingFace `NeoQuasar`) per prevedere l'andamento delle prossime 12 candele a 5 minuti (**1 ora nel futuro**: High, Low e Close attesi in basis points).

L'utente può scegliere quale taglia del modello installare in base al proprio hardware (anche su una piccola VPS solo CPU, su un Mac Apple Silicon o su una VPS GPU):

### 📊 Tabella Comparativa dei Modelli Kronos Disponibili

| Modello (`--size`) | Repository HuggingFace | Tokenizer | Parametri | Contesto Max | RAM / VRAM Richiesta | Hardware Consigliato |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **`mini`** *(Consigliato per Mini-VPS / CPU)* | `NeoQuasar/Kronos-mini` | `NeoQuasar/Kronos-Tokenizer-2k` | **4.1M** *(Il più leggero in assoluto)* | `2048` | **~350 MB RAM** | Qualsiasi **Mini-VPS Linux (CPU)**, Raspberry Pi 5, Mac M1/M2/M3/M4 |
| **`small`** *(Consigliato per GPU / Mac Pro)* | `NeoQuasar/Kronos-small` | `NeoQuasar/Kronos-Tokenizer-base` | **24.7M** | `512` | **~800 MB RAM/VRAM** | **VPS con GPU CUDA**, Apple Silicon (`mps`), CPU multi-core |
| **`base`** *(Server GPU dedicati)* | `NeoQuasar/Kronos-base` | `NeoQuasar/Kronos-Tokenizer-base` | **102.3M** | `512` | **~2.2 GB VRAM** | Server con GPU NVIDIA dedicata (`cuda:0`) |

> 💡 **Nota "Micro / Mini":** Nell'ecosistema ufficiale Kronos, il modello più piccolo e ultraleggero (4.1 milioni di parametri, progettato per girare istantaneamente anche su CPU senza scheda video) si chiama **`Kronos-mini`**. Il nostro script supporta l'installazione 1-Click sia di **`mini` (4.1M)** che di **`small` (24.7M)**.

---

### 🛠️ OPZIONE A: Installazione Automatica 1-Click (Consigliata)

All'interno della cartella `openclaw-trader`, abbiamo incluso l'installer universale `scripts/install_kronos_oracle.sh` che clona Kronos, crea l'ambiente virtuale isolato, scarica i pesi da HuggingFace e configura automaticamente il servizio `systemd` (`kronos-oracle.service`) sulla porta `8090`:

#### 1️⃣ Per installare **`Kronos-mini` (4.1M)** — Ideale per Mini-VPS senza GPU o basso consumo RAM:
```bash
cd ~/openclaw-trader
bash scripts/install_kronos_oracle.sh --size mini
```

#### 2️⃣ Per installare **`Kronos-small` (24.7M)** — Ideale per VPS con GPU o Apple Silicon:
```bash
cd ~/openclaw-trader
bash scripts/install_kronos_oracle.sh --size small
```

---

### 🛠️ OPZIONE B: Installazione Manuale Passo-Passo (Linux / macOS / Windows WSL)

Se desideri installare manualmente l'oracolo Kronos su qualsiasi macchina locale o remota:

```bash
# 1. Clona il repository ufficiale di Kronos
git clone https://github.com/shiyu-coder/Kronos.git ~/Kronos
cd ~/Kronos

# 2. Crea il virtual environment Python e installa PyTorch + dipendenze
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install torch numpy pandas huggingface_hub safetensors tqdm einops

# 3. Avvia il server Oracolo Universale incluso in openclaw-trader
#    Usa --size mini (4.1M, CPU/Mini-VPS) oppure --size small (24.7M, GPU/MPS)
./venv/bin/python ~/openclaw-trader/scripts/kronos_oracle_server.py --size mini --port 8090
```

---

### 🔗 Come collegare `predator_daemon.py` al tuo Server Kronos

Nel file `.env` nella root di `openclaw-trader`, imposta la variabile `KRONOS_ORACLE_URL`:
* Se Kronos gira **sulla stessa VPS** del bot:
  ```env
  KRONOS_ORACLE_URL="http://127.0.0.1:8090"
  ```
* Se Kronos gira **su una VPS GPU remota via Tailscale** (es. `geneticai-nemotron-spark`):
  ```env
  KRONOS_ORACLE_URL="http://100.125.189.103:8090"
  ```

Per verificare in qualsiasi momento che l'oracolo Kronos stia rispondendo con le previsioni a 1 ora:
```bash
curl -s "http://127.0.0.1:8090/forecast?pairs=SOL-USDC,NEAR-USDC" | python3 -m json.tool
```

> 🛡️ **Zero-Downtime Fallback:** Se il server Kronos viene spento o non è raggiungibile, `predator_daemon.py` continua a operare senza interruzioni ricalibrando automaticamente i pesi sulla Microstruttura L2 (`Cont-Stoikov OFI + VPIN + RLS + Kalman`).

---

## 💰 PASSAGGIO FONDAMENTALE: ATTIVAZIONE OKX SIMPLE EARN (1-CLICK)

Per consentire al sistema di generare il **10.0% APR di rendimento passivo** sulla riserva USDC in Simple Earn (`$35.46 USDC` nella run corrente), esegui un unico click di attivazione sul tuo account OKX:

1. Vai su OKX Web (`my.okx.com`) ➔ Menu **Earn** ➔ **Simple Earn**.
2. Cerca **USDC** e clicca su **Sottoscrivi (Flessibile / Flexible)**.
3. Inserisci l'importo, spunta *"Ho letto e accetto il Contratto Utente"* e clicca **Sottoscrivi**.
4. Attiva la levetta **"Sottoscrizione Automatica" (Auto-subscribe)**.

---

## 📁 STRUTTURA DEL REPOSITORY (v6.0)

```text
openclaw-trader/
├── core/
│   ├── microstructure.py         # Cont-Stoikov Multi-Level OFI, VPIN Toxicity, Hawkes Burst, Micro-Price
│   ├── predictor.py              # Online RLS Streaming Learner (λ=0.985) + Kalman Velocity Filter
│   ├── kronos_oracle.py          # Client HTTP a 0 MB RAM per Kronos-mini (4.1M) / Kronos-small (24.7M)
│   └── predator_auditor.py       # Sincronizzatore FIFO Dual-Ledger + Cost-Basis Floor & Nemotron Auditor
├── agents/
│   └── llm_council.py            # 3-Agent Adversarial Debate (Bull vs Bear vs CIO Judge su OpenRouter Free)
├── execution/
│   └── okx_hybrid_executor.py    # Client REST Nativo HMAC-SHA256 OKX EEA (100% Post-Only Maker)
├── scripts/
│   ├── accounting_engine.py      # Motore contabile deterministico 100% Penny Match
│   ├── telegram_bot.py           # Bot Telegram interattivo Read-Only (@beato_zava)
│   ├── telegram_reporter.py      # Reportistica automatica 08:00 / 20:00 CEST
│   ├── kronos_oracle_server.py   # Server universale per Kronos-mini (4.1M) / Kronos-small (24.7M)
│   └── install_kronos_oracle.sh  # Installer 1-Click per Kronos-mini / Kronos-small
├── predator_daemon.py            # Orchestratore autonomo principale TRE OS v6.0
└── install.sh                    # Installer 1-Click dell'intero sistema
```

---

## 🚀 INSTALLAZIONE RAPIDA 1-CLICK DELL'INTERO SISTEMA

```bash
curl -fsSL https://raw.githubusercontent.com/glaucogaribaldi/openclaw-trader/main/install.sh | bash
```

---

*Gestito ed auditato autonomamente da Lehman Brody su VPS `brody` (Debian 13 Trixie, Python 3.13.5, SQLite3 WAL).*
