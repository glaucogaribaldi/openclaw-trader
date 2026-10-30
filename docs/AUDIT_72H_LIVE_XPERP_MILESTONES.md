# PIANO DI AUDIT CHIRURGICO A 72 ORE & MILESTONES DI VALIDAZIONE DEFINITIVA (`TRE OS v14.0 — LIVE XPERP 2.5X ISOLATED`)
<!-- project: github.com/glaucogaribaldi/openclaw-trader -->

> **Data Inizio Osservazione Live:** Venerdì 30 Ottobre 2026, ore `13:20 CET` (`12:20 UTC`)
> **Capitale Netto Certificato al Cutover (T0):** `$267.88 USDC` nel Conto di Trading OKX (`uid: 885203458402552862`) + `$6.06 USD` polvere in Finanziamento = **`$273.94 USDC` Totali** (Baseline Run 28/10: `$285.74`; Baseline Storica 22/10: `$298.89`)
> **Motore Unico di Produzione:** `predator_futures_demo.py` in modalità **`LIVE_XPERP_2.5X`** (`openclaw-futures-demo.service`) sui 12 Perpetual Futures regolamentati OKX Europa (`*-USD_UM_XPERP-*`, `instType=FUTURES`, `settleCcy=USD` 1:1 con `USDC`, leva `2.5x Isolated`, `LONG + SHORT`, commissioni Maker `2 bps` / Taker `5 bps`).

---

## 1. OBIETTIVO DELL'AUDIT A 72 ORE (`30 OTTOBRE 13:20 CET ➔ 2 NOVEMBRE 13:20 CET`)

Determinare con **certezza matematica ed empirica** (zero opinioni, solo esiti registrati su OKX `/api/v5/trade/orders-history?instType=FUTURES` e `/api/v5/account/bills`) se **`TRE OS v14.0` (`LIVE_XPERP_2.5X`)** è il sistema definitivo per la run fino al `31/12/2026` e quali micro-tarature applicare ad ogni checkpoint.

### Le 5 Domande Fondamentali a cui le 72 Ore devono rispondere:
1. **Efficienza di Esecuzione Reale (`Fill Rate` & `Slippage`):** Quanti ordini `post_only` (`2 bps`) vengono effettivamente eseguiti su OKX Europa prima della scadenza dei `22 secondi` rispetto a quanti scadono ineseguiti?
2. **Abbattimento Reale del `Fee-Drag Ratio`:** Il passaggio da Spot (`16-20 bps` round-trip) a `XPERP` (`4 bps` Maker / `10 bps` Taker round-trip) mantiene davvero il rapporto `Commissioni / Profitto Lordo <= 12%`?
3. **Simmetria `LONG` vs `SHORT`:** La piramide a **7 Orizzonti Kronos (`5m, 10m, 1h, 2h, 6h, 12h, 24h`)** cattura profitti reali sia nelle fasi di ribasso (`SHORT`) sia nelle fasi di rialzo (`LONG`), evitando i falsi contro-trend?
4. **Efficacia dello Scudo a `+28 bps` + Time-Decay a `45m (+14 bps)`:** Quante posizioni vengono chiuse in profitto protetto (`CLOSED_SHIELD` / `CLOSED_PROFIT`) rispetto agli stop (`CLOSED_STOPLOSS`), e il **Payoff Ratio Medio (`Vincita Media / Perdita Media`)** combinato col **Win Rate** produce un **Expectancy per Trade `E[R] > +$0.12` netto**?
5. **Tenuta Invalicabile del Rischio (`-4.00%` Margin Cap):** Nessun singolo trade chiuso in stop-loss supera mai `-$1.45 USDC` (`-4.00%` dei `~$36 USDC` di margine isolato dello slot)?

---

## 2. CRONOPROGRAMMA DELLE 5 MILESTONES CHIRURGICHE (`T+6h`, `T+12h`, `T+24h`, `T+48h`, `T+72h`)

### 🏁 MILESTONE 1 — `T+6h` (`Venerdì 30 Ottobre, ore 19:30 CET`)
**Focus:** *Verifica Meccanica del Ciclo d'Ordine Reale `XPERP` (Primo Eseguito, Primo Scudo, Zero Posizioni Fantasma).*
- **Controlli Obbligatori:**
  1. Verificare che `futures_demo_positions` (SQLite) coincida **al 100%** con `GET /api/v5/account/positions?instType=FUTURES` (zero posizioni fantasma dopo cancellazione ordini `post_only` a `22s`).
  2. Misurare il **`Post-Only Fill Ratio`** dei primi tentativi di ingresso:
     - *Soglia OK:* `>= 35%` degli ordini `post_only` piazzati viene eseguito entro `22s`.
     - *Azione Correttiva se `< 35%`:* Se i contratti `XPERP` scappano via senza eseguire il `post_only` sul `best_bid`/`best_ask`, alzare la finestra di attesa da `22s` a `35s` oppure consentire ingresso `limit` a `mid_price` quando `|k5m| >= 10 bps` e `|OFI| >= 0.35`.
  3. Verificare la corretta applicazione di `reduceOnly=True` sulla prima chiusura reale (`CLOSED_SHIELD` o `CLOSED_PROFIT`).

---

### 🏁 MILESTONE 2 — `T+12h` (`Sabato 31 Ottobre, ore 01:30 CET / Verifica Mattutina 08:30 CET`)
**Focus:** *Stress-Test Notturno, Funding Rate & Tenuta del Time-Decay a 45 Minuti.*
- **Controlli Obbligatori:**
  1. Verificare il comportamento durante la fascia notturna (`00:00 - 06:00 CET`): zero over-trading in bassa liquidità e rispetto rigoroso della **Quarantena Post-Uscita** (`30m` dopo profitto/scudo, `120m` dopo stop-loss).
  2. Controllare i primi addebiti/accrediti di Funding su `/api/v5/account/bills` per le posizioni rimaste aperte a cavallo dello snapshot di funding.
  3. Verificare l'intervento del **Time-Decay Tightener (`>= 45m ➔ Scudo a +14 bps`)**:
     - *Soglia OK:* Nessuna posizione resta bloccata in laterale per più di `90 minuti` se ha toccato almeno `+14 bps`.
     - *Azione Correttiva se le posizioni restano appese `> 90m` tra `-30 bps` e `+12 bps`:* Introdurre uno **Stagnation Exit a `90 minuti`** che chiude a `break-even (+5 bps)` qualsiasi posizione rimasta ferma per 90 minuti con `|k5m| < 3 bps`.

---

### 🏁 MILESTONE 3 — `T+24h` (`Sabato 31 Ottobre, ore 13:30 CET`)
**Focus:** *Primo Bilancio Economico Giornaliero & Audit Matematico del `Fee-Drag Ratio`.*
- **KPI Quantitativi da Misurare (su almeno `5-12` trade chiusi reali):**
  1. **Net Cashflow 24h (`Delta NAV Reale OKX`):**
     - *Target Regola Aurea 1:* **`+0.70% <-> +5.00%` (`+$1.88 <-> +$13.40 USDC` netti)**.
     - *Soglia Minima Accettabile:* `>= +$0.50 USDC` netti con Drawdown Max Intraday `<= -1.80%`.
  2. **`Fee-Drag Ratio` (`Commissioni Totali Pagate / Profitto Lordo`):**
     - *Soglia OK:* **`<= 12.0%`** (grazie ai `2 bps` Maker di `XPERP`).
     - *Azione Correttiva se `> 15.0%`:* L'Auditor Gemini Free alza automaticamente `min_kronos_10m_bps` da `8.0` a `11.0 bps` e `fast_shield_bps` da `28.0` a `32.0 bps` per aumentare il profitto medio unitario per trade.
  3. **Win Rate (`Wins + ShieldLocks / Totale Chiusi`):**
     - *Soglia OK:* **`>= 65.0%`**.
     - *Azione Correttiva se `< 60.0%`:* Analizzare se gli stop derivano da (a) ingressi contro il micro-trend di `BTC-USD_UM_XPERP-310404` (nel qual caso stringere il `BTC Correlation Veto` da `12 bps` a `8 bps`) o (b) altcoin troppo erratiche (nel qual caso disabilitare la peggiore tra le 12 coppie).

---

### 🏁 MILESTONE 4 — `T+48h` (`Domenica 1 Novembre, ore 13:30 CET`)
**Focus:** *Analisi Asimmetria `LONG` vs `SHORT` & Selezione Darwiniana dei 12 Contratti `XPERP`.*
- **Controlli Obbligatori:**
  1. **Scomposizione PnL `LONG` vs `SHORT`:**
     - Calcolare separatamente `PnL Netto LONG`, `Win Rate LONG` e `PnL Netto SHORT`, `Win Rate SHORT`.
     - *Regola di Perfezionamento:* Se una delle due direzioni ha `Win Rate < 50%`, verificare la soglia `macro_bull` / `macro_bear` (`k6h >= 10 bps, k1h >= 6 bps`) e rendere più selettiva la direzione debole (`k1h >= 10 bps` e `|OFI| >= 0.25`).
  2. **Classifica Darwiniana per Contratto (`Top 6` vs `Bottom 6`):**
     - Estrarre da SQLite e `/api/v5/account/bills` il PnL netto generato da ciascuno dei 12 contratti `*-USD_UM_XPERP-*`.
     - *Regola di Perfezionamento:* Qualsiasi contratto che abbia subito `>= 2` Stop-Loss netti con PnL cumulato `< -$2.00 USDC` in 48h viene **espulso dall'universo attivo** o ridotto a mezzo slot (`6.7%` NAV).

---

### 🏁 MILESTONE 5 — `T+72h` (`Lunedì 2 Novembre, ore 13:30 CET — VERDETTO DEFINITIVO`)
**Focus:** *Certificazione Finale del Sistema Definitivo e Promozione a Regime Composto (`Novembre - 31 Dicembre 2026`).*
- **Criteri Oggettivi per Dichiarare `TRE OS v14.0` il "Sistema Definitivo":**
  1. **Crescita Netta Certificata a 72h:** `NAV Reale OKX > $273.50 USDC` (`>= +2.10%` netto cumulato in 72h, pari a `>= +0.70% / giorno`).
  2. **Zero Violazioni della Regola Aurea 2:** Nessuna singola perdita ha superato il `-4.00%` del margine isolato dello slot (`<= -$1.45 USDC`).
  3. **`Fee-Drag Ratio` Certificato `<= 12.0%`** su tutto il campione di trade delle 72 ore.
  4. **Stabilità Infrastrutturale `100%`:** Zero crash o memory leak su `kronos-oracle.service` (`RAM <= 450 MB`) e `openclaw-futures-demo.service`, e zero interventi manuali richiesti.

---

## 3. COMANDO RAPIDO DI VERIFICA MILESTONE (ESEGUIBILE IN QUALSIASI ISTANTE)

Su `brody` è disponibile lo script di audit istantaneo e test end-to-end:
```bash
/home/zavattoni_giacomo/openclaw-trader/venv/bin/python /home/zavattoni_giacomo/openclaw-trader/scripts/test_v14_xperp_suite.py
/home/zavattoni_giacomo/openclaw-trader/venv/bin/python /home/zavattoni_giacomo/openclaw-trader/scripts/brody_fast_status.py
```
