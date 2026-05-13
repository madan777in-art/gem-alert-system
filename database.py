"""
database.py — SQLite deduplication store
Prevents the same tender from being alerted more than once.
"""

import sqlite3
import hashlib
import logging
import os

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "tenders.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_tenders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            hash        TEXT UNIQUE NOT NULL,
            title       TEXT,
            source      TEXT,
            link        TEXT,
            first_seen  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialised")


def tender_hash(tender):
    raw = (tender.get("title", "") + tender.get("link", "")).strip().lower()
    return hashlib.md5(raw.encode()).hexdigest()


def is_new(tender):
    h = tender_hash(tender)
    conn = get_connection()
    row = conn.execute("SELECT id FROM seen_tenders WHERE hash=?", (h,)).fetchone()
    conn.close()
    return row is None


def mark_seen(tender):
    h = tender_hash(tender)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO seen_tenders (hash, title, source, link) VALUES (?,?,?,?)",
            (h, tender.get("title","")[:500], tender.get("source",""), tender.get("link",""))
        )
        conn.commit()
    except Exception as e:
        logger.error(f"DB insert error: {e}")
    finally:
        conn.close()


def filter_new(tenders):
    """Return only tenders not seen before, and mark them seen."""
    new_ones = []
    for t in tenders:
        if is_new(t):
            new_ones.append(t)
            mark_seen(t)
    logger.info(f"{len(new_ones)} new tenders (out of {len(tenders)} matched)")
    return new_ones
