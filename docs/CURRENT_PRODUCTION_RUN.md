# CURRENT PRODUCTION RUN — TRE OS v14.0 (Sovereign Futures 2.5x Isolated Edition)
<!-- project: github.com/glaucogaribaldi/openclaw-trader -->

> **Stato Attivo in Produzione su `brody`:** **LIVE PERPETUAL FUTURES `2.5x Isolated` (`LONG + SHORT`)** sui 12 contratti regolamentati OKX Europa (`*-USD_UM_XPERP-*`, `instType=FUTURES`, `ruleType=xperp`, `settleCcy=USD` 1:1 con `USDC`).
> **Servizio Primario:** `openclaw-futures-demo.service` (`predator_futures_live.py` / `predator_futures_demo.py`, modalità `LIVE_XPERP_2.5X`).
> **Vecchio Motore Spot 1x (`openclaw-predator.service`):** Spento e disabilitato (`inactive / disabled`) dopo liquidazione pulita al 100% in `USDC` alle `13:18 CET` del `30 Ottobre 2026`.

---

## 1. PARAMETRI UFFICIALI DELLA RUN IN PRODUZIONE (`config/purified_run_config.json`)

- **Capitale Netto Certificato al Cutover Futures `v14.0` (`30/10/2026 13:20 CET`):**
  - **Conto di Trading OKX (`18`):** `$267.88 USDC` (100% disponibile per margine isolato `USD_UM_XPERP`)
  - **Conto di Finanziamento OKX (`6`):** `$6.06 USD` (polvere non negoziabile)
  - **NAV Totale Complessivo:** **`$273.94 USDC`** (Baseline Run Purificata 28/10: `$285.74 USDC`; Baseline Storica 22/10: `$298.89 USDC`)
- **Architettura a Due Camere (`4 Slot x 12.5% NAV = 50% / 50%`):**
  - **Camera 1 (Assalto Futures `2.5x Isolated` `LONG + SHORT`):** Max **4 Slot contemporanei**, ciascuno pari al **`12.5%` del NAV attuale** (`~$33.50 USDC` di margine isolato = `~$83.75 USD` nozionale a leva `2.5x`, max `50%` del NAV impegnato).
  - **Camera 2 (Scudo Contanti Puro `USDC`):** Minimo **`50.0%` del NAV** sempre liquido e intoccabile a riserva.
- **Le 3 Regole Auree Invalicabili (`TRE OS v14.0`):**
  1. **Regola Aurea 1 (`+0.70% <-> +5.00% / giorno`):** Ordini `post_only` Maker (`2 bps` entrata + `2 bps` uscita = `4 bps` round-trip sul nozionale), **Scudo Break-Even Rapido a `+28 bps`** (blocca l'82% del picco) e **45m Time-Decay Tightener a `+14 bps`**.
  2. **Regola Aurea 2 (Tetto Massimo di Perdita `-4.00%` sul Margine):**
     - **Stadio B (Uscita Cognitiva Anticipata a `-110 bps` prezzo = `-2.75%` margine):** chiude se `5m` e `6h` di Kronos confermano la rottura della tesi;
     - **Stadio C (Hard Cap Invalicabile a `-156 bps` prezzo + `4 bps` fee = `-4.00%` margine):** chiusura immediata `reduceOnly=True`;
     - **Circuit Breaker Generale di Portafoglio:** blocca nuove aperture se il NAV scende oltre `-8.0%` dalla baseline.
  3. **Regola Aurea 3 (Interesse Composto Continuo fino a `expiry_iso`):**
     - La taglia di ogni slot (`12.5% * live_nav_est`) scala dinamicamente a ogni profitto incassato fino a `2026-12-31T21:00:00Z` (tapering Reduce-Only negli ultimi 6 giorni dal `25/12/2026`).
