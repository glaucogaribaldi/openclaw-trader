# ⚡ TRE OS v7.7 (SOVEREIGN PREDATOR EDITION) • AUTONOMOUS FLUID MULTI-HORIZON MICROSTRUCTURE & LOCAL KRONOS-MINI QUANT OS (OKX SPOT EEA)

**TRE OS v7.7 — Sovereign Predator Edition** (`openclaw-trader`) è il sistema operativo quantitativo autonomo progettato per **OKX Spot (Area EEA, Zero Leva, `tdMode: cash`, Rischio Liquidazione Zero, Esecuzione 100% Post-Only Maker `0.00% Fee`)**.

Nella versione **v7.7 Sovereign**, l'intero stack (incluso il Foundation Model finanziario **`NeoQuasar/Kronos-mini` da 4.1M parametri** con previsioni **Triplo-Orizzonte `5m + 15m + 1H`** a bassa varianza `T=0.35`, il **Cervello Fluido Multi-Orizzonte** e il nuovo **Institutional Web Terminal React/TypeScript/Tailwind**) gira **al 100% dentro una singola Mini-VPS Linux (`brody`, `< 680 MB RAM` complessivi, costo aggiuntivo `$0`)** senza alcuna dipendenza da server GPU esterni, mantenendo come mandato inviolabile la **Regola Aurea di Compounding Organico Giornaliero (`+0.70%` ↔ `+5.00%` al giorno)** fino al **31 Dicembre 2026**.

---

## 🗺️ SCHEMA DECISIONALE COMPLETO (ARCHITETTURA & CERVELLO FLUIDO A 15 SECONDI)

```mermaid
flowchart TD
    subgraph BRODY["🖥️ VPS SOVRANA BRODY (Debian 13 • 2 vCPU • 964MB RAM + 2GB NVMe Swap)"]
        direction TB
        
        subgraph KRONOS_SVC["🧠 kronos-oracle.service (127.0.0.1:8090 • 3-Horizon Worker)"]
            K1["Fetch Candele OKX EEA\n(180×5m + 120×15m + 120×1H)"] --> K2["NeoQuasar/Kronos-mini (4.1M)\nT=0.35, sample_count=3"]
            K2 --> K3["Cache RAM O(1) (0.00ms HTTP)\n• Micro 1h (5m): ret_1h_bps, high/low\n• Macro 2h (15m): macro_2h_bps\n• Swing 12h (1H): swing_12h_bps"]
        end

        subgraph DAEMON["⚡ openclaw-predator.service (Ciclo Deterministico ogni 15s • Keep-Alive TLS Pool)"]
            P1["1. Parallel Prefetch (4-Thread Auth + 6-Thread L2)\nBalances, OpenOrders, Fills, Kronos +\nOrderBook Top-5 & 25 Trades per BTC + 12 Coppie"]
            
            P1 --> B_RADAR["2. Cross-Asset BTC-USDC Radar\nCalcola OFI_BTC & btc_lead_lag_bps"]
            P1 --> MICRO["3. Microstruttura L2 + Rebound Catcher (2h Low/High)\n• Cont-Stoikov OFI (5 livelli) + VPIN + Hawkes Burst\n• Rileva inversioni a V dai minimi 2h (+12..+130 bps)"]
            
            K3 --> BLEND
            B_RADAR --> BLEND
            MICRO --> BLEND["4. Fusione Predittiva a 4 Fattori + Macro Trend Veto (core/predictor.py)\n• 45% Online RLS (Noise Gate >=1.2bps + L2 Prior Shrinkage) + Kalman\n• 35% Kronos-mini 3-Horizon (5m + 15m + 1H con Veto se 2h<-20bps)\n• 12% Multi-Model Free OpenRouter Council (Kronos-aware)\n• 8% BTC-USDC Lead-Lag Radar"]

            BLEND --> REGIME{"5. Selezione Regime\n& Cervello Fluido"}
            
            REGIME -->|"VPIN >= 0.68 o\nBTC Lead-Lag < -12 bps"| R_TOXIC["🛡️ TOXIC_DIP_DEFENSE\n• Allarga Buy Trap (-65..-165 bps)\n• Blocca nuovi acquisti se BTC < -14 bps"]
            REGIME -->|"Bounce 2h +12..+130 bps &\nOFI >= +0.15 & Sconto >= 25 bps"| R_REB["🎯 REBOUND_CATCHER\n• Boost OppScore fino a +18.0 pts\n• Stringe Buy Offset (* 0.45) per catturare il minimo"]
            REGIME -->|"Pred >= +8 bps & OFI >= +0.25 &\n(Kronos 2h >= +15 o 12h >= +60)"| R_RUN["🚀 ADAPTIVE UPSIDE RUNNER\n• Espande TP Quick-Scalp fino a +115 bps\n• Trailing 78% Profit-Lock sopra +55 bps\n• Bull-Wave Legacy Runner (+45..+95 bps)"]
            REGIME -->|"Default / Range"| R_SCALP["⚡ ACTIVE_SCALP_MM & MEAN_REVERSION\n• Spread calibrato su Envelope Kronos-mini\n• Fast-Cycle Buy Chaser (Re-peg se drift > 38 bps)"]
        end

        subgraph EXEC_GUARD["🔒 DOPPIO BINARIO, FAST-UNLOCK & COMPOUNDING ESPONENZIALE"]
            R_TOXIC & R_REB & R_RUN & R_SCALP --> DUAL{"6. Gestione Ordini,\nSub-Ledger & Dashboard"}
            
            DUAL -->|"Binario A: Posizioni Storiche"| LEGACY["🛡️ Cost-Basis Floor + Auto-Refresh + Micro-Slice Ratchet\n• 100% Inventory Coverage (Zero Moonbag inattive)\n• Cost-Basis Refresh: abbassa subito il TP storico quando un Quick-Scalp riduce openAvgPx\n• Micro-Slice Ratchet ($10 slice) + Bull-Wave Legacy Runner\n• FET & SEI in modalità Harvest & Retire"]
            
            DUAL -->|"Binario B: Nuovi Acquisti"| QUICK["⚡ Fresh Tranche Quick-Scalp Sub-Ledger + Auto-Dust Sweeper\n• Isola ogni nuovo BUY in fresh_scalp_tranches (+35..+115 bps TP)\n• Time-Decay Fast-Exit Ratchet: dopo 4h abbassa il TP a +14 bps (sempre in utile!) per liberare cassa al primo rimbalzo\n• Auto-Dust Sweeper: raccoglie tutte le frazioni decimali residue"]
            
            DUAL -->|"Binario C: Cassa Libera >= $6"| SWEEPER["🎯 Opportunity-Ranked Cash Sweeper (2-Slot Split)\n• OppScore = Pred + 15·OFI + Liq + DarwinianVel + Rebound + MacroSwing12h - 20·VPIN - 50·Inv\n• 2-Slot Parallel Split ($10 + $10) + Dynamic 5.8% NAV Cap\n• Re-Entry Pullback Guard (45m / -25 bps) + Deep-Dip Sniper Reserve"]
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
