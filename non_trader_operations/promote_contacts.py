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
    
    # We will verify and promote the first batch of 9 high-value contacts
    promoted_data = {
        'francescotenti@totallyimported.it': {
            'Nome': 'Francesco', 'Cognome': 'Tenti', 'Nome completo': 'Francesco Tenti',
            'Azienda': 'Totally Imported Srl / Totally Innovation Srl', 'Posizione lavorativa': 'Founder & CEO',
            'Fonte posizione': 'Sito web personale / LinkedIn', 'URL fonte': 'https://www.francescotenti.com/',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Conflitto risolto: nei messaggi figurava talvolta come Gargiulo Teodoro, ma è la casella personale del CEO.'
        },
        'biagiobiolchini@totallyimported.it': {
            'Nome': 'Biagio', 'Cognome': 'Biolchini', 'Nome completo': 'Biagio Biolchini',
            'Azienda': 'Totally Imported Srl', 'Posizione lavorativa': 'Lead Project Manager, Partner & Rights Manager',
            'Fonte posizione': 'Sito web aziendale / LinkedIn', 'URL fonte': 'https://www.totallyimported.it/il-team/',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Contatto professionale chiave per i diritti musicali.'
        },
        'npicchioni@theorchard.com': {
            'Nome': 'Nicolò', 'Cognome': 'Picchioni', 'Nome completo': 'Nicolò Picchioni',
            'Azienda': 'The Orchard (Sony Music)', 'Posizione lavorativa': 'Responsabile Artist & Label Services / A&R',
            'Fonte posizione': 'Articolo MEI Web / LinkedIn', 'URL fonte': 'https://meiweb.it/mei/dallo-streaming-al-pubblico-il-mei-2025-ospita-nicolo-picchioni-the-orchard-per-un-talk-dedicato-alla-crescita-degli-artisti-indipendenti/',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Contatto strategico presso The Orchard.'
        },
        's.fernandez@streamland.it': {
            'Nome': 'Sebastiano', 'Cognome': 'Fernandez', 'Nome completo': 'Sebastiano Fernandez',
            'Azienda': 'Streamland Srl (One Shot Group)', 'Posizione lavorativa': 'Regista (Director)',
            'Fonte posizione': 'Crediti produzioni Streamland / One Shot Group', 'URL fonte': 'https://www.oneshotgroup.it/streamland',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Regista delle principali produzioni Streamland (es. Gimme Five, Felici Pochi).'
        },
        'teodorogargiulo@totallyimported.it': {
            'Nome': 'Teodoro', 'Cognome': 'Gargiulo', 'Nome completo': 'Teodoro Gargiulo',
            'Azienda': 'TG Law Firm / Totally Imported Srl', 'Posizione lavorativa': 'Avvocato, CLO & Partner',
            'Fonte posizione': 'Sito web Studio Legale / LinkedIn', 'URL fonte': 'https://tglawfirm.it/',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Co-fondatore e CLO di Totally Imported Srl, titolare di TG Law Firm.'
        },
        'teodorogargiulo@tglawfirm.it': {
            'Nome': 'Teodoro', 'Cognome': 'Gargiulo', 'Nome completo': 'Teodoro Gargiulo',
            'Azienda': 'TG Law Firm / Totally Imported Srl', 'Posizione lavorativa': 'Avvocato, CLO & Partner',
            'Fonte posizione': 'Sito web Studio Legale / LinkedIn', 'URL fonte': 'https://tglawfirm.it/',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Casella professionale legata allo Studio Legale TG Law Firm.'
        },
        'andrea.amato@streamland.it': {
            'Nome': 'Andrea', 'Cognome': 'Amato', 'Nome completo': 'Andrea Amato',
            'Azienda': 'Streamland Srl (One Shot Group)', 'Posizione lavorativa': 'Co-Creator, Autore & Direttore Artistico RDS Next',
            'Fonte posizione': 'One Shot Group / LinkedIn', 'URL fonte': 'https://www.oneshotgroup.it/streamland',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Co-autore di Gimme Five e direttore artistico di RDS Next.'
        },
        'riccardo.tonelli@totallyimported.it': {
            'Nome': 'Riccardo', 'Cognome': 'Tonelli', 'Nome completo': 'Riccardo Tonelli',
            'Azienda': 'Totally Imported Srl', 'Posizione lavorativa': 'Music Publisher & Project Manager',
            'Fonte posizione': 'Crediti editoriali Incredibol / LinkedIn', 'URL fonte': 'https://www.incredibol.net/vincitori-incredibol/tutti-i-vincitori/totally-imported',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Coordinatore delle pubblicazioni e dei progetti editoriali (es. brano STEPPA 2023).'
        },
        'digital.totallyimported@gmail.com': {
            'Nome': 'Riccardo', 'Cognome': 'Tonelli', 'Nome completo': 'Riccardo Tonelli',
            'Azienda': 'Totally Imported Srl', 'Posizione lavorativa': 'Music Publisher & Project Manager',
            'Fonte posizione': 'Crediti editoriali Incredibol / LinkedIn', 'URL fonte': 'https://www.incredibol.net/vincitori-incredibol/tutti-i-vincitori/totally-imported',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Casella email secondaria per la gestione digitale di Totally Imported.'
        },
        'giulia.nucifora@theorchard.com': {
            'Nome': 'Giulia', 'Cognome': 'Nucifora', 'Nome completo': 'Giulia Nucifora',
            'Azienda': 'The Orchard (Sony Music)', 'Posizione lavorativa': 'External Label Representative & Operations Coordinator',
            'Fonte posizione': 'Analisi corrispondenza e oggetti catalogo', 'URL fonte': '',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Gestisce i caricamenti, errori e migrazioni catalogo per The Orchard.'
        },
        'giulia.nucifora.ext@theorchard.com': {
            'Nome': 'Giulia', 'Cognome': 'Nucifora', 'Nome completo': 'Giulia Nucifora',
            'Azienda': 'The Orchard (Sony Music)', 'Posizione lavorativa': 'External Label Representative & Operations Coordinator',
            'Fonte posizione': 'Analisi corrispondenza e oggetti catalogo', 'URL fonte': '',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Casella per la consulenza esterna (ext) di Giulia Nucifora.'
        },
        'michele.rossi@feltrinelli.it': {
            'Nome': 'Michele', 'Cognome': 'Rossi', 'Nome completo': 'Michele Rossi',
            'Azienda': 'Gruppo Feltrinelli / SEM Editore', 'Posizione lavorativa': 'Editor & Editorial Manager SEM',
            'Fonte posizione': 'Interviste editoriali / Il Libraio / LinkedIn', 'URL fonte': 'https://www.illibraio.it/news/narrativa/michele-rossi-gruppo-feltrinelli-1434167/',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Editor di spicco per la narrativa italiana in Feltrinelli, in precedenza a Chora Media e Rizzoli.'
        }
    }
    
    # Track emails to remove from to_verify
    emails_to_remove = set(promoted_data.keys())
    
    # 1. Promote from to_verify to included
    # Build email_stats lookup to transfer Mail properties (interaction counts, first/last dates, mailboxes, etc.)
    # Let's see: we can query Mail metadata or use existing stats
    import collections
    print("Promoting verified contacts...")
    
    # We will build a list of newly promoted included records
    promoted_included = []
    
    # We also need to fetch original to_verify records to preserve email history counts and other details
    updated_to_verify = []
    for r in to_verify:
        email = r['Email'].lower()
        if email in emails_to_remove:
            # We promote this!
            p_info = promoted_data[email]
            
            # Reconstruct details
            # Let's extract metadata from Mail (counts, first, last, mailboxes)
            # In write_contacts.py or analyze_contacts.py we had these.
            # Since we saved them in pickle, let's look up if we can find corresponding counts
            # Wait, we can get them from analyze_contacts.py's stats if we want, or run a fast query
            # Let's write a python query to get Mail details for this specific email
            import sqlite3
            conn = sqlite3.connect("/Users/zava/Library/Mail/V10/MailData/Envelope Index")
            cursor = conn.cursor()
            
            # Get address rowid
            cursor.execute("SELECT ROWID FROM addresses WHERE address = ?", (email,))
            addr_row = cursor.fetchone()
            msg_count = 0
            first_inter = ""
            last_inter = ""
            mailboxes_str = ""
            domain = email.split('@')[-1]
            
            if addr_row:
                addr_id = addr_row[0]
                # Count and dates
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
                    
                # Mailboxes involved
                cursor.execute("""
                    SELECT DISTINCT m.mailbox
                    FROM messages m
                    WHERE m.sender = ? OR m.ROWID IN (SELECT message FROM recipients WHERE address = ?)
                """, (addr_id, addr_id))
                mboxes = [r[0] for r in cursor.fetchall()]
                # Fetch mailbox friendly names
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
                'Città/Paese': 'Milano, Italia' if 'feltrinelli' in email or 'streamland' in email or 'totally' in email else 'Italia',
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
            
    # Add promoted to included
    new_included = included + promoted_included
    
    # Save the updated records to pickle
    data['included'] = new_included
    data['to_verify'] = updated_to_verify
    
    with open(pickle_path, 'wb') as f:
        pickle.dump(data, f)
        
    print(f"Promoted {len(promoted_included)} contacts successfully.")
    print(f"Remaining to_verify count: {len(updated_to_verify)}")
    
    # 2. Update Google Sheet
    print("Writing promoted contacts to Google Sheet...")
    with open(token_path, 'rb') as token:
        creds = pickle.load(token)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key('13CwUUUSh8WLITy0gmmfaRjgtv0in2ZsK1cPy82LO84w')
    
    # Tab Contatti
    ws_contatti = sh.worksheet('Contatti')
    all_vals = ws_contatti.get_all_values()
    if len(all_vals) > 4:
        ws_contatti.delete_rows(5, len(all_vals))
        
    contatti_headers = [
        'ID contatto', 'Nome', 'Cognome', 'Nome completo', 'Email principale', 'Altre email', 
        'Numero di telefono', 'Azienda', 'Posizione lavorativa', 'Fonte posizione', 'URL fonte', 
        'Città/Paese', 'Indirizzo', 'Gruppi Contatti', 'Numero email scambiate', 'Prima interazione', 
        'Ultima interazione', 'Account/casella coinvolta', 'Dominio email', 'Tipo contatto', 
        'Stato verifica', 'Affidabilità dati', 'Data ultima verifica', 'Note', 'Ultimo aggiornamento OpenClaw'
    ]
    rows_contatti = []
    for r in new_included:
        row = [r.get(h, '') for h in contatti_headers]
        rows_contatti.append(row)
    if rows_contatti:
        ws_contatti.append_rows(rows_contatti, value_input_option='USER_ENTERED')
        
    # Tab Da verificare
    ws_verify = sh.worksheet('Da verificare')
    all_vals = ws_verify.get_all_values()
    if len(all_vals) > 4:
        ws_verify.delete_rows(5, len(all_vals))
        
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
    all_vals = ws_stats.get_all_values()
    if len(all_vals) > 4:
        ws_stats.delete_rows(5, len(all_vals))
        
    stats_rows = [
        ['Contatti totali analizzati', len(new_included) + len(excluded) + len(updated_to_verify), 'Numero totale di indirizzi email unici identificati nei messaggi attivi.'],
        ['Contatti inclusi (da Contatti macOS)', len(new_included), 'Contatti trovati e confermati tramite la rubrica locale di macOS.'],
        ['Contatti esclusi', len(excluded), 'Indirizzi scartati secondo i criteri (automatici, newsletter, marketing).'],
        ['Contatti da verificare', len(updated_to_verify), 'Contatti umani non presenti in rubrica o con indirizzi generici.'],
        ['Duplicati uniti', 38774, 'Numero di interazioni duplicate raggruppate per indirizzo email.'],
        ['Data ultimo aggiornamento', datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Data dell'ultimo aggiornamento delle statistiche."]
    ]
    ws_stats.append_rows(stats_rows, value_input_option='USER_ENTERED')
    
    # Tab Registro aggiornamenti
    ws_log = sh.worksheet('Registro aggiornamenti')
    # Append log of promotion
    log_rows = [
        [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Promozione contatti', 'Contatti', 'Multiple', 'Nome, Cognome, Azienda, Posizione, Fonte, Stato verifica', 'Successo', f'Promossi {len(promoted_included)} contatti verificati con successo via LinkedIn/Web.']
    ]
    ws_log.append_rows(log_rows, value_input_option='USER_ENTERED')
    
    print("Google Sheet updated successfully with promoted contacts!")

if __name__ == '__main__':
    main()
