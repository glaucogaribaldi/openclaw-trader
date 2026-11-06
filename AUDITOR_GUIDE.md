# 🏛️ TRE OS v34.0 — Guida Tecnica Completa per Auditor Esterno: Flussi, Architettura, Mentalità e Sfide Aperte

**Documento Tecnico di Audit Quantitativo & Architetturale**  
**Versione Motore:** `TRE OS v34.0` (`v1.7.0` Turnkey Release)  
**Target di Mercato:** OKX Europe (EEA) Regulated Perpetual Futures (`*-USD_UM_XPERP-*`, `instType=FUTURES`, `settleCcy=USD` 1:1 `USDC`, Leva Isolata `2.0x -> 3.0x`)

---

## 🧭 1. MENTALITÀ E FILOSOFIA DEL SISTEMA ("THE QUANT MINDSET")

Il sistema **TRE OS (Trading & Risk Execution Operating System)** non è un bot basato su un singolo indicatore tecnico, ma un **sistema operativo quantitativo multi-agente e multi-orizzonte** progettato attorno a **4 pilastri filosofici**:

### 1.1 Il Principio Anti-Compartimenti Stagni (Protocollo Logico-Creativo in 6 Fasi)
Un sistema di trading algoritmico è un **organismo unico**: ogni modifica a un filtro d'ingresso cambia la distribuzione dei trade che arrivano ai gradini della piramide, modifica il prezzo medio ponderato (`avgPx`) post-rincaro e altera il comportamento del trailing stop (Chandelier) e il peso delle commissioni (`Fee-Drag`).
Per questo ogni intervento sul sistema segue obbligatoriamente **6 Fasi**:
1. **Fase 1 (Zoom-Out Olistico):** analisi statistica su blocchi di 40–100 trade reali in SQLite divisi per *Asset Class* (`CRYPTO`, `COMMODITY`, `US_EQUITY`), *Sessione Oraria* (`Notte`, `EU`, `USA`) e *Picco Massimo Raggiunto* (`Peak < 15 bps` Nati Morti vs `15..49 bps` Intermedi vs `>= 50 bps` Runner).
2. **Fase 2 (Fisiologia vs Patologia):** distinzione rigorosa tra *Fisiologia di Mercato* (un normale micro-stop su un setup statisticamente valido, per il quale **è vietato toccare il codice**) e *Patologia di Sistema* (un bug meccanico, un ordine `post_only` rigettato, un calcolo `VPIN` non scalato per `ct_val`, o un'asimmetria invertita tra perdite e vincite).
3. **Fase 3 (Esplorazione tramite le 4 Lenti):**
   - *Lente #1 (Microstruttura L2 & Flusso):* `OFI`, `VPIN`, `Spread`, `Muri L2`, `CVD 1h`, `VWAP 1h`.
   - *Lente #2 (Natura dell'Asset):* distinzione strutturale tra Crypto, Materie Prime macro e Azioni USA.
   - *Lente #3 (Dinamica della Posizione):* interazione tra la Sonda iniziale, i rincari e il nuovo `avgPx`.
   - *Lente #4 (Salute dell'Infrastruttura):* latenza del ciclo, sincronia tra codice deterministico Python e agenti LLM, verifica dell'effettiva esecuzione degli ordini sui server OKX.
4. **Fase 4 (Matrice degli Effetti Collaterali Incrociati):** verifica preventiva di come una modifica in Ingresso impatta Uscita, Piramide, Asset Class e Orari.
5. **Fase 5 (Pre-Mortem & Simulazione Storica):** backtest sui dati storici reali (30 giorni di candele OKX + replay sui trade archiviati in SQLite + suite delle 8 Trappole Reali in `config/trap_simulation_playbook.json`).
6. **Fase 6 (Sintesi & Co-Approvazione + Parameter Freeze):** nessuna modifica ai parametri di mercato viene introdotta a caldo senza validazione e successivo congelamento (`Parameter Freeze`) per lasciare lavorare la legge dei grandi numeri.

### 1.2 I 2 Assiomi Cardine
- **Assioma 1 (Asimmetria Obbligatoria tra Perdite in Sonda e Vincite in Espansione):**
  Le piccole perdite sono fisiologiche nel trading, ma devono avvenire su **volume ridotto (Fase 0 "Sonda" `~60% del lotto base`)** e con taglio rapido (`-18..-45 bps`), mentre le vincite devono avvenire su **volume espanso (Fase 2 e Fase 3 a Leva `3x` in Free-Roll, `~3x–5x` il volume della Sonda)**. È inammissibile rischiare `1$` per guadagnarne `0,40$`.
- **Assioma 2 (Zero Blocchi Silenziosi Incrociati & Dominanza del Trend Reale):**
  I filtri di sicurezza devono modulare la taglia o bloccare trappole oggettive (es. comprare un'ombra di rigetto con `RSI >= 73`), ma non devono mai paralizzare il motore quando il mercato reale (`15m + 1h + 48h + OFI`) sta sviluppando una vera onda direzionale.

---

## ⚙️ 2. ARCHITETTURA DEI COMPONENTI E FLUSSI DI DATI END-TO-END

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                      MASTER WORD CLOCK (core/word_clock.py)                          │
│         Battito Sincronizzato 15,0s (10,0s quando una posizione è in G2/G3)          │
└───────┬──────────────────────────┬───────────────────────────┬───────────────────────┘
        │ Ogni 15s (Slave 1x)      │ Ogni 150s (Slave /10)     │ Ogni 240s / Post-Trade
        ▼                          ▼                           ▼
┌───────────────────────┐  ┌────────────────────────┐  ┌───────────────────────────────┐
│  MOTORE PRINCIPALE    │  │ SCANNER 257 CONTRATTI  │  │ CERVELLO STRATEGICO AI        │
│ predator_futures_demo │  │ refresh_dynamic_xperp  │  │ run_gemini_ordinary_audit     │
│ • Book L2 (5 livelli) │  │ • Scopre i Top 8 mover │  │ • Diagnostica Generale (Payoff│
│ • Candele 15m/1h/4H   │  │   con spread <= 5 bps  │  │   Ratio, DOA count, Fee-Drag) │
│ • Open Interest & CVD │  │   e vol >= $25k        │  │ • Autopsia Ultimo Trade       │
└───────┬───────────────┘  └───────────┬────────────┘  │ • Fallback: gemini-3.5-flash  │
        │                              │               │   -> gemma-4-26b-a4b-it       │
        ▼                              ▼               └───────────────┬───────────────┘
┌───────────────────────────────────────────────────┐                  │
│   ORACOLO NEURALE LOCALE IN RAM (127.0.0.1:8090)  │                  │
│   kronos-oracle.service (NeoQuasar/Kronos-mini)   │                  │
│ • 7 Orizzonti: 5m, 10m, 1h, 2h, 6h, 12h, 24h      │                  │
│ • Metriche Pre-Mean Monte Carlo (Tsinghua Paper): │                  │
│   kronos_zscore_1h, tp_touch_prob_1h, vol_surge   │                  │
└───────────────────────┬───────────────────────────┘                  │
                        │                                              │
                        ▼                                              ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│           IMBUTO DECISIONALE & CICLO DI VITA DELLA POSIZIONE (TRE OS v34.0)          │
│  1. PRE-TRADE:   Micro-Tools #1-#10 + Real-Trend Override + Conferma 2 Cicli         │
│  2. FASE 0:      Sonda Agile (~$60 a 2x) | Taglio Tesi Rotta 6-8m | SL max -45 bps   │
│  3. FASE 0.5/1:  A +25 bps SL -> -20 bps | A +34 bps Scudo G1 (SL -> -10 bps)        │
│  4. FASE 2:      A +44 bps -> Rincaro Garantito a ~$177 (Leva 3x Free-Roll),         │
│                  Peak Rebase sul nuovo avgPx, Floor +2 bps -> Lock 65% sopra +32 bps │
│  5. FASE 3:      A +100 bps -> Rincaro Runner a ~$310 (Leva 3x) + Chandelier Largo   │
│  6. POST-TRADE:  Verifica Fill Chiusura 1,2s (fallback Market) + Pausa 4m/8m +       │
│                  Replay Controfattuale a 60m + Shadow Paper-Arena (SQLite)           │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔍 3. DETTAGLIO TECNICO DEI 6 FLUSSI OPERATIVI

### FLUSSO 1 — Raccolta Dati, Microstruttura L2 e Correzione `ct_val` (`_fetch_swap_book_and_trades` & `core/microstructure.py`)
Ad ogni ciclo (in parallelo tramite `ThreadPoolExecutor(max_workers=12)`), per ciascun contratto attivo in `FUTURES_UNIVERSE` (14 contratti core + fino a 8 contratti *dynamic hot* scoperti tra i 257 `XPERP` di OKX Europa):
1. **Orderbook L2 (`sz=5`) e Trade Tape (`limit=25`):**
   - Calcola **Order Flow Imbalance (`ofi_norm` in `[-1, +1]`)** secondo il modello di *Cont, Kukanov & Stoikov (2014)*.
   - Calcola **`vpin_toxicity` (`[0, 1]`)** secondo *Easley, López de Prado & O'Hara (2012)* e l'intensità auto-eccitante di **Hawkes (`hawkes_net_burst`)**.
   - **Nota Tecnica Importante per l'Auditor (`Audit Fix v32.2`):** sui contratti futures `XPERP` di OKX, la quantità `tr.size` nel trade tape è espressa in *numero di contratti* (es. per `BTC-USD_UM_XPERP`, `1 contratto = 0.0001 BTC`). Il motore moltiplica esplicitamente `tr.size * ct_val` prima di alimentare `VPINTracker`, evitando che 1 contratto da `$8` venga trattato come `1 BTC = $80.000` (che saturerebbe erroneamente il VPIN a `1.0`).
2. **Candele `15m` (ultime 15 barre) e `4H` (ultime 13 barre = 48h):**
   - **Finestra Rolling 15m:** se la candela `15m` corrente è nata da meno di 4 minuti (`c0_age_ms < 240000`), il rendimento `real_15m_bps` viene calcolato rispetto all'apertura della candela precedente per evitare falsi segnali nei primi secondi della nuova barra.
   - **Volume USD normalizzato (`c_vols_usd`):** calcolato come `max(volCcyQuote, volCcy * close, volContracts * ct_val * close)` per gestire i contratti `XPERP` in cui il campo `volCcyQuote` (`x[7]`) di OKX è `0`.
   - Da queste barre vengono estratti: `atr_1h_bps`, `vwap_1h`, `cvd_1h` (Cumulative Volume Delta), `rsi_15m` (RSI a 14 periodi) e le ombre di rigetto (`upper_wick_bps`, `lower_wick_bps`).
3. **Open Interest (`oi_delta_bps`) & Squeeze Detector:**
   - Confronta l'Open Interest attuale con l'ancora a 15 minuti: se il prezzo sale (`real_15m_bps >= +5 bps`), l'OI cresce e l'`OFI >= +0.22` (o il funding è negativo), dichiara `SQUEEZE_LONG` (e simmetricamente `SQUEEZE_SHORT`).

---

### FLUSSO 2 — L'Oracolo Neurale `Kronos-mini (4.1M)` e il "Real-Trend Dominance Override" (`core/kronos_oracle.py` & `kronos_oracle_server.py`)
1. **Inferenza Neurale Locale (`127.0.0.1:8090`):**
   - Il servizio `kronos-oracle.service` mantiene in RAM il Foundation Model per serie storiche finanziarie `NeoQuasar/Kronos-mini (4.1M parametri)` sviluppato alla Tsinghua University (`arXiv:2508.02739v1`).
   - Genera previsioni autoregressive su **7 orizzonti (`5m, 10m, 1h, 2h, 6h, 12h, 24h`)** sia sulle coppie Spot `-USDC` sia direttamente sulle candele dei contratti `*-USD_UM_XPERP-*`.
   - Prima di fare la media delle traiettorie Monte Carlo (*Pre-Mean Trajectory Extraction*), estrae 3 metriche di confidenza:
     - `kronos_zscore_1h`: rapporto Segnale/Rumore rispetto alla volatilità realizzata storica della moneta (richiesto `>= 0.20`);
     - `tp_touch_prob_1h`: probabilità che le traiettorie tocchino almeno `+26 bps` entro 60 minuti;
     - `pred_volume_surge_ratio`: rapporto tra il volume previsto e la media storica.
2. **Scoperta Empirica sul Bias Mean-Reverting di Kronos e Soluzione (`TRE OS v33.0`):**
   - **Il Fenomeno Osservato:** `Kronos-mini` ha una natura intrinsecamente *mean-reverting* sugli shock violenti. Quando Bitcoin crolla di `-290 bps` in un'ora, Kronos tende a prevedere un rimbalzo (`+45..+100 bps LONG`). Se usato come filtro bloccante rigido, durante un crollo di mercato Kronos impedisce di aprire posizioni `SHORT` e tenta invece di comprare rimbalzi `LONG` controcorrente.
   - **La Regola di Dominanza del Trend Reale (`real_crash_regime` / `trend_follow_bear`):**
     - Quando il mercato reale è in crollo confermato (`real_1h_bps <= -25 bps` o `btc_real_1h <= -45 bps`), **è vietato comprare i rimbalzi mean-reverting di Kronos (`raw_bull_setup = False`)**.
     - Quando `15m`, `1h`, `48h` (o `BTC 1h`) e il flusso `OFI` spingono tutti insieme nella direzione del breakout/breakdown reale (`trend_follow_bull` / `trend_follow_bear`), il sistema segue il **Trend Reale** anche se Kronos sta scommettendo sul ritorno alla media.

---

### FLUSSO 3 — I 3 Profili di Asset Class e i 10 Micro-Strumenti Anti-Errore (`Tools #1–#10`)
Il sistema separa i 257 contratti in **3 classi strutturali**:
1. **`CRYPTO_NEURAL` (`BTC, ETH, SOL, NEAR, LINK, AVAX, UNI, SUI, ZEC, ONDO, INJ, TAO...`):** attive 24/7, soggette al filtro di correlazione Beta con Bitcoin (`Tool #9`) e al *Nocturnal Stop Breaker* (120m di pausa notturna dopo un singolo stop tra le `23:00` e le `06:00 CET`).
2. **`COMMODITY_MACRO` (`CL` WTI, `BZ` Brent, `XAU` Oro, `XAG` Argento):** svincolate dal beta a 5m di Bitcoin, bloccate nella finestra notturna illiquida (`22:30–05:45 CET`) e protette dal *Twin-Commodity Cooldown* (uno stop su `CL` blocca anche `BZ` per 240 minuti e viceversa).
3. **`US_EQUITY_XPERP` (`NVDA, TSLA, AAPL, AMZN, COIN, MSTR, QQQ, INTC, SOXL, SNDK, GOOGL, SPCX`):** autorizzate a operare **esclusivamente durante gli orari cash di Wall Street (`15:35–21:30 CET`, Lun–Ven)**.

Ogni candidato passa attraverso **10 Micro-Strumenti Anti-Errore indipendenti per Long (`bull_trap`) e Short (`bear_trap`)**:
- **`Tool #1` (24h Post-Pump Bleed):** blocca `LONG` se il prezzo ha perso `>= 45%` del range 24h con massimi decrescenti su 4H e `15m + 1h` entrambi negativi.
- **`Tool #2` (Liquidity & Spread Gate):** richiede spread `<= 5.5 bps`, volume 1h `>= $5.000` e profondità reale nei primi 2 livelli del book L2 `>= $75`.
- **`Tool #3` (Wick Rejection Guard):** blocca `LONG` se la candela a 15m ha un'ombra superiore di rigetto `>= 38 bps` (`>= 52%` del range della candela); blocca `SHORT` su ombra inferiore analoga.
- **`Tool #4` (1h VWAP & CVD Divergence):** blocca `LONG` sotto il VWAP 1h con `CVD < -0.25`; blocca `SHORT` sopra il VWAP 1h con `CVD > +0.25`.
- **`Tool #5` (Multi-Timeframe & Kronos Alignment):** richiede coerenza tra spinta intraday e orizzonti superiori.
- **`Tool #6` (75m Zombie Exit):** chiude in Maker le posizioni rimaste piatte in Fase 0 dopo 75 minuti se il trend a 1h/6h si è indebolito.
- **`Tool #7` (Anti-Bottom Shorting Guard):** blocca `SHORT` nel `18%` inferiore del range 24h se c'è un rimbalzo in atto (minimo crescente, ombra inferiore `>= 22 bps` o `RSI <= 31`).
- **`Tool #8` (RSI-14 Extreme Guard):** blocca `LONG` con `RSI-14 >= 73` (ipercomprato); blocca `SHORT` con `RSI-14 <= 27` (ipervenduto).
- **`Tool #9` (BTC Beta Veto):** non apre `LONG` su Altcoin mentre Bitcoin sta crollando (e viceversa per `SHORT`).
- **`Tool #10` (Funding & US-Open Whip-Saw Shield):** sospende i nuovi ingressi nei 2 minuti a cavallo dello stacco del funding (`00:00, 08:00, 16:00 UTC`) e nei primi 10 minuti di whipsaw dell'apertura USA (`14:25–14:35 UTC`).

---

### FLUSSO 4 — Ciclo di Vita della Posizione: Analisi Prima, Durante e Dopo (`TRE OS v31.0–v34.0`)

1. **PRIMA DELL'APERTURA (`Pre-Trade Confirmation Gate`):**
   - I candidati vengono classificati tramite uno **Score Composito** che somma: previsione Kronos (`5m, 10m, 1h`), accelerazione multi-orizzonte (`+12 pt`), corpo candela *WorldQuant Alpha #101* (`+10 pt`), probabilità Pre-Mean (`k_prob_bonus`), `OFI` L2, bonus `Squeeze OI+Funding` (`+12..+22 pt`) e `priority_boost` di Gemini.
   - Il candidato deve confermare direzione e tenuta del prezzo per **2 cicli consecutivi (`_PRE_TRADE_CONFIRM_MAP`)** (oppure presentare una convinzione estrema `score >= 38.0`).
2. **FASE 0 — Ingaggio a Sonda (`Probe ~$60 USDC` a Leva `2x`):**
   - Si entra inizialmente con una **Sonda ridotta (`~$58–$64 USDC`)** e ordine `Maker post_only (2 bps)` con Stop-Loss e Take-Profit nativi (`attachAlgoOrds`) registrati direttamente nel matching engine di OKX.
   - **Controllo CONTINUO DURANTE LA POSIZIONE (`thesis_broken_in_trade` & `8m DOA Cut`):** se dopo `6–8 minuti` la posizione non ha mai toccato `+10..+12 bps` e sia `Kronos 5m/10m` sia l'`OFI` si sono girati contro, la Sonda viene chiusa preventivamente (`-$0,12..-$0,20`).
   - **Gradino 0.5 (`+25 bps`):** dimezza lo Stop-Loss a `-20 bps` (`~-$0,12`).
   - **Gradino 1 (`+34 bps`):** stringe lo Stop-Loss a `-10 bps`.
3. **FASE 2 & 3 — Espansione del Volume in Free-Roll (`Gradino 2 a +44 bps` e `Gradino 3 a +100 bps`):**
   - **A `+44 bps` (`Gradino 2`):** quando l'onda è confermata dal flusso L2 (`pyr_flow_ok`), la leva passa a **`3x`** e il sistema inietta **`+$115 USDC` con esecuzione garantita (`urgent_stop=True`)**, portando il volume totale a **`~$177 USDC` (3 volte il volume della Sonda!)**.
   - **Peak Rebase & Spazio Vitale (`v34.0`):** ricalcola il nuovo prezzo medio ponderato (`avgPx`), fissa il pavimento iniziale di sicurezza a **`+2,0 bps` sopra il nuovo `avgPx`** (pari a `~+30 bps` di utile già blindato sulla Sonda iniziale, lasciando `14+ bps` di respiro per non soffocare il trade post-raddoppio) e, appena il prezzo supera **`+32 bps` sopra il nuovo `avgPx`**, blinda progressivamente il **`65%` del profitto (`max(+22 bps, 0.65 * Peak_G2)`)**.
   - **A `+100 bps` sopra il nuovo `avgPx` (`Gradino 3`):** aggiunge un terzo lotto portando il volume a **`~$310 USDC`** per i macro-runner.
4. **DOPO LA CHIUSURA (`Verified Close + Decompression Pause + Counterfactual Audit`):**
   - **Verifica di Chiusura Reale a `1,2s` (`v32.2`):** quando chiude in `post_only`, attende `1,2s` e verifica su OKX che `state == "filled"`; se ancora appeso, cancella e chiude immediatamente a `market` (`reduceOnly=True`), eliminando il rischio di posizioni "fantasma".
   - **Zero Slot-Machine Automatica:** vieta qualsiasi riapertura nello stesso ciclo e impone una **pausa obbligatoria di osservazione (`4 minuti` dopo uno scudo/vincita, `8 minuti` dopo uno stop)** + audit immediato di Gemini Free.

---

## ⚠️ 4. TRASPARENZA PER L'AUDITOR ESTERNO: LIMITI ATTUALI E SFIDE APERTE

Per consentire a un auditor quantitativo esterno una valutazione intellettualmente onesta e completa, ecco le **3 criticità empiriche** emerse dal trading live su conto piccolo (`~$250 USDC`) su cui si concentra l'attuale revisione strategica:

1. **Il Peso delle Commissioni (`Fee-Drag`) rispetto alla Frequenza di Trading (Overtrading):**
   - Con `15–20 operazioni al giorno`, anche pagando `2 bps` Maker in ingresso e `2–5 bps` in uscita, il conto sostiene **`~$1,30–$1,80 USDC/giorno` di commissioni fisse** (pari a circa lo `0,5%–0,7%` del NAV ogni giorno, ovvero `> 15%/mese` di ostacolo commissivo).
   - **Implicazione per l'Auditor:** su un capitale di `$250 USDC`, l'alta frequenza intraday erode il vantaggio statistico. Ridurre la frequenza a **2–4 operazioni al giorno ad altissima selettività** ridurrebbe il *fee-drag* dell'`80%`.
2. **La Distribuzione Empirica delle Escursioni Intraday (`+40..+60 bps` Mean-Reversion vs Trend-Following Pyramid):**
   - Dall'analisi dei 110+ trade registrati in `config/okx_futures_demo.db`, oltre il **60% dei trade indovina la direzione iniziale raggiungendo tra `+35 bps` e `+64 bps`**, ma solo una frazione minore supera `+100..+160 bps` senza prima ritracciare di `-30..-40 bps`.
   - **Il Trade-Off:**
     - Se si usa una **Piramide Trend-Following** (che non prende profitto a `+45 bps` ma anzi aggiunge contratti alzando il prezzo medio `avgPx`), tutte le onde normali che si fermano a `+50..+60 bps` e ritracciano di `-25 bps` chiudono in pareggio (`+$0,04`) o leggera perdita (`-$0,13`), lasciando il conto dipendente dai rari *outlier* da `+160 bps`.
     - Viceversa, un approccio **Swing/Scalp a Target Fisso o Parti-Close** (es. incassare il `70%` della posizione in Limit Maker a `+45..+52 bps` e lasciare correre solo il `30%`) monetizzerebbe costantemente quella fascia `+40..+60 bps` che oggi il sistema centra con regolarità ma non incassa.
3. **Natura Mean-Reverting di `Kronos-mini (4.1M)` durante i Macro-Shock:**
   - `Kronos-mini` eccelle nei regimi di oscillazione normale, ma durante i breakout/breakdown direzionali violenti tende a prevedere il ritorno alla media (dando segnali `LONG` durante i crolli e `SHORT` durante i rally). L'introduzione del *Real-Trend Override (`v33.0`)* ha mitigato questo conflitto, ma la separazione formale tra un **Regime Momentum** e un **Regime Mean-Reversion** resta la leva principale di ottimizzazione.

---

## 🛠️ 5. COME ISPEZIONARE E TESTARE IL SISTEMA (COMANDI RAPIDI PER L'AUDITOR)

| Obiettivo di Audit | Comando da Eseguire nella Repository |
| :--- | :--- |
| **1. Eseguire il Backtest Storico a 30 Giorni (Dati Reali OKX EEA) + Suite delle 8 Trappole Reali** | `./venv/bin/python scripts/simulate_30d_and_traps_v28.py` |
| **2. Generare il Report Esecutivo Completo a 5 Blocchi + Replay Controfattuale 60m + Shadow Paper-Arena** | `./venv/bin/python scripts/executive_report.py` |
| **3. Avviare il Motore in Modalità Paper / Demo Co-Testing (Zero Ordini Reali su OKX)** | `FUTURES_LIVE_EXECUTION=false ./venv/bin/python predator_futures_demo.py --demo` |
| **4. Ispezionare la Costituzione Unificata e le 12 Garanzie Matematiche (`G01–G12`)** | `cat config/unified_mission_and_guarantees.json` |
| **5. Interrogare il Database Storico SQLite dei Trade e della Shadow Arena** | `sqlite3 config/okx_futures_demo.db "SELECT * FROM futures_demo_positions ORDER BY opened_at DESC LIMIT 30;"` |
