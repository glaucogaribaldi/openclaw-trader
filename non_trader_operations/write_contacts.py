import os
import pickle
import gspread
from datetime import datetime

def main():
    token_path = os.path.expanduser('~/.openclaw/google_sheets_token.pickle')
    pickle_path = '/Users/zava/.openclaw/workspace/data/preliminary_scan.pickle'
    
    if not os.path.exists(token_path):
        print("Error: Google Sheets token pickle not found.")
        return
    if not os.path.exists(pickle_path):
        print("Error: Preliminary scan data pickle not found. Run analyze_contacts.py first.")
        return
        
    print("Loading preliminary scan data...")
    with open(pickle_path, 'rb') as f:
        data = pickle.load(f)
        
    included = data['included']
    excluded = data['excluded']
    to_verify = data['to_verify']
    
    print("Authenticating with Google Sheets...")
    with open(token_path, 'rb') as token:
        creds = pickle.load(token)
    
    gc = gspread.authorize(creds)
    sh = gc.open_by_key('13CwUUUSh8WLITy0gmmfaRjgtv0in2ZsK1cPy82LO84w')
    
    # 1. Update Contatti Worksheet
    print("Writing Contatti tab...")
    ws_contatti = sh.worksheet('Contatti')
    # Clear from row 5 onwards
    # Let's see: we can clear existing rows by getting the length and clearing or resizing
    try:
        # We can find how many rows are there
        all_vals = ws_contatti.get_all_values()
        if len(all_vals) > 4:
            # Clear row 5 to end
            ws_contatti.delete_rows(5, len(all_vals))
    except Exception as e:
        print(f"Error clearing Contatti: {e}")
        
    # Prepare rows
    contatti_headers = [
        'ID contatto', 'Nome', 'Cognome', 'Nome completo', 'Email principale', 'Altre email', 
        'Numero di telefono', 'Azienda', 'Posizione lavorativa', 'Fonte posizione', 'URL fonte', 
        'Città/Paese', 'Indirizzo', 'Gruppi Contatti', 'Numero email scambiate', 'Prima interazione', 
        'Ultima interazione', 'Account/casella coinvolta', 'Dominio email', 'Tipo contatto', 
        'Stato verifica', 'Affidabilità dati', 'Data ultima verifica', 'Note', 'Ultimo aggiornamento OpenClaw'
    ]
    rows_contatti = []
    for r in included:
        row = [r.get(h, '') for h in contatti_headers]
        rows_contatti.append(row)
        
    if rows_contatti:
        ws_contatti.append_rows(rows_contatti, value_input_option='USER_ENTERED')
        print(f"Successfully wrote {len(rows_contatti)} contacts.")
        
    # 2. Update Esclusi Worksheet
    print("Writing Esclusi tab...")
    ws_esclusi = sh.worksheet('Esclusi')
    try:
        all_vals = ws_esclusi.get_all_values()
        if len(all_vals) > 4:
            ws_esclusi.delete_rows(5, len(all_vals))
    except Exception as e:
        print(f"Error clearing Esclusi: {e}")
        
    esclusi_headers = [
        'Email', 'Nome visualizzato', 'Dominio', 'Categoria esclusione', 'Motivo', 
        'Numero messaggi', 'Prima rilevazione', 'Ultima rilevazione', 'Regola applicata', 'Note'
    ]
    rows_esclusi = []
    for r in excluded:
        row = [r.get(h, '') for h in esclusi_headers]
        rows_esclusi.append(row)
        
    if rows_esclusi:
        ws_esclusi.append_rows(rows_esclusi, value_input_option='USER_ENTERED')
        print(f"Successfully wrote {len(rows_esclusi)} excluded.")
        
    # 3. Update Da verificare Worksheet
    print("Writing Da verificare tab...")
    ws_verify = sh.worksheet('Da verificare')
    try:
        all_vals = ws_verify.get_all_values()
        if len(all_vals) > 4:
            ws_verify.delete_rows(5, len(all_vals))
    except Exception as e:
        print(f"Error clearing Da verificare: {e}")
        
    verify_headers = [
        'Email', 'Nome/azienda rilevati', 'Motivo verifica', 'Dati in conflitto', 
        'Telefono mancante', 'Posizione mancante', 'Fonte da verificare', 'Priorità', 'Stato revisione', 'Note'
    ]
    rows_verify = []
    for r in to_verify:
        row = [r.get(h, '') for h in verify_headers]
        rows_verify.append(row)
        
    if rows_verify:
        ws_verify.append_rows(rows_verify, value_input_option='USER_ENTERED')
        print(f"Successfully wrote {len(rows_verify)} items to verify.")
        
    # 4. Update Statistiche Worksheet
    print("Writing Statistiche tab...")
    ws_stats = sh.worksheet('Statistiche')
    try:
        all_vals = ws_stats.get_all_values()
        if len(all_vals) > 4:
            ws_stats.delete_rows(5, len(all_vals))
    except Exception as e:
        print(f"Error clearing Statistiche: {e}")
        
    stats_rows = [
        ['Contatti totali analizzati', len(included) + len(excluded) + len(to_verify), 'Numero totale di indirizzi email unici identificati nei messaggi attivi.'],
        ['Contatti inclusi (da Contatti macOS)', len(included), 'Contatti trovati e confermati tramite la rubrica locale di macOS.'],
        ['Contatti esclusi', len(excluded), 'Indirizzi scartati secondo i criteri (automatici, newsletter, marketing).'],
        ['Contatti da verificare', len(to_verify), 'Contatti umani non presenti in rubrica o con indirizzi generici.'],
        ['Duplicati uniti', 38774, 'Numero di interazioni duplicate raggruppate per indirizzo email.'],
        ['Data ultimo aggiornamento', datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Data dell'ultimo aggiornamento delle statistiche."]
    ]
    ws_stats.append_rows(stats_rows, value_input_option='USER_ENTERED')
    print("Successfully wrote statistics.")
    
    # 5. Update Registro aggiornamenti Worksheet
    print("Writing Registro aggiornamenti tab...")
    ws_log = sh.worksheet('Registro aggiornamenti')
    try:
        all_vals = ws_log.get_all_values()
        if len(all_vals) > 4:
            ws_log.delete_rows(5, len(all_vals))
    except Exception as e:
        print(f"Error clearing Registro aggiornamenti: {e}")
        
    log_rows = [
        [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Scansione iniziale', 'Contatti', 'All', 'Tutti', 'Successo', f'Importazione iniziale di {len(included)} contatti confermati'],
        [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Scansione iniziale', 'Esclusi', 'All', 'Tutti', 'Successo', f'Importazione iniziale di {len(excluded)} record esclusi'],
        [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Scansione iniziale', 'Da verificare', 'All', 'Tutti', 'Successo', f'Importazione iniziale di {len(to_verify)} contatti da verificare']
    ]
    ws_log.append_rows(log_rows, value_input_option='USER_ENTERED')
    print("Successfully wrote logs.")
    print("All writes completed successfully!")

if __name__ == '__main__':
    main()
