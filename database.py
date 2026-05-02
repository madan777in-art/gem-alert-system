"""
database.py — SQLite operations
"""
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict
import os

logger = logging.getLogger(__name__)
DB_PATH = os.environ.get("DB_PATH", "gem_tenders.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS seen_tenders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                bid_no     TEXT NOT NULL UNIQUE,
                title      TEXT,
                source     TEXT,
                first_seen TEXT NOT NULL,
                alerted    INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS alert_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                bid_no     TEXT NOT NULL,
                alerted_at TEXT NOT NULL,
                email_sent INTEGER DEFAULT 0,
                error      TEXT
            );
            CREATE TABLE IF NOT EXISTS scrape_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                scraped_at    TEXT NOT NULL,
                portal        TEXT,
                tenders_found INTEGER DEFAULT 0,
                new_tenders   INTEGER DEFAULT 0,
                success       INTEGER DEFAULT 1,
                error         TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_bid_no ON seen_tenders(bid_no);
        """)
    logger.info(f"Database ready: {DB_PATH}")


def is_new_tender(bid_no: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM seen_tenders WHERE bid_no=?", (bid_no,)).fetchone()
        return row is None


def mark_tender_seen(t: Dict) -> bool:
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO seen_tenders (bid_no,title,source,first_seen,alerted) VALUES (?,?,?,?,0)",
                (t.get("bid_no",""), t.get("title","")[:500], t.get("source",""), datetime.now().isoformat())
            )
            return conn.total_changes > 0
    except Exception as e:
        logger.error(f"DB insert error: {e}")
        return False


def mark_alerted(bid_no: str):
    with get_connection() as conn:
        conn.execute("UPDATE seen_tenders SET alerted=1 WHERE bid_no=?", (bid_no,))
        conn.execute("INSERT INTO alert_log (bid_no,alerted_at,email_sent) VALUES (?,?,1)",
                     (bid_no, datetime.now().isoformat()))


def log_alert_error(bid_no: str, error: str):
    with get_connection() as conn:
        conn.execute("INSERT INTO alert_log (bid_no,alerted_at,email_sent,error) VALUES (?,?,0,?)",
                     (bid_no, datetime.now().isoformat(), error))


def log_scrape(portal, found, new, success, error=""):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO scrape_log (scraped_at,portal,tenders_found,new_tenders,success,error) VALUES (?,?,?,?,?,?)",
            (datetime.now().isoformat(), portal, found, new, int(success), error)
        )


def get_recent_tenders(limit=50) -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT bid_no,title,source,first_seen FROM seen_tenders "
            "WHERE first_seen >= datetime('now','-24 hours') ORDER BY first_seen DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_consecutive_failures() -> int:
    with get_connection() as conn:
        rows = conn.execute("SELECT success FROM scrape_log ORDER BY id DESC LIMIT 3").fetchall()
        return sum(1 for r in rows if r["success"] == 0) if rows else 0


def get_stats() -> Dict:
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM seen_tenders").fetchone()["c"]
        alerted = conn.execute("SELECT COUNT(*) as c FROM seen_tenders WHERE alerted=1").fetchone()["c"]
        last = conn.execute("SELECT scraped_at FROM scrape_log ORDER BY id DESC LIMIT 1").fetchone()
        return {"total_seen": total, "total_alerted": alerted,
                "last_scrape": last["scraped_at"] if last else "Never"}
