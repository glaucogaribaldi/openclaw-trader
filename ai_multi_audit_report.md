# 🛡️ CO-AUDIT AI MULTI-MODELLO SUL MOTORE REALE TRE-OS
> **Modelli interrogati (Ollama VPS remota)**: `nemotron-3.5-lightning:latest` & `nemotron:latest`
> **Data di Audit**: 3 Ottobre 2026

---

## 🟥 MODELLO 1: nemotron-3.5-lightning:latest (L'Analista SRE & Sistemista)
# AUDIT TECHNIQUE SPREGIATO: "SQLite State Machine" per Trading H24 OKX

**Ruolo:** Lead Cybersecurity Auditor & Senior Quantitative Architect  
**Obiettivo:** Valutazione rigorosa, costruttiva e "senza peli sulla lingua" dell'architettura proposta.  
**Voto finale sintetico:** **4.5 / 10**. L'architettura possiede un'intelligenza concettuale valida (state machine basata su DB per trading continuo), ma è **produttivamente inaccettabile** in termini di resilienza, sicurezza operativa e gestione del rischio quantitativo. Mancano blocchi fondamentali di protezione, il codice è fragile di fronte a failure di rete e i parametri di risk management sono ignorati completamente durante l'esecuzione.

---

## 1. Robustness della Gestione degli Stati SQLite
**Voto: 5 / 10**

### Analisi Critica
- **Transizioni logiche ma fragili:** Il flusso `BUY_SUBMITTED` → `SELL_SUBMITTED` → `BUY_SUBMITTED` è correttamente mappato, ma **manca la validazione dello stato corrente** prima del transition. Se il daemon si blocca tra il rilevamento del fill e l'`UPDATE` del DB, lo stato diventa "orfano" e il ciclo successivo potrebbe ri-attivare ordini duplicati o ignorare fill reali.
- **Assenza di atomicità e concorrenza:** L'uso di `sqlite3.connect()` senza `BEGIN IMMEDIATE` o lock row-level espone il DB a race condition se più istanze del daemon girano contemporaneamente (o in contesti cron paralleli). L'istruzione `UPDATE WHERE inst_id = ?` sovrascriverà lo stato senza verificare la coerenza precedente.
- **Stato `CLOSED` inutilizzato:** Nel `bootstrap_db.py`, i token senza ordini aperti vengono marcati `CLOSED`. Nel `watcher_daemon.py`, lo stato viene completamente ignorato (`if not info: continue`), ma non c'è un meccanismo di "risveglio" o transizione forzata se il prezzo rientra nei parametri. È un "cementafon" pronto a generare segnali fantasma.
- **Chiave primaria impropria:** `inst_id` è `PRIMARY KEY`, ma `cl_ord_id` non ha un vincolo UNIQUE. Se l'API OKX restituisce lo stesso `cl_ord_id` per ordini diversi (ripristino sessione) o se il daemon ne piazza due con lo stesso ID, il DB permette silenziosamente l'overwrite.

### Suggerimenti Pratici
- Implementare un campo `version` o `rowid` con lock ottimistica: `UPDATE scalp_runs SET state = ?, version = version + 1 WHERE inst_id = ? AND version = ?`.
- Introdurre uno stato transitorio `PENDING_CONFIRM` e un job di recovery periodico che scansiona il DB per stati bloccati da > N secondi e li sincronizza con lo stato reale sull'exchange.
- Aggiungere UNIQUE constraint su `cl_ord_id` e migrare lo schema per forzare l'idempotenza a livello DB.
- Rivedere il trattamento dello stato `CLOSED`: o rimuoverlo, o dargli una logica di "riattivazione" basata su soglie di prezzo.

---

## 2. Gestione Timeout API OKX & Eccezioni
**Voto: 3 / 10**

### Analisi Critica
- **Crash totale su fallimento API:** Tutte le funzioni (`get_okx_orders`, `get_okx_balance`, `get_ticker_price`, `place_limit_order`) usano `subprocess.run(..., check=True)`. Se l'CLI `okx` restituisce un errore, il processo si arresta immediatamente con `CalledProcessError`. In un daemon H24, un singolo timeout DNS o un rate limit di OKX significa **arresto totale del sistema di trading**.
- **Rilevamento falso di "Fill" (Bug Critico):** In `watcher_daemon.py`, la logica `if cl_ord_id_str not in open_orders_map` viene eseguita dopo `orders = get_okx_orders()`. Se `get_okx_orders()` fallisce ed restituisce `[]`, `open_orders_map` diventa `{}`. **Tutti gli ordini tracciati appariranno come "FILLED"**, generando ordini di vendita/spazzatura inesistenti.
- **Nessun circuit breaker / retry:** Nessuna politica di backoff esponenziale, nessun timeout configurabile sulle chiamate, nessun fallback a prezzi cached o a last known price se l'API è down.
- **Gestione parziale delle risposte:** `place_limit_order` stampa il risultato ma non solleva eccezioni né ritorna uno stato strutturato (successo/fallimento/margine insufficiente). Il codice prosegue assumendo che l'ordine sia stato accettato.

### Suggerimenti Pratici
- Wrapare tutte le chiamate `subprocess` in funzioni con `timeout` configurabile (es. 10s) e gestione `subprocess.TimeoutExpired`.
- Implementare un **Circuit Breaker pattern**: se il numero di errori consecutivi supera una soglia (es. 5), il daemon passa in modalità "safe mode" dove non piazza ordini ma continua a monitorare e loggare.
- Aggiungere un `try/except` intorno all'intero ciclo `main()` che, in caso di errore fatale, salva lo stato corrente su file e riavvia con backoff, invece di crashare.
- **Fix immediato:** Salvare il risultato di `get_okx_orders()` in una variabile e verificare la sua lunghezza/validità prima di iterare, restituendo un elenco vuoto solo *dopo* un log warning, non un crash.

---

## 3. Protezione contro Doppie Aperture (Idempotenza)
**Voto: 4 / 10**

### Analisi Critica
- **Dipendenza esclusiva dall'ID ordine esterno:** L'unico meccanismo di dedup è il controllo `if cl_ord_id_str not in open_orders_map`. Non c'è verifica se un ordine con quell'ID è già stato piazzato in un ciclo precedente e poi cancellato/ritentato.
- **Bootstrap `INSERT OR REPLACE` non sufficienta:** Nel `bootstrap_db.py`, `INSERT OR REPLACE` sovrascrive il record esistente basandosi su `inst_id` (PK). Se il daemon viene riavviato mentre ci sono ordini aperti sull'exchange ma non sincronizzati nel DB, lo stato diventa inconsistente e il daemon potrebbe piazzare un nuovo ordine "fantasma".
- **Nessuna verifica lato exchange prima dell'invio:** Il codice non controlla se esiste già un ordine aperto per quell`inst_id` con prezzo/varianti simili prima di inviare un nuovo limite. Questo espone il capitale a "over-exposure" se il loop gira velocemente (es. secondi) e l'exchange accetta entrambe le richieste.
- **Assenza di nonce o timestamp:** Per garantire true idempotency in ambienti a alta frequenza, servirebbe un meccanismo di dedup basato su timestamp univoci o nonce forniti dall'exchange, oppure un controllo `open orders` immediato prima di ogni `place_limit_order`.

### Suggerimenti Pratici
- Prima di `place_limit_order`, eseguire un `get_okx_orders()` filtrato su `inst_id` e verificare che non esista un ordine aperto non ancora riempito con prezzo/varianti simili.
- Aggiungere una colonna `is_active` o `attempts` nel DB `scalp_runs`, incrementandola ad ogni tentativo di ordine e resettandola solo a fill confermato.
- Utilizzare il campo `cl_ord_id` come UNIQUE constraint a livello DB e gestire l'errore `UNIQUE constraint failed` come "ordine già esistente, ignorare".
- Implementare un "Order Audit Log" che scrive su file/DB ogni ordine piazzato, annullato o scaduto, con timestamp e hash dell'input, per forensic e debug post-mortem.

---

## 4. Sostegno Matematico Gestione Rischio & Drawdown
**Voto: 3 / 10**

### Analisi Critica
- **Parametri di rischio completamente ignorati:** Il file `protected.json` definisce limiti rigorosi (`max_scalp_bet_size: 100`, `absolute_drawdown_limit: -20`, `min_scalp_target: 0.20`, `max_scalp_target: 2.50`), ma **nessuna di queste variabili viene letta o applicata** nel `watcher_daemon.py`. Il capitolo quantitativo è teorico, non operativo.
- **Dimensionamento fisso e non adattivo:** `size_usd = 50.0` è hardcoded nella mappa `whitelisted_tokens`. Non c'è nessuna logica di Kelly, volatility-adjusted sizing o scaling basato sull'equity corrente. Se il capitale crolla del 15%, il sistema continua a rischiare $50 per trade.
- **Target profit e offset non validati:** I target dai `playbook.json` (es. BTC 0.55%) sono inferiori al minimo consentito da `protected.json` (0.20%) ma sopra il massimo (2.50%). Non c'è nessuna validazione `if target < min or target > max: reject o log warning`. Potrebbe essere piazzato un ordine con target irrealistico o troppo aggressivo.
- **Nessuna stima di commissioni/slippage:** Il calcolo `sell_px = round(entry_px * (1 + target_pct), ...)` non include fee maker/taker di OKX (tipicamente 0.02% - 0.1% spot). Il sistema crede di raggiungere il target netto, ma in realtà il profitto è eroso. Inoltre, nessuna tolleranza di slippage è prevista.
- **Drawdown circolante non monitorato:** Non c'è tracciamento del P&L accumulato in tempo reale. L'impostazione `absolute_drawdown_limit: -20` (probabilmente % sul capitale totale) non viene mai controllata. Il sistema potrebbe continuare a scalping fino a prosciugare il conto prima che un supervisore esterno intervenga.
- **Correlation / basket risk:** I 4 token sono trattati in modo indipendente. Non c'è controllo di esposizione totale sul basket (es. se BTC e ETH scendono insieme, il drawdown combinato potrebbe superare il limite -20% molto prima che il sistema si fermi).

### Suggerimenti Pratici
- **Integrare `protected.json` nel core loop:** All'inizio di ogni iterazione, leggere il saldo attuale, il P&L della sessione e confrontare con `absolute_drawdown_limit`. Se superato, forzare lo stato a `HALT` e disabilitare ulteriori piazzamenti.
- **Validazione target:** Prima di calcolare `sell_px`, verificare `if target_pct < protected["min_scalp_target"] or target_pct > protected["max_scalp_target"]: log error e skip trade`.
- **Dinamica position sizing:** Implementare una funzione di dimensionamento che legga l'equity disponibile e applichi un % fisso (es. 2% per trade) o un modello Kelly basato sulla storia dei win/loss. Sostituire `size_usd = 50.0` con una query live al saldo del conto.
- **Stima commissioni:** Aggiungere una costante `OKX_FEE_RATE = 0.001` (es.) e sottrarla al calcolo del prezzo target: `sell_px = round(entry_px * (1 + target_pct + OKX_FEE_RATE), ...)` per garantire che il target netto sia rispettato.
- **Drawdown tracking in DB:** Aggiungere una tabella `daily_pnl` o una colonna `session_pnl` in `scalp_runs` che sommi il realized P&L di ogni fill, e un job che fermi il sistema se l'accumulato viola i limiti.

---

## VERdetto Finale & Raccomandazioni Estrattive

L'architettura attuale è un **MVP (Minimum Viable Product) concettualmente interessante ma produttivamente pericoloso**. Se messo in produzione in questa forma, esporrebbe il capitale a:
1. **Ordini duplicati** per fallback API innocui.
2. **Crash totali** del sistema a primo timeout di rete.
3. **Risk management bypassato**, con potenziale drawdown illimitato.
4. **Stati DB incoerenti** in caso di arresto improviso.

### Codice "Production-Ready" Minimo (Snippet)

**Aggiornamento `watcher_daemon.py` - Loop Principale con Safeguards:**
```python
# ... imports ...
OKX_FEE_RATE = 0.001  # 0.1% stima fee maker

def safe_api_call(func, *args, timeout=15, retries=3):
    """Wrapper con retry e circuit breaker."""
    for attempt in range(retries):
        try:
            return func(*args)
        except subprocess.TimeoutExpired:
            print(f"[WARN] Timeout API tentativo {attempt+1}/{retries}")
            time.sleep(2 ** attempt)  # exponential backoff
        except Exception as e:
            print(f"[WARN] Errore API: {e}")
            time.sleep(1)
    return None  # fallback sicuro

# ... inside main() ...
    for row in tracked_runs:
        # ... existing var extraction ...
        
        # 1. Validate risk before any state transition
        balances = safe_api_call(get_okx_balance)
        if not balances: continue  # skip cycle, non bloccare il sistema
        
        # Check drawdown semplificato (esimio)
        # In produzione leggerei un file PNL accumulato o tabella DB
        if not check_drawdown_safe(): 
            print("[!] Drawdown limit reached. Halting order placement.")
            continue
            
        # 2. Double-open check
        existing_open = safe_api_call(get_okx_orders)
        if existing_open and any(o['instId'] == inst_id and o['side'] == side for o in existing_open):
            print(f"[!] Order already open for {inst_id}, skipping placement.")
            continue
            
        # ... resto della logica fill -> transition ...
        # 3. Fee-aware TP calculation
        target_pct = playbook.get(playbook_key, {}).get("target_profit_percentage", 0.70) / 100.0
        if target_pct < protected["min_scalp_target"] or target_pct > protected["max_scalp_target"]:
            print(f"[!] Target {target_pct*100:.2f}% out of allowed range [{protected['min_scalp_target']}, {protected['max_scalp_target']}%]")
            continue
            
        # ... apply fee to TP \
        effective_target = target_pct + OKX_FEE_RATE
        sell_px = round(entry_px * (1 + effective_target), precision)
        # ...
```

### Roadmap Correttiva (Priorità)
1. **Critical:** Wrap API calls + timeout + circuito di fallback.
2. **High:** Validazione rischio/drawdown integrata nel loop principale.
3. **High:** Idempotenza a livello DB (UNIQUE cl_ord_id) + verifica ordini aperti pre-placement.
4. **Medium:** Aggiungere stato `PENDING_CONFIRM` + job recovery per stati orfani.
5. **Medium:** Dinamico position sizing basato equity reale, non hardcoded.

Voto finale riveduto dopo safeguards minimal: **6.5 / 10**. Ancora lontano da production-grade, ma le basi per renderlo sicuro ci sono con interventi mirati.

---

## 🟦 MODELLO 2: nemotron:latest (Il Critico Quantitativo Massivo)
**Verdetto di Audit**

**1. Robustezza della gestione degli stati in SQLite (transizioni corrette da BUY_SUBMITTED a SELL_SUBMITTED e CLOSED)**
**Voto: 7/10**

* Punti di forza:
	+ Utilizzo di una tabella SQLite per gestire gli stati, che permette una facile lettura e scrittura.
	+ Transizioni di stato logiche e coerenti.
* Punti di debolezza:
	+ Mancanza di vincoli di integrità sui campi della tabella (ad esempio, PRIMARY KEY non è abbastanza restrittivo).
	+ Nessuna gestione di conflitti in caso di aggiornamenti concorrenti.
	+ La transizione da SELL_SUBMITTED a CLOSED non è esplicitamente gestita (potrebbe essere aggiunta una condizione per gestire la chiusura di un ordine).

**Suggerimenti di modifica:**

* Aggiungere vincoli di integrità sui campi della tabella (ad esempio, UNIQUE per `inst_id` e `state`).
* Implementare un meccanismo di locking per gestire aggiornamenti concorrenti.
* Aggiungere una condizione per gestire la transizione da SELL_SUBMITTED a CLOSED.

Esempio di modifica:
```sql
CREATE TABLE scalp_runs (
    inst_id TEXT NOT NULL,
    state TEXT NOT NULL,
    size REAL NOT NULL,
    price REAL NOT NULL,
    cl_ord_id TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (inst_id, state),
    UNIQUE (inst_id, cl_ord_id),
    CHECK (state IN ('BUY_SUBMITTED', 'SELL_SUBMITTED', 'CLOSED'))
)
```

**2. Gestione dei timeout API OKX e delle eccezioni (cosa succede se un ordine fallisce o se l'API va in timeout?)**
**Voto: 4/10**

* Punti di forza:
	+ Gestione basilare delle eccezioni con `try`-`except`.
* Punti di debolezza:
	+ Mancanza di gestione specifica per timeout API.
	+ Nessuna strategia di retry per ordini falliti.
	+ Eccezioni non vengono loggate in modo significativo.

**Suggerimenti di modifica:**

* Implementare un meccanismo di timeout per le chiamate API (ad esempio, utilizzare `timeout` parametro in `subprocess.run`).
* Aggiungere una strategia di retry per ordini falliti (ad esempio, utilizzare `tenacity` libreria).
* Loggare eccezioni in modo più significativo (ad esempio, utilizzare `logging` modulo).

Esempio di modifica:
```python
import tenacity

@tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, min=4, max=10))
def place_limit_order(...):
    # ...

try:
    proc = subprocess.run(..., timeout=10)
except subprocess.TimeoutExpired:
    logging.error("Timeout API: %s", proc.args)
```

**3. Protezione contro doppie aperture (idempotenza)**
**Voto: 6/10**

* Punti di forza:
	+ Utilizzo di un'ID univoca per gli ordini (`cl_ord_id`).
* Punti di debolezza:
	+ Nessuna verifica esplicita per prevenire doppie aperture.
	+ La logica di idempotenza non è chiaramente separata.

**Suggerimenti di modifica:**

* Aggiungere una verifica esplicita per prevenire doppie aperture (ad esempio, controllare se un ordine con la stessa ID esiste già).
* Separare la logica di idempotenza in una funzione dedicata.

Esempio di modifica:
```python
def is_order_existing(cl_ord_id):
    # Verifica se un ordine con la stessa ID esiste già
    cursor.execute("SELECT 1 FROM scalp_runs WHERE cl_ord_id = ?", (cl_ord_id,))
    return cursor.fetchone() is not None

def place_limit_order(...):
    if is_order_existing(cl_ord_id):
        logging.warning("Ordine già esistente: %s", cl_ord_id)
        return None
    # ...
```

**4. Sostegno matematico della gestione del rischio e del drawdown**
**Voto: 8/10**

* Punti di forza:
	+ Utilizzo di parametri di gestione del rischio (ad esempio, `target_profit_percentage`).
	+ Logica di gestione del drawdown coerente.
* Punti di debolezza:
	+ Mancanza di una descrizione chiara dei parametri di gestione del rischio.
	+ Nessuna verifica di coerenza tra i parametri.

**Suggerimenti di modifica:**

* Aggiungere una descrizione chiara dei parametri di gestione del rischio.
* Verificare la coerenza tra i parametri (ad esempio, `target_profit_percentage` e `max_scalp_bet_size`).

Esempio di modifica:
```json
// config/strategy_playbook.json
{
    // ...
    "btc_scalp": {
        "target_profit_percentage": 0.55,
        "buy_offset_percentage": 0.0,
        "description": "Target profit percentage for BTC scalp strategy"
    },
    // ...
}
```

---
TRE OS • Multi-Model Verification System • Sincronizzato con GitHub
