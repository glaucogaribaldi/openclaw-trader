# Progetto Mappa Antiviolenza Lombardia (Prototipo Open-Source)
## Audit Consolidato e Piano di Realizzazione

Questo documento definisce il piano d'azione definitivo, i requisiti tecnici e i protocolli di sicurezza per il prototipo della **Mappa Antiviolenza Lombardia**, progettata per essere totalmente aperta, collaborativa e scalabile a livello nazionale.

---

## 🚨 1. Linea Rossa di Sicurezza ed Etica: Riservatezza Assoluta

*   **Le Case Rifugio (CR):** Non verranno mai mappate con coordinate esatte. Saranno rappresentate graficamente solo ed esclusivamente tramite:
    1.  **Associazione alla sede amministrativa del rispettivo Centro Antiviolenza (CAV)** partner (che gestisce materialmente l'accesso in sicurezza della donna).
    2.  In alternativa, tramite un **pin generico sul centroide del comune o della provincia** di appartenenza, privo di indicazioni di via, indirizzo o dettagli visivi della struttura.
*   **Sicurezza della Navigazione:** La Landing Page ospitata su GitHub Pages includerà un pulsante prominente di **"Uscita Rapida" (Quick Exit)**. Se cliccato, questo pulsante:
    *   Reindirizzerà istantaneamente il browser a un sito sicuro e comune (es. Google, Meteo.it o Wikipedia).
    *   Sostituirà la cronologia recente del tab corrente (`window.location.replace`) per rendere più difficile il tracciamento da parte del partner abusante qualora dovesse riprendere improvvisamente il controllo del dispositivo.

---

## 🛠️ 2. Architettura Tecnica

```
┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│  Dati su GitHub (Repo)  │ ───> │   Mappa uMap Dinamica   │ ───> │  GitHub Pages (Landing) │
│  (GeoJSON open-source)  │      │  (OSM, zero costi API)  │      │  (Integrazione + SOS)   │
└─────────────────────────┘      └─────────────────────────┘      └─────────────────────────┘
```

1.  **Piattaforma di Mappatura:** **uMap (OpenStreetMap)**
    *   *Perché:* Gratuito al 100%, conforme al GDPR (nessun tracciamento dell'utente, fondamentale per contesti vulnerabili), nessun costo di API a consumo (a differenza di Google Maps) e predisposto per l'aggiornamento automatico dei dati.
2.  **Archiviazione e Collaborazione:** **GitHub (Repository Pubblica)**
    *   *Perché:* Consente la massima trasparenza, il controllo delle versioni dei dati e permette ad associazioni, attivisti e sviluppatori di contribuire tramite *Pull Request* o segnalando correzioni tramite *GitHub Issues*.
3.  **Aggiornamento Dinamico (Remote Data):**
    *   uMap verrà configurato per leggere i dati direttamente dai file GeoJSON ospitati su GitHub. Ogni aggiornamento o correzione apportata su GitHub si rifletterà istantaneamente sulla mappa pubblica senza dover modificare la configurazione di uMap.
4.  **Landing Page e Geolocalizzazione:**
    *   La mappa uMap verrà incorporata tramite un `iframe` responsivo all'interno di un sito web statico ospitato gratuitamente su **GitHub Pages**.
    *   uMap include nativamente il pulsante di geolocalizzazione (icona del mirino). Quando l'utente lo clicca, la mappa centra istantaneamente la visualizzazione sulla sua posizione GPS attuale, mostrando i CAV, i Pronto Soccorso e le caserme più vicine.

---

## 📊 3. Sourcing e Categorie dei Dati per la Lombardia

Il prototipo della Lombardia includerà i seguenti livelli (Layer) informativi:

| Livello (Layer) | Colore Marker | Icona | Fonti dei Dati per la Lombardia |
| :--- | :--- | :--- | :--- |
| **Centri Antiviolenza (CAV)** | `Rosa Scuro` (`#FF1493`) | `home` | Mappatura ufficiale 1522 (Dipartimento Pari Opportunità) e Albo dei CAV di Regione Lombardia. |
| **Pronto Soccorso (Codice Rosa & Bollino Rosa)** | `Rosso` (`#FF0000`) | `medical` | Database del Ministero della Salute. Ospedali con "Bollini Rosa" (Fondazione Onda) ed evidenziazione dei PS con percorsi dedicati di "Codice Rosa". |
| **Forze dell'Ordine** | `Blu` (`#0000FF`) | `cop` | Carabinieri, Questure e Commissariati della Polizia di Stato in Lombardia (Open Data Ministero dell'Interno). Posti di Polizia negli ospedali lombardi. |
| **Case di Comunità e Servizi Sociali** | `Verde` (`#008000`) | `heart` | Elenco ufficiale delle nuove Case di Comunità attivate da Regione Lombardia (PNRR) che offrono consultori e supporto psicologico. |
| **Supporto Legale (Gratuito Patrocinio)** | `Giallo` (`#FFD700`) | `town-hall` | *Strategia:* Dato che non disponiamo di un database strutturato, inizialmente inseriremo i link diretti agli elenchi degli Ordini degli Avvocati provinciali (Milano, Brescia, Bergamo, ecc.) per l'assistenza alle vittime di violenza di genere. Predisporremo un form GitHub per permettere ad avvocati pro-bono verificati di candidarsi per essere aggiunti sulla mappa. |
| **Reinserimento Lavorativo** | `Arancione` (`#FF8C00`) | `briefcase` | Cooperative sociali e sportelli attivi per l'autonomia economica censiti da Legacoop Sociali (rete WOMAP+). |

---

## 📐 4. Schema dei Dati (Standard GeoJSON)

I dati saranno organizzati in una cartella `data/lombardia/` nella repository sotto forma di file GeoJSON divisi per categorie (es. `cav.geojson`, `pronto_soccorso.geojson`, `forze_ordine.geojson`).

Esempio di struttura di un elemento (Feature):
```json
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [9.1904, 45.4642] // [Longitudine, Latitudine]
  },
  "properties": {
    "categoria": "CAV",
    "nome": "Centro Antiviolenza Milano SVS",
    "indirizzo": "Via della Commenda 12, Milano (MI)",
    "telefono": "02-XXXXXX / 1522",
    "orari": "H24 / Lun-Ven 9:00-18:00",
    "servizi": "Ascolto, supporto psicologico, consulenza legale, orientamento lavoro",
    "bollino_rosa": "no",
    "codice_rosa": "n/a",
    "gratuito": "Sì",
    "link": "https://www.svs-dad.org"
  }
}
```

---

## 🚀 5. Fasi Esecutive dell'Implementazione

### 🟩 Fase A: Configurazione Ambiente e Repository (Giorno 1)
1.  Inizializzazione della repository GitHub pubblica `mappa-antiviolenza-lombardia` con licenza open source (MIT/Creative Commons).
2.  Configurazione di GitHub Pages per l'hosting della Landing Page.
3.  Scrittura della struttura di base della Landing Page (HTML/CSS) con il layout responsivo e il pulsante **"Uscita Rapida"**.

### 🟩 Fase B: Raccolta Dati, Normalizzazione e Geocoding (Giorni 2-3)
1.  Sviluppo di uno script Python (`scripts/geocoder.py`) che:
    *   Legge i dati grezzi dei servizi in Lombardia (CAV, Forze dell'Ordine, Pronto Soccorso).
    *   Interroga le API di geocodifica gratuite di OpenStreetMap (*Nominatim*) per ricavare latitudine e longitudine esatte a partire dagli indirizzi fisici.
    *   Pulisce e maschera le informazioni sensibili delle Case Rifugio (applicando la regola del centroide comunale).
    *   Esporta i dati puliti in file `.geojson` nella cartella `data/`.

### 🟩 Fase C: Configurazione uMap e Collegamento Dati (Giorno 4)
1.  Creazione della mappa ufficiale su uMap.
2.  Configurazione dei singoli layer (CAV, Forze dell'Ordine, Sanità, Psicologia, Legale, Lavoro) impostando colori e icone dedicati.
3.  Configurazione della sincronizzazione dinamica dei layer puntando agli URL "raw" di GitHub dei file `.geojson` (abilitando i parametri per evitare la cache del browser).
4.  Attivazione del widget di geolocalizzazione nativo per permettere agli utenti lombardi di centrare la mappa sulla propria posizione GPS.

### 🟩 Fase D: Integrazione e Pubblicazione (Giorno 5)
1.  Integrazione dell'iframe di uMap all'interno della Landing Page su GitHub Pages.
2.  Ottimizzazione della visualizzazione su smartphone (layout mobile-first, bottoni di chiamata telefonica diretta click-to-call).
3.  Creazione della sezione "Collabora" con le istruzioni e il template per avvocati pro-bono, psicologi o associazioni che vogliono proporsi per essere inseriti sulla mappa.
4.  Lancio e consegna del link di condivisione pubblico.

---
<!-- project: path:/Users/zava/.openclaw/workspace -->
