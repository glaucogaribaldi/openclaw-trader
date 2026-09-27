import os
import sqlite3
import json
import re
import pickle
from datetime import datetime
from collections import defaultdict
import subprocess

def fetch_contacts_jxa():
    jxa_script = """
    var contacts = Application("Contacts");
    var people = contacts.people;
    
    var ids = people.id();
    var firstNames = people.firstName();
    var lastNames = people.lastName();
    var organizations = people.organization();
    var jobTitles = people.jobTitle();
    var notes = people.note();
    var emails = people.emails.value();
    var phones = people.phones.value();
    
    var streets = [];
    var cities = [];
    var countries = [];
    try {
        streets = people.addresses.street();
        cities = people.addresses.city();
        countries = people.addresses.country();
    } catch(e) {}
    
    var groups = contacts.groups();
    var group_map = {};
    for (var g = 0; g < groups.length; g++) {
        var group = groups[g];
        var g_name = group.name() || "";
        try {
            var g_ids = group.people.id();
            for (var p_idx = 0; p_idx < g_ids.length; p_idx++) {
                var pid = g_ids[p_idx];
                if (!group_map[pid]) {
                    group_map[pid] = [];
                }
                group_map[pid].push(g_name);
            }
        } catch(e) {}
    }
    
    var results = [];
    for (var i = 0; i < ids.length; i++) {
        var pid = ids[i];
        results.push({
            id: pid,
            firstName: firstNames[i] || "",
            lastName: lastNames[i] || "",
            organization: organizations[i] || "",
            jobTitle: jobTitles[i] || "",
            note: notes[i] || "",
            emails: emails[i] || [],
            phones: phones[i] || [],
            streets: streets[i] || [],
            cities: cities[i] || [],
            countries: countries[i] || [],
            groups: group_map[pid] || []
        });
    }
    JSON.stringify(results);
    """
    p = subprocess.Popen(['osascript', '-l', 'JavaScript'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(input=jxa_script.encode('utf-8'))
    if err and err.strip():
        print("JXA Error fetching contacts:", err.decode('utf-8'))
        return []
    return json.loads(out.decode('utf-8'))

def normalize_email(email):
    if not email:
        return ""
    return email.strip().lower()

def clean_subject(subj):
    if not subj:
        return ""
    # Strip Re:, Fwd:, etc.
    return re.sub(r'^(re|fwd|i|r|ris|inoltrato|fw|reply):\s*', '', subj, flags=re.IGNORECASE).strip()

def is_automated_subject(subj):
    subj_lower = subj.lower()
    auto_keywords = [
        'ricevuta', 'notifica', 'alert', 'avviso', 'fattura', 'conferma', 'ordine', 'pagamento',
        'receipt', 'invoice', 'notification', 'ticket', 'backup', 'cron', 'status', 'build', 'deploy',
        'newsletter', 'offerta', 'promozione', 'coupon', 'sconto', 'promo', 'invito', 'evento',
        'registrazione', 'iscritt', 'benvenuto', 'welcome', 'unsubscribe', 'disiscriviti'
    ]
    return any(kw in subj_lower for kw in auto_keywords)

def main():
    print("Step 1: Fetching macOS Contacts...")
    contacts = fetch_contacts_jxa()
    print(f"Loaded {len(contacts)} contacts from Contacts app.")
    
    # Map email -> contact
    email_to_contact = {}
    for c in contacts:
        for em in c['emails']:
            norm = normalize_email(em)
            if norm:
                email_to_contact[norm] = c
                
    print("Step 2: Connecting to macOS Mail Envelope Index...")
    conn = sqlite3.connect("/Users/zava/Library/Mail/V10/MailData/Envelope Index")
    cursor = conn.cursor()
    
    # Fetch Mailboxes and Map
    cursor.execute("SELECT ROWID, url FROM mailboxes")
    mailboxes = {}
    excluded_mailbox_ids = set()
    draft_mailbox_ids = set()
    for rowid, url in cursor.fetchall():
        url_lower = url.lower()
        
        # Account mapping
        account = "iCloud"
        if "22d7fc7b-7d93-4693-b171-eb599f795de" in url_lower:
            account = "Totallyimported"
        elif "89d2cd85-b8ea-40bb-b0bc-ad7fc509ee05" in url_lower:
            account = "Totallyinnovation"
        elif "local://" in url_lower:
            account = "Local"
            
        friendly_folder = url.split('/')[-1]
        friendly_folder = friendly_folder.replace("%20", " ")
        
        is_excluded = False
        is_draft = False
        if any(k in url_lower for k in ['junk', 'spam', 'deleted', 'trash', 'cestino', 'indesiderata']):
            is_excluded = True
            excluded_mailbox_ids.add(rowid)
        elif 'drafts' in url_lower:
            is_draft = True
            draft_mailbox_ids.add(rowid)
            
        mailboxes[rowid] = {
            'account': account,
            'folder': friendly_folder,
            'is_excluded': is_excluded,
            'is_draft': is_draft
        }
        
    print(f"Mapped {len(mailboxes)} mailboxes.")
    
    # Query all active messages
    # Join senders and recipients
    # Senders: join addresses on m.sender = s_addr.ROWID
    print("Step 3: Querying messages...")
    
    mailbox_filter = ""
    if excluded_mailbox_ids or draft_mailbox_ids:
        all_ex = excluded_mailbox_ids | draft_mailbox_ids
        mailbox_filter = f"WHERE m.mailbox NOT IN ({','.join(map(str, all_ex))})"
        
    query = f"""
        SELECT m.ROWID, m.date_sent, m.date_received, m.mailbox, m.list_id_hash,
               s_addr.address, s_addr.comment,
               subj.subject
        FROM messages m
        LEFT JOIN addresses s_addr ON m.sender = s_addr.ROWID
        LEFT JOIN subjects subj ON m.subject = subj.ROWID
        {mailbox_filter}
    """
    
    cursor.execute(query)
    messages_data = cursor.fetchall()
    print(f"Retrieved {len(messages_data)} active messages.")
    
    # Group interactions by normalized email address
    # We will track: sender and recipients (To, CC, BCC)
    # email_stats = { email: { 'names': set(), 'dates': [], 'mailboxes': set(), 'subjects': [], 'list_id': False } }
    email_stats = defaultdict(lambda: {
        'names': set(),
        'dates': [],
        'mailboxes': set(),
        'subjects': [],
        'list_id': False
    })
    
    # To do this efficiently, we will do a single query for recipients of ALL retrieved messages
    # Or query by chunks
    print("Step 4: Fetching recipients for active messages...")
    cursor.execute("""
        SELECT r.message, r_addr.address, r_addr.comment, r.type
        FROM recipients r
        JOIN addresses r_addr ON r.address = r_addr.ROWID
    """)
    recipients_data = cursor.fetchall()
    
    # Map message ID -> list of recipients
    msg_to_recipients = defaultdict(list)
    for msg_id, r_email, r_name, r_type in recipients_data:
        msg_to_recipients[msg_id].append((r_email, r_name, r_type))
        
    print("Step 5: Processing interactions...")
    # Add sender and recipient interactions
    for m_id, d_sent, d_rec, m_box, list_id_hash, s_email, s_name, subj in messages_data:
        m_info = mailboxes.get(m_box, {'account': 'Unknown', 'folder': 'Unknown'})
        mbox_str = f"{m_info['account']}/{m_info['folder']}"
        
        # Timestamp logic
        timestamp = d_rec if d_rec else d_sent
        if not timestamp:
            continue
        try:
            dt = datetime.fromtimestamp(timestamp)
        except Exception:
            dt = datetime.now()
            
        # Clean subject
        cleaned_subj = clean_subject(subj)
        
        # 1. Process Sender
        norm_s = normalize_email(s_email)
        if norm_s:
            stats = email_stats[norm_s]
            if s_name:
                stats['names'].add(s_name.strip())
            stats['dates'].append(dt)
            stats['mailboxes'].add(mbox_str)
            if cleaned_subj:
                stats['subjects'].append(cleaned_subj)
            if list_id_hash != 0:
                stats['list_id'] = True
                
        # 2. Process Recipients
        for r_email, r_name, r_type in msg_to_recipients.get(m_id, []):
            norm_r = normalize_email(r_email)
            if norm_r:
                stats = email_stats[norm_r]
                if r_name:
                    stats['names'].add(r_name.strip())
                stats['dates'].append(dt)
                stats['mailboxes'].add(mbox_str)
                if cleaned_subj:
                    stats['subjects'].append(cleaned_subj)
                if list_id_hash != 0:
                    stats['list_id'] = True
                    
    print(f"Found {len(email_stats)} unique email addresses.")
    
    # Step 6: Classification
    included_records = []
    excluded_records = []
    to_verify_records = []
    
    # Regex exclusion rules for email address
    exclude_email_regex = re.compile(
        r'(no-reply|noreply|do-not-reply|donotreply|mailer-daemon|postmaster|bounce|automated|notification|notify|alert|daemon|system|support|info|admin|amministrazione|news|newsletter|mailing|marketing|promo|billing|fattura|invoice|accounts|help|ufficio)',
        re.IGNORECASE
    )
    
    strict_exclude_email_regex = re.compile(
        r'(no-reply|noreply|do-not-reply|donotreply|mailer-daemon|postmaster|bounce|automated|notification|notify|alert|daemon|system)',
        re.IGNORECASE
    )
    
    # Let's categorize each email address
    for email, stats in email_stats.items():
        domain = email.split('@')[-1] if '@' in email else ""
        
        # Friendly name
        display_name = ""
        if stats['names']:
            # Find the most frequent or longest name
            display_name = max(stats['names'], key=len)
            
        # Dates
        first_inter = min(stats['dates']).isoformat() if stats['dates'] else ""
        last_inter = max(stats['dates']).isoformat() if stats['dates'] else ""
        num_emails = len(stats['dates'])
        mailboxes_list = ", ".join(sorted(list(stats['mailboxes'])))
        
        # Check matched contact from Contacts app
        matched_contact = email_to_contact.get(email)
        
        # Default category and reasons
        is_excluded = False
        ex_cat = ""
        ex_reason = ""
        ex_rule = ""
        
        # 1. Check strict automated emails (always exclude!)
        if strict_exclude_email_regex.search(email):
            is_excluded = True
            ex_cat = "Indirizzi automatici"
            ex_reason = f"L'indirizzo contiene parole chiave automatiche."
            ex_rule = "rule_strict_automated_email"
            
        # 2. Check mailing list header
        elif stats['list_id']:
            is_excluded = True
            ex_cat = "Newsletter/Mailing List"
            ex_reason = "Il messaggio contiene l'intestazione List-ID o segnale di mailing list."
            ex_rule = "rule_list_id_hash"
            
        # 3. Check newsletter/marketing patterns in email address
        elif re.search(r'(news|newsletter|mailing|marketing|promo|offers|campagne|coupon)', email):
            is_excluded = True
            ex_cat = "Newsletter/Marketing"
            ex_reason = "L'indirizzo contiene parole chiave promozionali o di newsletter."
            ex_rule = "rule_promo_email"
            
        # 4. Check if all subjects look automated
        elif num_emails > 0 and all(is_automated_subject(s) for s in stats['subjects']):
            # If we don't have a contact saved, exclude
            if not matched_contact:
                is_excluded = True
                ex_cat = "Ricevute/Notifiche/Marketing"
                ex_reason = "Tutti i messaggi scambiati contengono argomenti automatizzati o commerciali."
                ex_rule = "rule_all_subjects_automated"
                
        # Let's check if excluded
        if is_excluded:
            excluded_records.append({
                'Email': email,
                'Nome visualizzato': display_name,
                'Dominio': domain,
                'Categoria esclusione': ex_cat,
                'Motivo': ex_reason,
                'Numero messaggi': num_emails,
                'Prima rilevazione': first_inter,
                'Ultima rilevazione': last_inter,
                'Regola applicata': ex_rule,
                'Note': f"Oggetti campionati: {', '.join(stats['subjects'][:3])}"
            })
            continue
            
        # Now let's handle non-excluded emails
        # If we have a match in Contacts, it's included!
        if matched_contact:
            # Reconstruct details from matched contact
            nome = matched_contact['firstName']
            cognome = matched_contact['lastName']
            nome_completo = f"{nome} {cognome}".strip() or display_name or matched_contact['organization']
            
            other_emails = "; ".join([em for em in matched_contact['emails'] if normalize_email(em) != email])
            phone = "; ".join(matched_contact['phones'])
            azienda = matched_contact['organization']
            posizione = matched_contact['jobTitle']
            
            # Postal address
            city_country = ""
            if matched_contact['cities']:
                city = matched_contact['cities'][0]
                country = matched_contact['countries'][0] if matched_contact['countries'] else ""
                city_country = f"{city}, {country}".strip(", ")
            elif matched_contact['countries']:
                city_country = matched_contact['countries'][0]
                
            address = "; ".join(matched_contact['streets'])
            groups = ", ".join(matched_contact['groups'])
            note = matched_contact['note']
            
            # Check completeness / need verification
            # If role-based address (info@, support@, etc.) we keep it in Da verificare if we are not sure,
            # but since they saved it in Contacts, it is Confermato!
            status_ver = "Confermato"
            affidabilita = "Alta"
            
            included_records.append({
                'ID contatto': matched_contact['id'],
                'Nome': nome,
                'Cognome': cognome,
                'Nome completo': nome_completo,
                'Email principale': email,
                'Altre email': other_emails,
                'Numero di telefono': phone,
                'Azienda': azienda,
                'Posizione lavorativa': posizione,
                'Fonte posizione': 'Contatti',
                'URL fonte': '',
                'Città/Paese': city_country,
                'Indirizzo': address,
                'Gruppi Contatti': groups,
                'Numero email scambiate': num_emails,
                'Prima interazione': first_inter,
                'Ultima interazione': last_inter,
                'Account/casella coinvolta': mailboxes_list,
                'Dominio email': domain,
                'Tipo contatto': 'Professionale' if azienda else 'Privato',
                'Stato verifica': status_ver,
                'Affidabilità dati': affidabilita,
                'Data ultima verifica': datetime.now().strftime("%Y-%m-%d"),
                'Note': note,
                'Ultimo aggiornamento OpenClaw': datetime.now().isoformat()
            })
            
        else:
            # No contact matched!
            # Is it role-based (info@, support@, amministrazione@)?
            is_role_based = re.match(r'^(info|support|amministrazione|admin|sales|marketing|commerciale|contatti|help|ufficio|billing|fatturazione|invoice|accounts)@', email, re.IGNORECASE)
            
            if is_role_based:
                # Add to "Da verificare"
                to_verify_records.append({
                    'Email': email,
                    'Nome/azienda rilevati': display_name,
                    'Motivo verifica': "Indirizzo di ruolo (info/support/amministrazione) senza contatto in Contatti.",
                    'Dati in conflitto': "",
                    'Telefono mancante': "Sì",
                    'Posizione mancante': "Sì",
                    'Fonte da verificare': "Web / LinkedIn",
                    'Priorità': "Media",
                    'Stato revisione': "In attesa",
                    'Note': f"Dominio: {domain}. Oggetti campionati: {', '.join(stats['subjects'][:3])}"
                })
            else:
                # It is a normal human address, but not saved in Contacts!
                # Let's put it in included_records, but mark state as "Da verificare" (as requested: "Se il caso è dubbio, o incompleto, inseriscilo in Da verificare")
                # Wait, let's see: should it go directly into the "Da verificare" sheet or "Contatti" with state "Da verificare"?
                # "Scrivi i risultati nel tab 'Contatti', rispettando tutte le colonne già predisposte. Inserisci i casi incompleti, ambigui o con dati conflittuali in 'Da verificare'."
                # Let's add it to "Da verificare" worksheet so Giacomo can review it!
                to_verify_records.append({
                    'Email': email,
                    'Nome/azienda rilevati': display_name,
                    'Motivo verifica': "Contatto umano non salvato in Contatti dell'app macOS.",
                    'Dati in conflitto': "",
                    'Telefono mancante': "Sì",
                    'Posizione mancante': "Sì",
                    'Fonte da verificare': "LinkedIn",
                    'Priorità': "Alta",
                    'Stato revisione': "In attesa",
                    'Note': f"Oggetti campionati: {', '.join(stats['subjects'][:3])}"
                })
                
    # Save the scanned records locally to pickles or JSON files so we can import them on confirmation!
    os.makedirs('/Users/zava/.openclaw/workspace/data', exist_ok=True)
    with open('/Users/zava/.openclaw/workspace/data/preliminary_scan.pickle', 'wb') as f:
        pickle.dump({
            'included': included_records,
            'excluded': excluded_records,
            'to_verify': to_verify_records
        }, f)
        
    print("\n=== SCAN SUMMARY ===")
    print(f"Total Unique Addresses Found: {len(email_stats)}")
    print(f"Included (Confirmed in Contacts): {len(included_records)}")
    print(f"Excluded (Mailing lists, system-generated, marketing): {len(excluded_records)}")
    print(f"To Verify (Ambiguous, role-based, or not in Contacts): {len(to_verify_records)}")
    
    # Preview 20 records
    print("\n=== PREVIEW (20 RECORDS) ===")
    all_previews = []
    for r in included_records[:10]:
        all_previews.append(f"INCLUSO: {r['Nome completo']} <{r['Email principale']}> | {r['Azienda']} | {r['Numero email scambiate']} email")
    for r in to_verify_records[:5]:
        all_previews.append(f"DA VERIFICARE: {r['Nome/azienda rilevati']} <{r['Email']}> | {r['Motivo verifica']}")
    for r in excluded_records[:5]:
        all_previews.append(f"ESCLUSO: <{r['Email']}> | {r['Categoria esclusione']} | {r['Motivo']}")
        
    for p in all_previews[:20]:
        print("-", p)

if __name__ == '__main__':
    main()
