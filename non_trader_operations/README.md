# Non-Trader Operations Archive

This directory was created by **Lehman Brody** (Autonomous Quant OS) to catalog and separate non-trading components from the core OKX algorithmic trading system, keeping the repository root directory clean, specialized, and highly organized.

No useful data was destroyed. All archived components are documented below:

---

## 📱 1. TikTok Fleet Module
Autonomous system for managing and uploading content to multiple TikTok accounts.
*   **`tiktok_fleet.db`**: Local SQLite database containing account states, schedule registries, and publishing queues.
*   **`tiktok_project_plan.md`**: Master plan for the TikTok fleet daemon, account setups, and scheduling layers.
*   **`SYSTEM_STATUS.md`**: Technical roadmap and details of the TikTok Fleet daemon architecture (Schedules, APIs, Lut management).

## ✉️ 2. Contacts Scraping & Cold Outreach
Python pipeline for scraping, verifying, validating, and promoting B2B contacts.
*   **`list_mailboxes.py` / `test_auth.py`**: Authentication tests and mailbox listings.
*   **`get_all_contacts.py` / `write_contacts.py` / `read_sheets_info.py`**: Google Sheets sync engines.
*   **`test_contacts.py` / `test_contacts_full.py` / `test_query.py` / `test_vectorized.py`**: Contact query, fuzzy matching, and vector search testing suites.
*   **`auto_enrich_domains.py`**: Automated company domain enrichment.
*   **`analyze_contacts.py`**: Verification metrics and analytical breakdowns of scraped databases.
*   **`promote_contacts.py` / `promote_second_batch.py` / `promote_third_batch.py`**: Pipeline controllers for promoting contact batches to active outreach stages.
*   **`data/`**: Directory containing temporary databases and CSV files of scraped contacts.

## 📊 3. Presentations & Automated Reports
Scripts to automatically generate slide decks and PDFs for client presentations.
*   **`create_presentation.py`**: PPTX generation engine.
*   **`feltrinelli_report.pptx`**: Compiled Feltrinelli slides.
*   **`gdrive_automator.py`**: Google Drive automation for synchronizing generated documents.

## 🏛️ 4. Administrative & Submodules
Local administrative filings and non-trading web-mapping tools.
*   **`Documento_SCIA_Milano_Oltre1000.md`**: Official documentation regarding SCIA administrative requirements in Milan.
*   **`PLAN_AUDIT_MAPPA.md`**: Audit plan for the Lombardy anti-violence center web-map.
*   **`mappa-antiviolenza-lombardia/`**: Interactive web application mapping anti-violence centers in Lombardy.
