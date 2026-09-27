import os
import pickle
import gspread
from datetime import datetime

def main():
    token_path = os.path.expanduser('~/.openclaw/google_sheets_token.pickle')
    pickle_path = '/Users/zava/.openclaw/workspace/data/preliminary_scan.pickle'
    
    if not os.path.exists(token_path) or not os.path.exists(pickle_path):
        print("Error: Pickles not found.")
        return
        
    print("Loading scan data...")
    with open(pickle_path, 'rb') as f:
        data = pickle.load(f)
        
    included = data['included']
    to_verify = data['to_verify']
    excluded = data['excluded']
    
    # Second batch of promoted contacts
    promoted_data = {
        'zava@rcwaves.it': {
            'Nome': 'Giacomo', 'Cognome': 'Zavattoni', 'Nome completo': 'Giacomo Zavattoni',
            'Azienda': 'RC Waves / Totally Imported Srl', 'Posizione lavorativa': 'Co-Founder & Executive Director',
            'Fonte posizione': 'Database Interno / Fondazione RC Waves 2014', 'URL fonte': '',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'La tua casella email principale legata alla co-fondazione di RC Waves.'
        },
        'zavattoni.giacomo@icloud.com': {
            'Nome': 'Giacomo', 'Cognome': 'Zavattoni', 'Nome completo': 'Giacomo Zavattoni',
            'Azienda': 'RC Waves / Totally Imported Srl', 'Posizione lavorativa': 'Co-Founder & Executive Director',
            'Fonte posizione': 'Database Interno', 'URL fonte': '',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Privato', 'Note': 'La tua casella email iCloud personale.'
        },
        'francesco@rcwaves.it': {
            'Nome': 'Francesco', 'Cognome': 'Italiano', 'Nome completo': 'Francesco Italiano',
            'Azienda': 'RC Waves / Totally Imported Srl', 'Posizione lavorativa': 'Co-Founder, Partner & Label Manager',
            'Fonte posizione': 'Intervista Voolcano Music / Varese News', 'URL fonte': 'https://voolcanomusic.com/backstage-francesco-italiano/',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Co-fondatore di RC Waves nel 2014 con Giacomo Zavattoni e partner di Totally Imported.'
        },
        'rocco.putignano@kobaltmusic.com': {
            'Nome': 'Rocco', 'Cognome': 'Putignano', 'Nome completo': 'Rocco Putignano',
            'Azienda': 'Kobalt Music Group', 'Posizione lavorativa': 'Music Industry Professional & Client Relations Manager',
            'Fonte posizione': 'Medium Profile / LinkedIn / Kobalt', 'URL fonte': 'https://medium.com/@roccorokputignano/reposts',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Professionista dell\'industria musicale, bassista, produttore e referente Kobalt.'
        },
        'dshortymusic@gmail.com': {
            'Nome': 'Davide', 'Cognome': 'Shorty', 'Nome completo': 'Davide Shorty',
            'Azienda': 'Davide Shorty Music / Totally Imported', 'Posizione lavorativa': 'Artist, Singer-Songwriter & Producer',
            'Fonte posizione': 'Sanremo 2021 Credits / Wikipedia / YouTube', 'URL fonte': 'https://it.wikipedia.org/wiki/Davide_Shorty',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Professionale', 'Note': 'Cantautore italiano finalista a Sanremo 2021, prodotto e gestito da Totally Imported.'
        },
        'nicolo@artistfirst.it': {
            'Nome': 'Nicolò', 'Cognome': 'Picchioni', 'Nome completo': 'Nicolò Picchioni',
            'Azienda': 'Artist First / The Orchard', 'Posizione lavorativa': 'A&R & Artist & Label Services (Ex-Artist First)',
            'Fonte posizione': 'Contatti storici / LinkedIn', 'URL fonte': '',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Casella storica legata al suo precedente ruolo presso il distributore Artist First.'
        }
    }
    
    emails_to_remove = set(promoted_data.keys())
    
    # 1. Promote from to_verify to included
    import collections
    print("Promoting second batch...")
    
    promoted_included = []
    updated_to_verify = []
    
    for r in to_verify:
        email = r['Email'].lower()
        if email in emails_to_remove:
            p_info = promoted_data[email]
            
            # Fetch Mail database details
            import sqlite3
            conn = sqlite3.connect("/Users/zava/Library/Mail/V10/MailData/Envelope Index")
            cursor = conn.cursor()
            
            cursor.execute("SELECT ROWID FROM addresses WHERE address = ?", (email,))
            addr_row = cursor.fetchone()
            msg_count = 0
            first_inter = ""
            last_inter = ""
            mailboxes_str = ""
            domain = email.split('@')[-1]
            
            if addr_row:
                addr_id = addr_row[0]
                cursor.execute("""
                    SELECT COUNT(*), MIN(m.date_sent), MAX(m.date_sent)
                    FROM messages m
                    WHERE m.sender = ? OR m.ROWID IN (SELECT message FROM recipients WHERE address = ?)
                """, (addr_id, addr_id))
                res = cursor.fetchone()
                if res and res[0] > 0:
                    msg_count = res[0]
                    first_inter = datetime.fromtimestamp(res[1]).isoformat() if res[1] else ""
                    last_inter = datetime.fromtimestamp(res[2]).isoformat() if res[2] else ""
                    
                cursor.execute("""
                    SELECT DISTINCT m.mailbox
                    FROM messages m
                    WHERE m.sender = ? OR m.ROWID IN (SELECT message FROM recipients WHERE address = ?)
                """, (addr_id, addr_id))
                mboxes = [r[0] for r in cursor.fetchall()]
                cursor.execute("SELECT ROWID, url FROM mailboxes WHERE ROWID IN ({})".format(",".join(map(str, mboxes if mboxes else [0]))))
                m_names = []
                for m_id, url in cursor.fetchall():
                    account = "iCloud"
                    if "22d7fc7b-7d93-4693-b171-eb599f795de" in url.lower():
                        account = "Totallyimported"
                    elif "89d2cd85-b8ea-40bb-b0bc-ad7fc509ee05" in url.lower():
                        account = "Totallyinnovation"
                    f_name = url.split('/')[-1].replace('%20', ' ')
                    m_names.append(f"{account}/{f_name}")
                mailboxes_str = ", ".join(sorted(m_names))
            
            new_record = {
                'ID contatto': f"CLAW-{email.split('@')[0].upper()}",
                'Nome': p_info['Nome'],
                'Cognome': p_info['Cognome'],
                'Nome completo': p_info['Nome completo'],
                'Email principale': email,
                'Altre email': '',
                'Numero di telefono': '',
                'Azienda': p_info['Azienda'],
                'Posizione lavorativa': p_info['Posizione lavorativa'],
                'Fonte posizione': p_info['Fonte posizione'],
                'URL fonte': p_info['URL fonte'],
                'Città/Paese': 'Milano, Italia' if 'rcwaves' in email or 'artistfirst' in email or 'streamland' in email else 'Italia',
                'Indirizzo': '',
                'Gruppi Contatti': '',
                'Numero email scambiate': msg_count,
                'Prima interazione': first_inter,
                'Ultima interazione': last_inter,
                'Account/casella coinvolta': mailboxes_str,
                'Dominio email': domain,
                'Tipo contatto': p_info['Tipo contatto'],
                'Stato verifica': 'Confermato',
                'Affidabilità dati': p_info['Affidabilità dati'],
                'Data ultima verifica': datetime.now().strftime("%Y-%m-%d"),
                'Note': p_info['Note'],
                'Ultimo aggiornamento OpenClaw': datetime.now().isoformat()
            }
            promoted_included.append(new_record)
        else:
            updated_to_verify.append(r)
            
    # Save the updated records to pickle
    data['included'] = included + promoted_included
    data['to_verify'] = updated_to_verify
    
    with open(pickle_path, 'wb') as f:
        pickle.dump(data, f)
        
    print(f"Promoted {len(promoted_included)} contacts successfully.")
    print(f"Remaining to_verify count: {len(updated_to_verify)}")
    
    # 2. Update Google Sheet
    print("Writing second batch of promoted contacts to Google Sheet...")
    with open(token_path, 'rb') as token:
        creds = pickle.load(token)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key('13CwUUUSh8WLITy0gmmfaRjgtv0in2ZsK1cPy82LO84w')
    
    # Tab Contatti
    ws_contatti = sh.worksheet('Contatti')
    try:
        ws_contatti.batch_clear(["A5:Z2000"])
    except Exception as e:
        print(f"Error clearing Contatti: {e}")
        
    contatti_headers = [
        'ID contatto', 'Nome', 'Cognome', 'Nome completo', 'Email principale', 'Altre email', 
        'Numero di telefono', 'Azienda', 'Posizione lavorativa', 'Fonte posizione', 'URL fonte', 
        'Città/Paese', 'Indirizzo', 'Gruppi Contatti', 'Numero email scambiate', 'Prima interazione', 
        'Ultima interazione', 'Account/casella coinvolta', 'Dominio email', 'Tipo contatto', 
        'Stato verifica', 'Affidabilità dati', 'Data ultima verifica', 'Note', 'Ultimo aggiornamento OpenClaw'
    ]
    rows_contatti = []
    for r in data['included']:
        row = [r.get(h, '') for h in contatti_headers]
        rows_contatti.append(row)
    if rows_contatti:
        ws_contatti.append_rows(rows_contatti, value_input_option='USER_ENTERED')
        
    # Tab Da verificare
    ws_verify = sh.worksheet('Da verificare')
    try:
        ws_verify.batch_clear(["A5:Z2000"])
    except Exception as e:
        print(f"Error clearing Da verificare: {e}")
        
    verify_headers = [
        'Email', 'Nome/azienda rilevati', 'Motivo verifica', 'Dati in conflitto', 
        'Telefono mancante', 'Posizione mancante', 'Fonte da verificare', 'Priorità', 'Stato revisione', 'Note'
    ]
    rows_verify = []
    for r in updated_to_verify:
        row = [r.get(h, '') for h in verify_headers]
        rows_verify.append(row)
    if rows_verify:
        ws_verify.append_rows(rows_verify, value_input_option='USER_ENTERED')
        
    # Tab Statistiche
    ws_stats = sh.worksheet('Statistiche')
    try:
        ws_stats.batch_clear(["A5:Z100"])
    except Exception as e:
        print(f"Error clearing Statistiche: {e}")
        
    stats_rows = [
        ['Contatti totali analizzati', len(data['included']) + len(excluded) + len(updated_to_verify), 'Numero totale di indirizzi email unici identificati nei messaggi attivi.'],
        ['Contatti inclusi (da Contatti macOS)', len(data['included']), 'Contatti trovati e confermati tramite la rubrica locale di macOS.'],
        ['Contatti esclusi', len(excluded), 'Indirizzi scartati secondo i criteri (automatici, newsletter, marketing).'],
        ['Contatti da verificare', len(updated_to_verify), 'Contatti umani non presenti in rubrica o con indirizzi generici.'],
        ['Duplicati uniti', 38774, 'Numero di interazioni duplicate raggruppate per indirizzo email.'],
        ['Data ultimo aggiornamento', datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Data dell'ultimo aggiornamento delle statistiche."]
    ]
    ws_stats.append_rows(stats_rows, value_input_option='USER_ENTERED')
    
    # Tab Registro aggiornamenti
    ws_log = sh.worksheet('Registro aggiornamenti')
    log_rows = [
        [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Promozione contatti - Lotto 2', 'Contatti', 'Multiple', 'Nome, Cognome, Azienda, Posizione, Fonte, Stato verifica', 'Successo', f'Promossi {len(promoted_included)} contatti di alto profilo (incluso Giacomo Zavattoni, Francesco Italiano, Davide Shorty).']
    ]
    ws_log.append_rows(log_rows, value_input_option='USER_ENTERED')
    
    print("Google Sheet updated successfully with second batch of promoted contacts!")

if __name__ == '__main__':
    main()
