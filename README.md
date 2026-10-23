# ⚡ TRE OS v7.0 (SOVEREIGN PREDATOR EDITION) • AUTONOMOUS PREDICTIVE MICROSTRUCTURE & LOCAL KRONOS-MINI QUANT OS (OKX SPOT EEA)

**TRE OS v7.0 — Sovereign Predator Edition** (`openclaw-trader`) è il sistema operativo quantitativo autonomo progettato per **OKX Spot (Area EEA, Zero Leva, `tdMode: cash`, Rischio Liquidazione Zero, Esecuzione 100% Post-Only Maker `0.00% Fee`)**.

Nella versione **v7.0 Sovereign**, l'intero stack (incluso il Foundation Model finanziario **`NeoQuasar/Kronos-mini` da 4.1M parametri** con previsioni Multi-Orizzonte `5m + 15m`) gira **al 100% dentro una singola Mini-VPS Linux (`brody`, `< 680 MB RAM` complessivi, costo aggiuntivo `$0`)** senza alcuna dipendenza da server GPU esterni, mantenendo come mandato inviolabile la **Regola Aurea di Compounding Organico Giornaliero (`+0.70%` ↔ `+5.00%` al giorno)**.

---

## 🗺️ SCHEMA DECISIONALE COMPLETO (ARCHITETTURA & FLUSSO A 15 SECONDI)

```mermaid
flowchart TD
    subgraph BRODY["🖥️ VPS SOVRANA BRODY (Debian 13 • 2 vCPU • 964MB RAM + 2GB NVMe Swap)"]
        direction TB
        
        subgraph KRONOS_SVC["🧠 kronos-oracle.service (127.0.0.1:8090 • Background Worker)"]
            K1["Fetch Candele OKX EEA\n(180×5m + 120×15m)"] --> K2["NeoQuasar/Kronos-mini (4.1M)\n+ Kronos-Tokenizer-2k"]
            K2 --> K3["Cache RAM O(1) (0.00ms HTTP)\n• Micro 1h: ret_1h_bps, high_bps, low_bps\n• Macro 2h: macro_2h_bps, horizon_aligned"]
        end

        subgraph DAEMON["⚡ openclaw-predator.service (Ciclo Deterministico ogni 15s)"]
            P1["1. Parallel L2 Prefetch (6 Thread, ~0.85s)\nOrderBook Top-5 + 25 Trades per:\nBTC-USDC + 12 Coppie Universo"]
            
            P1 --> B_RADAR["2. Cross-Asset BTC-USDC Radar\nCalcola OFI_BTC & btc_lead_lag_bps"]
            P1 --> MICRO["3. Microstruttura L2 (con Trade Deduplication)\n• Cont-Stoikov OFI (5 livelli)\n• VPIN Toxicity Bucket Tracker\n• Hawkes Burst Intensity + Stoikov Micro-Price"]
            
            K3 --> BLEND
            B_RADAR --> BLEND
            MICRO --> BLEND["4. Fusione Predittiva a 4 Fattori (core/predictor.py)\n• 45% Online RLS (λ=0.985) + Kalman Velocity\n• 35% Kronos-mini Multi-Horizon (75% 5m + 25% 15m)\n• 12% Multi-Model Free OpenRouter Council\n• 8% BTC-USDC Lead-Lag Radar"]

            BLEND --> REGIME{"5. Selezione Regime\n& Scudo Rischio"}
            
            REGIME -->|"VPIN >= 0.68 o\nBTC Lead-Lag < -12 bps"| R_TOXIC["🛡️ TOXIC_DIP_DEFENSE\n• Allarga Buy Trap (-65..-165 bps)\n• Blocca nuovi acquisti se BTC < -14 bps"]
            REGIME -->|"Pred >= +12 bps &\nOFI >= +0.48 & Aligned"| R_BREAK["🚀 AGGRESSIVE_BREAKOUT\n• Turbo-Scalp TP (+20% se 5m+15m allineati)\n• Join Top-of-Book Bid (Post-Only)"]
            REGIME -->|"|Pred| <= 6.5 bps &\nVPIN < 0.45"| R_SCALP["⚡ ACTIVE_SCALP_MM\n• Spread Stretto (-10..-26 bps Buy / +20..+52 bps TP)\n• Fast-Cycle Buy Chaser (Re-peg se drift > 38 bps)"]
            REGIME -->|"Default"| R_MEAN["🔄 MEAN_REVERSION\n• Calibrato su Envelope High/Low di Kronos-mini"]
        end

        subgraph EXEC_GUARD["🔒 DOPPIO BINARIO DI ESECUZIONE & SALVAGUARDIE ZERO-LOSS"]
            R_TOXIC & R_BREAK & R_SCALP & R_MEAN --> DUAL{"6. Gestione Ordini\n& Sub-Ledger"}
            
            DUAL -->|"Binario A: Posizioni Storiche"| LEGACY["🛡️ Cost-Basis Floor + Ratchet Recycler\n• 100% Inventory Coverage (Zero Moonbag inattive)\n• Prezzo Minimo Vendita >= openAvgPx × (1.0005..1.0022)\n• Ratchet Pool (20% profitti Quick-Scalp) avvicina il TP storico\n• FET & SEI in modalità Harvest & Retire (solo vendita in profitto)"]
            
            DUAL -->|"Binario B: Nuovi Acquisti"| QUICK["⚡ Fresh Tranche Quick-Scalp Sub-Ledger\n• Tabella fresh_scalp_tranches isola ogni nuovo BUY\n• Piazza subito SELL Post-Only a +35..+65 bps sopra buy_px\n• Fresh-Tranche Profit-Lock stringe al Best Ask a +28 bps"]
            
            DUAL -->|"Binario C: Cassa Libera >= $8"| SWEEPER["🎯 Opportunity-Ranked Cash Sweeper\n• Classifica le 10 coppie attive per OppScore\n  (Pred_bps + 15·OFI + LiqBonus + Aligned - 20·VPIN - 50·InvWeight)\n• Anti-Stacking Guard: Max $17.50 USDC per singolo token\n• Tetto Max 20% NAV per singolo asset"]
        end
    end
```

---

## 🏆 EVOLUZIONI ARCHITETTURALI DI TRE OS v7.0 (SOVEREIGN EDITION)

| Modulo / Funzione | Precedente v6.0 | ⚡ Nuovo TRE OS v7.0 (Sovereign Predator) |
| :--- | :--- | :--- |
| **Oracolo AI K-Line** | Dipendente da VPS GPU esterna | **100% Locale su `brody` (`127.0.0.1:8090`) con `NeoQuasar/Kronos-mini (4.1M)`, Pre-Warmer in background (`0.00ms` latenza HTTP) e Doppio Orizzonte (`5m` + `15m`)** |
| **Universo Spot OKX EEA** | 8 Token statici | **12 Coppie Dinamiche:** 10 Attive Ultra-Liquide (**`HYPE`, `ZEC`, `SOL`, `SUI`, `NEAR`, `UNI`, `XRP`, `LINK`, `RENDER`, `AVAX`**) + 2 in **`Harvest & Retire` (`FET`, `SEI`)** |
| **Latenza Scansione Mercato** | Sequenziale (`~5.45s` per 13 coppie) | **Parallela a 6 Thread (`ThreadPoolExecutor`, `~0.85s` per leggere 13 OrderBook L2 + 13 Trade Tape)** |
| **Protezione Crash Macro** | Solo VPIN singolo token | **Cross-Asset `BTC-USDC` Lead-Lag Radar:** attiva `TOXIC_DIP_DEFENSE` su tutto il portafoglio se `BTC` scarica (`< -12 bps`) |
| **Rotazione Capitale Veloce** | Media globale `openAvgPx` | **`Fresh Tranche Quick-Scalp Sub-Ledger` (`+35..+65 bps` TP indipendente + `+28 bps` Profit-Lock) + `Anti-Stacking Guard` (`$17.50` max/token)** |
| **Sblocco Posizioni Storiche** | Attesa passiva | **`100% Inventory Coverage` (zero frazioni libere) + `Ratchet Capital Recycler` (usa il 20% dei profitti realizzati per abbassare e sbloccare il TP storico più vicino)** |
| **Consiglio & Audit LLM** | Singolo endpoint | **Multi-Model Free OpenRouter Rotation (`openrouter/free`, `nemotron-ultra-253b:free`, `deepseek-r1:free`, `llama-3.3-70b:free`)** |

---

## 🧠 GUIDA PER L'UTENTE: INSTALLAZIONE 1-CLICK DI KRONOS (`Kronos-mini` 4.1M o `Kronos-small` 24.7M)

**TRE OS v7.0** include lo script universale `scripts/install_kronos_oracle.sh` per installare il Foundation Model finanziario **[shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)** direttamente sulla propria Mini-VPS CPU (`Kronos-mini` 4.1M) o su macchina GPU/Mac (`Kronos-small` 24.7M):

```bash
cd ~/openclaw-trader

# 1. Per Mini-VPS solo CPU (1 GB RAM + 2 GB Swap) -> Installa Kronos-mini (4.1M, ~16 MB di pesi):
bash scripts/install_kronos_oracle.sh --size mini

# 2. Per Server con GPU CUDA o Mac Apple Silicon -> Installa Kronos-small (24.7M):
bash scripts/install_kronos_oracle.sh --size small
```

Il servizio `kronos-oracle.service` mantiene pre-calcolate in RAM le previsioni `5m` (1h) e `15m` (2h) di tutte le 12 coppie e risponde su `http://127.0.0.1:8090/forecast` in **`0.00 ms`**.

---

## 🚀 INSTALLAZIONE 1-CLICK DELL'INTERO SISTEMA

```bash
curl -fsSL https://raw.githubusercontent.com/glaucogaribaldi/openclaw-trader/main/install.sh | bash
```

---

*Gestito ed auditato autonomamente h24 da Lehman Brody su VPS `brody` (Debian 13 Trixie, Python 3.13.5, SQLite3 WAL).*
