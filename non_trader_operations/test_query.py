import sqlite3
from collections import defaultdict
from datetime import datetime

def main():
    conn = sqlite3.connect("/Users/zava/Library/Mail/V10/MailData/Envelope Index")
    cursor = conn.cursor()
    
    # 1. Fetch Mailboxes
    cursor.execute("SELECT ROWID, url, total_count FROM mailboxes")
    mailboxes = {}
    excluded_mailbox_ids = set()
    draft_mailbox_ids = set()
    for rowid, url, count in cursor.fetchall():
        url_lower = url.lower()
        friendly_name = url.split('/')[-1]
        
        # Classification
        is_excluded = False
        is_draft = False
        if any(k in url_lower for k in ['junk', 'spam', 'deleted', 'trash', 'cestino', 'indesiderata']):
            is_excluded = True
            excluded_mailbox_ids.add(rowid)
        elif 'drafts' in url_lower:
            is_draft = True
            draft_mailbox_ids.add(rowid)
            
        mailboxes[rowid] = {
            'url': url,
            'friendly_name': friendly_name,
            'count': count,
            'is_excluded': is_excluded,
            'is_draft': is_draft
        }
        
    print(f"Total mailboxes: {len(mailboxes)}")
    print(f"Excluded mailboxes: {len(excluded_mailbox_ids)}")
    print(f"Draft mailboxes: {len(draft_mailbox_ids)}")
    
    # Let's count messages in active mailboxes
    active_mailbox_ids = set(mailboxes.keys()) - excluded_mailbox_ids - draft_mailbox_ids
    active_msg_count = sum(mailboxes[mid]['count'] for mid in active_mailbox_ids)
    print(f"Total messages in active mailboxes: {active_msg_count}")
    
    # 2. Let's do a test query to get sender & recipients for the first 5 messages
    cursor.execute("""
        SELECT m.ROWID, m.date_sent, m.date_received, m.mailbox, 
               s_addr.address, s_addr.comment,
               subj.subject
        FROM messages m
        LEFT JOIN addresses s_addr ON m.sender = s_addr.ROWID
        LEFT JOIN subjects subj ON m.subject = subj.ROWID
        WHERE m.mailbox NOT IN ({}) AND m.mailbox NOT IN ({})
        LIMIT 5
    """.format(
        ",".join(map(str, excluded_mailbox_ids)),
        ",".join(map(str, draft_mailbox_ids))
    ))
    
    print("\nSample messages:")
    for m_id, d_sent, d_rec, m_box, s_email, s_name, subj in cursor.fetchall():
        print(f"Msg {m_id}: {s_name} <{s_email}> | Subj: {subj} | Mailbox: {mailboxes[m_box]['friendly_name']}")
        
        # Get recipients
        cursor.execute("""
            SELECT r_addr.address, r_addr.comment, r.type
            FROM recipients r
            JOIN addresses r_addr ON r.address = r_addr.ROWID
            WHERE r.message = ?
        """, (m_id,))
        for r_email, r_name, r_type in cursor.fetchall():
            type_str = {0: "To", 1: "CC", 2: "BCC"}.get(r_type, str(r_type))
            print(f"  -> {type_str}: {r_name} <{r_email}>")

if __name__ == '__main__':
    main()
