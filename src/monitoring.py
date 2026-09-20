"""
Monitoring module for tracking account health, quarantine state, and errors.
"""
import sqlite3
import os
import time
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tiktok_fleet.db")


def get_connection():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_quarantine_table():
    """Initialize quarantine tracking table."""
    with get_connection() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS quarantine (
                serial_no TEXT PRIMARY KEY,
                quarantined_at INTEGER,
                expires_at INTEGER,
                reason TEXT DEFAULT 'proxy_failure'
            )
        """)
        c.commit()


def mark_quarantined(serial_no: str, minutes: int = 30, reason: str = "proxy_failure"):
    """Mark a phone as quarantined due to proxy failure."""
    now = int(time.time())
    expires = now + minutes * 60
    with get_connection() as c:
        c.execute("""
            INSERT OR REPLACE INTO quarantine (serial_no, quarantined_at, expires_at, reason)
            VALUES (?, ?, ?, ?)
        """, (serial_no, now, expires, reason))
        c.commit()


def is_quarantined(serial_no: str) -> bool:
    """Check if a phone is currently quarantined."""
    now = int(time.time())
    with get_connection() as c:
        row = c.execute(
            "SELECT * FROM quarantine WHERE serial_no = ? AND expires_at > ?",
            (serial_no, now),
        ).fetchone()
        return row is not None


def cleanup_quarantines():
    """Remove expired quarantine entries."""
    now = int(time.time())
    with get_connection() as c:
        c.execute("DELETE FROM quarantine WHERE expires_at <= ?", (now,))
        c.commit()


def log_error(serial_no: str, error: str, context: str = ""):
    """Log an error for a specific account."""
    log_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "logs", "errors.log"
    )
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a") as f:
        timestamp = datetime.now().isoformat()
        f.write(f"[{timestamp}] {serial_no} - {context}: {error}\n")