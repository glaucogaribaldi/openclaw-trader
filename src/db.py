"""
SQLite state store for TikTok fleet daemon.
Tables: phones, videos, post_history.
"""
import sqlite3
import os
from contextlib import contextmanager

# Resolve DB path relative to workspace root
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(WORKSPACE, "tiktok_fleet.db")


def get_workspace():
    return WORKSPACE


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    """Initialize database tables."""
    with conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS phones (
                serial_no       TEXT PRIMARY KEY,
                serial_name     TEXT UNIQUE,
                group_name      TEXT,
                proxy           TEXT,
                timezone        TEXT,
                country         TEXT,
                slot_times      TEXT,
                content_key     TEXT,
                video_posts     INTEGER DEFAULT 0,
                profiled_at     INTEGER DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id              TEXT PRIMARY KEY,
                source_channel  TEXT,
                original_url    TEXT,
                edited_path     TEXT,
                resource_url    TEXT,
                description     TEXT,
                posted          INTEGER DEFAULT 0,
                created_at      INTEGER DEFAULT (strftime('%s','now'))
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS post_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                serial_no       TEXT,
                video_id        TEXT,
                task_id         TEXT,
                scheduled_at    INTEGER,
                slot            INTEGER,
                posted_at       INTEGER DEFAULT (strftime('%s','now'))
            )
        """)


def upsert_phone(phone: dict):
    """Register or update a phone in the database."""
    with conn() as c:
        c.execute("""
            INSERT INTO phones (serial_no, serial_name, group_name, proxy, timezone, country)
            VALUES (:serial_no, :serial_name, :group_name, :proxy, :timezone, :country)
            ON CONFLICT(serial_no) DO UPDATE SET
                serial_name = excluded.serial_name,
                group_name  = excluded.group_name,
                proxy       = excluded.proxy,
                timezone    = excluded.timezone,
                country     = excluded.country
        """, phone)


def get_phone(serial_no: str) -> dict | None:
    """Get phone configuration from DB."""
    with conn() as c:
        row = c.execute("SELECT * FROM phones WHERE serial_no = ?", (serial_no,)).fetchone()
        return dict(row) if row else None


def mark_video_posted(video_id: str, serial_no: str, task_id: str, scheduled_at: int, slot: int):
    """Mark a video as posted and record in history."""
    with conn() as c:
        c.execute("UPDATE videos SET posted = 1 WHERE id = ?", (video_id,))
        c.execute(
            "INSERT INTO post_history (serial_no, video_id, task_id, scheduled_at, slot) VALUES (?,?,?,?,?)",
            (serial_no, video_id, task_id, scheduled_at, slot),
        )
        c.execute("UPDATE phones SET video_posts = video_posts + 1 WHERE serial_no = ?", (serial_no,))


def get_last_post(serial_no: str) -> dict | None:
    """Get the last post record for an account."""
    with conn() as c:
        row = c.execute(
            "SELECT * FROM post_history WHERE serial_no = ? ORDER BY scheduled_at DESC LIMIT 1",
            (serial_no,),
        ).fetchone()
        return dict(row) if row else None


def pick_unposted_video(content_key: str) -> dict | None:
    """Pick an unposted video for a given content key."""
    with conn() as c:
        row = c.execute(
            "SELECT * FROM videos WHERE posted = 0 AND source_channel = ? ORDER BY created_at DESC LIMIT 1",
            (content_key,),
        ).fetchone()
        return dict(row) if row else None