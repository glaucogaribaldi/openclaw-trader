import sqlite3
import pickle
import os
import re
from collections import defaultdict

def main():
    token_path = os.path.expanduser('~/.openclaw/google_sheets_token.pickle')
    pickle_path = '/Users/zava/.openclaw/workspace/data/preliminary_scan.pickle'
    
    with open(pickle_path, 'rb') as f:
        data = pickle.load(f)
        
    included = data['included']
    excluded = data['excluded']
    to_verify = data['to_verify']
    
    # Let's map email to verify record
    verify_map = {r['Email'].lower(): r for r in to_verify}
    
    # We need to compute message count for each to_verify email from the database
    conn = sqlite3.connect("/Users/zava/Library/Mail/V10/MailData/Envelope Index")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ROWID FROM mailboxes 
        WHERE url LIKE "%junk%" OR url LIKE "%spam%" OR url LIKE "%deleted%" OR url LIKE "%trash%" OR url LIKE "%cestino%" OR url LIKE "%indesiderata%" OR url LIKE "%drafts%"
    """)
    ex_mboxes = [r[0] for r in cursor.fetchall()]
    
    email_counts = defaultdict(int)
    
    # Senders count
    cursor.execute("""
        SELECT s_addr.address
        FROM messages m
        JOIN addresses s_addr ON m.sender = s_addr.ROWID
        WHERE m.mailbox NOT IN ({})
    """.format(",".join(map(str, ex_mboxes))))
    for r in cursor.fetchall():
        if r[0]:
            email_counts[r[0].lower()] += 1
            
    # Recipients count
    cursor.execute("""
        SELECT r_addr.address
        FROM recipients r
        JOIN addresses r_addr ON r.address = r_addr.ROWID
        WHERE r.message IN (
            SELECT ROWID FROM messages WHERE mbox_not_ex
        )
    """.replace("mbox_not_ex", f"mailbox NOT IN ({','.join(map(str, ex_mboxes))})"))
    for r in cursor.fetchall():
        if r[0]:
            email_counts[r[0].lower()] += 1
            
    # Sort to_verify by email counts
    sorted_verify = []
    for r in to_verify:
        email = r['Email'].lower()
        count = email_counts.get(email, 0)
        sorted_verify.append((count, r))
        
    sorted_verify.sort(key=lambda x: x[0], reverse=True)
    
    print("=== TOP 20 DA VERIFICARE BY INTERACTION FREQUENCY ===")
    for idx, (count, r) in enumerate(sorted_verify[:20]):
        print(f"{idx+1}. {r['Email']} | Name: {r['Nome/azienda rilevati']} | Msg count: {count} | Reason: {r['Motivo verifica']}")
        
if __name__ == '__main__':
    main()
