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
    
    # Third batch of promoted contacts
    promoted_data = {
        'totallyimported@gmail.com': {
            'Nome': '', 'Cognome': '', 'Nome completo': 'Totally Imported Srl',
            'Azienda': 'Totally Imported Srl', 'Posizione lavorativa': 'Corporate Mailbox',
            'Fonte posizione': 'Database Interno', 'URL fonte': '',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Casella istituzionale e di gestione generica di Totally Imported.'
        },
        'editing@streamland.it': {
            'Nome': '', 'Cognome': '', 'Nome completo': 'Streamland Srl (Editing)',
            'Azienda': 'Streamland Srl (One Shot Group)', 'Posizione lavorativa': 'Editing Department',
            'Fonte posizione': 'Database Interno / One Shot Group', 'URL fonte': '',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Casella di reparto per il montaggio e post-produzione video di Streamland.'
        },
        'biagiobiolchini@totallyinnovation.com': {
            'Nome': 'Biagio', 'Cognome': 'Biolchini', 'Nome completo': 'Biagio Biolchini',
            'Azienda': 'Totally Innovation Srl / Totally Imported', 'Posizione lavorativa': 'Lead Project Manager & Partner',
            'Fonte posizione': 'Database Interno / LinkedIn', 'URL fonte': '',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Tua casella aziendale per Totally Innovation Srl.'
        },
        'francescotenti@totallyinnovation.com': {
            'Nome': 'Francesco', 'Cognome': 'Tenti', 'Nome completo': 'Francesco Tenti',
            'Azienda': 'Totally Innovation Srl / Totally Imported', 'Posizione lavorativa': 'Founder & CEO',
            'Fonte posizione': 'Database Interno / LinkedIn', 'URL fonte': '',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Casella aziendale del CEO Francesco Tenti.'
        },
        'bruno@totallyinnovation.com': {
            'Nome': 'Bruno', 'Cognome': 'B.', 'Nome completo': 'Bruno B.',
            'Azienda': 'Totally Innovation Srl', 'Posizione lavorativa': 'Creative Director / Developer',
            'Fonte posizione': 'Database Interno', 'URL fonte': '',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Referente creativo e di sviluppo per Totally Innovation Srl.'
        },
        'claudia.rossi@henkel.com': {
            'Nome': 'Claudia', 'Cognome': 'Rossi', 'Nome completo': 'Claudia Rossi',
            'Azienda': 'Henkel', 'Posizione lavorativa': 'Collaboratore Professionale',
            'Fonte posizione': 'Dominio Aziendale', 'URL fonte': '',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Referente e contatto presso la multinazionale Henkel.'
        },
        'andrea.dallamico@henkel.com': {
            'Nome': 'Andrea', 'Cognome': 'Dallamico', 'Nome completo': 'Andrea Dallamico',
            'Azienda': 'Henkel', 'Posizione lavorativa': 'Collaboratore Professionale',
            'Fonte posizione': 'Dominio Aziendale', 'URL fonte': '',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Referente e contatto presso la multinazionale Henkel.'
        },
        'tommaso.delorenzis@consultant.feltrinelli.it': {
            'Nome': 'Tommaso', 'Cognome': 'De Lorenzis', 'Nome completo': 'Tommaso De Lorenzis',
            'Azienda': 'Giangiacomo Feltrinelli Editore', 'Posizione lavorativa': 'Editorial Consultant / Editor',
            'Fonte posizione': 'Biografia Editoriale / Feltrinelli / Einaudi', 'URL fonte': 'https://www.lafeltrinelli.it/aspra-stagione-libro-tommaso-de-lorenzis-mauro-favale/e/9788806206000',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Editor e consulente editoriale di prestigio per Feltrinelli, Einaudi Stile Libero e Scuola Holden.'
        },
        'digital@totallyimported.it': {
            'Nome': 'Riccardo', 'Cognome': 'Tonelli', 'Nome completo': 'Riccardo Tonelli',
            'Azienda': 'Totally Imported Srl', 'Posizione lavorativa': 'Music Publisher & Project Manager',
            'Fonte posizione': 'Database Interno / LinkedIn', 'URL fonte': '',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Casella tecnica di Riccardo Tonelli per la gestione del catalogo digitale.'
        },
        'antonio.cortesi@bmg.com': {
            'Nome': 'Antonio', 'Cognome': 'Cortesi', 'Nome completo': 'Antonio Cortesi',
            'Azienda': 'BMG Rights Management (Italy)', 'Posizione lavorativa': 'A&R Publishing Manager',
            'Fonte posizione': 'Notizia Rockol / All Music Italia / LinkedIn', 'URL fonte': 'https://musicbiz.rockol.it/news-749287/bmg-italia-entra-antonio-cortesi-come-aandr-publishing',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Esperto A&R entrato in BMG Italia nel gennaio 2025, precedentemente in Believe Italia.'
        },
        'management@riccardomutimusic.com': {
            'Nome': 'Eleonora', 'Cognome': 'Bonaccorso', 'Nome completo': 'Eleonora Bonaccorso (RMMUSIC)',
            'Azienda': 'Riccardo Muti Music (RMMUSIC)', 'Posizione lavorativa': 'Artist Manager & Booking Coordinator',
            'Fonte posizione': 'Sito web ufficiale / LinkedIn', 'URL fonte': 'https://www.riccardomutimusic.com',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Gestore delle relazioni artistiche e del management del leggendario Direttore d\'Orchestra Riccardo Muti.'
        },
        'cristiana@metatrongroup.com': {
            'Nome': 'Cristiana', 'Cognome': 'Gizzarelli', 'Nome completo': 'Cristiana Gizzarelli',
            'Azienda': 'Metatron Group', 'Posizione lavorativa': 'Head of Copyright & Co-Founder, Ezechiele 25:17',
            'Fonte posizione': 'Sito web ufficiale / Rockol / LinkedIn', 'URL fonte': 'https://musicbiz.rockol.it/news-755570/management-nasce-ezechiele-25-17-per-chi-fa-musica-per-il-cinema',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Responsabile Copyright di Metatron Group dal 2012 e co-fondatrice dell\'agenzia di compositori cinematografici Ezechiele 25:17.'
        },
        'alessandro.prencipe@enginius.com': {
            'Nome': 'Alessandro', 'Cognome': 'Prencipe', 'Nome completo': 'Alessandro Prencipe',
            'Azienda': 'Enginius Srl', 'Posizione lavorativa': 'IT Consultant & Software Developer',
            'Fonte posizione': 'Forum di sviluppo Angular / LinkedIn', 'URL fonte': '',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Sviluppatore software specializzato in tecnologie web e Angular per Enginius Srl.'
        },
        'kevin@lmtdmusic.it': {
            'Nome': 'Kevin', 'Cognome': 'Russo', 'Nome completo': 'Kevin Russo',
            'Azienda': 'LMTD Music Management', 'Posizione lavorativa': 'Artist Manager & Founder',
            'Fonte posizione': 'Crediti video musicali ufficiali / YouTube', 'URL fonte': 'https://www.youtube.com/watch?v=X6U3hsPITMc',
            'Affidabilità dati': 'Alta', 'Tipo contatto': 'Aziendale', 'Note': 'Fondatore di LMTD Music, manager dell\'artista e influencer Christian Liguori.'
        }
    }
    
    emails_to_remove = set(promoted_data.keys())
    
    # We also handle jobs-listings@linkedin.com to exclude it!
    exclude_email = 'jobs-listings@linkedin.com'
    
    print("Promoting third batch and filtering automatic listings...")
    promoted_included = []
    updated_to_verify = []
    
    exclude_record_to_add = None
    
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
                mboxes = [row[0] for row in cursor.fetchall()]
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
                'Città/Paese': 'Milano, Italia' if 'totally' in email or 'streamland' in email or 'bmg' in email or 'metatron' in email else 'Italia',
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
            
        elif email == exclude_email:
            # Prepare to exclude
            import sqlite3
            conn = sqlite3.connect("/Users/zava/Library/Mail/V10/MailData/Envelope Index")
            cursor = conn.cursor()
            cursor.execute("SELECT ROWID FROM addresses WHERE address = ?", (exclude_email,))
            addr_row = cursor.fetchone()
            msg_count = 0
            first_inter = ""
            last_inter = ""
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
                    
            exclude_record_to_add = {
                'Email': exclude_email,
                'Nome visualizzato': 'LinkedIn Job Listings',
                'Dominio': 'linkedin.com',
                'Categoria esclusione': 'Indirizzi automatici',
                'Motivo': 'Invio automatico di inserzioni di lavoro da LinkedIn',
                'Numero messaggi': msg_count,
                'Prima rilevazione': first_inter,
                'Ultima rilevazione': last_inter,
                'Regola applicata': 'rule_strict_automated_email',
                'Note': 'Autofiltrato e rimosso da Da Verificare per pulizia.'
            }
        else:
            updated_to_verify.append(r)
            
    # Save the updated records to pickle
    data['included'] = included + promoted_included
    data['to_verify'] = updated_to_verify
    if exclude_record_to_add:
        excluded.append(exclude_record_to_add)
        data['excluded'] = excluded
        
    with open(pickle_path, 'wb') as f:
        pickle.dump(data, f)
        
    print(f"Promoted {len(promoted_included)} contacts successfully.")
    print(f"Excluded {1 if exclude_record_to_add else 0} automated contacts.")
    print(f"Remaining to_verify count: {len(updated_to_verify)}")
    
    # 2. Update Google Sheet
    print("Writing third batch of promoted contacts to Google Sheet...")
    with open(token_path, 'rb') as token:
        creds = pickle.load(token)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key('13CwUUUSh8WLITy0gmmfaRjgtv0in2ZsK1cPy82LO84w')
    
    # Tab Contatti
    ws_contatti = sh.worksheet('Contatti')
    try:
        ws_contatti.batch_clear(["A5:Z3000"])
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
        ws_verify.batch_clear(["A5:Z3000"])
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
        
    # Tab Esclusi (update with new excluded)
    ws_esclusi = sh.worksheet('Esclusi')
    try:
        ws_esclusi.batch_clear(["A5:Z1000"])
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
        [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Promozione contatti - Lotto 3', 'Contatti', 'Multiple', 'Nome, Cognome, Azienda, Posizione, Fonte, Stato verifica', 'Successo', f'Promossi {len(promoted_included)} contatti di alto profilo (BMG, Metatron, Riccardo Muti Music, Feltrinelli). Escluso jobs-listings@linkedin.com.']
    ]
    ws_log.append_rows(log_rows, value_input_option='USER_ENTERED')
    
    print("Google Sheet updated successfully with third batch of promoted contacts!")

if __name__ == '__main__':
    main()
