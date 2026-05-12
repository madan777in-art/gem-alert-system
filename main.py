"""
main.py - GeM Tender Alert System v3.1
Fix: Uses SMTP_SSL (port 465) instead of STARTTLS (port 587)
Railway blocks port 587 outbound — port 465 works fine.
"""

import os
import logging
import sqlite3
import smtplib
import hashlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from scraper import scrape_all_portals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

SMTP_HOST     = os.environ.get("SMTP_HOST",     "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER     = os.environ.get("SMTP_USER",     "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
TO_EMAIL      = os.environ.get("TO_EMAIL",      "madan78au@hotmail.com")
DB_PATH       = os.environ.get("DB_PATH",       "gem_tenders.db")
CHECK_MINUTES = int(os.environ.get("CHECK_EVERY_MINUTES", "30"))

KEYWORDS = [
    "e-learning", "elearning", "lms", "learning management",
    "igot", "content development", "content design", "storyboarding",
    "interactive content", "ar/vr", "augmented reality", "virtual reality",
    "immersive learning", "immersive solutions", "digital learning",
    "online training", "scorm", "courseware",
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen (
            hash TEXT PRIMARY KEY,
            title TEXT,
            first_seen TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info(f"Database ready: {DB_PATH}")

def is_new(title: str) -> bool:
    h = hashlib.md5(title.strip().lower()[:80].encode()).hexdigest()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT hash FROM seen WHERE hash=?", (h,)).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO seen (hash, title, first_seen) VALUES (?,?,?)",
            (h, title[:200], datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def send_email(subject: str, html_body: str):
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.error("EMAIL NOT CONFIGURED")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_USER
        msg["To"]      = TO_EMAIL
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, TO_EMAIL, msg.as_string())
        logger.info(f"✅ Email sent to {TO_EMAIL}: {subject}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("❌ EMAIL FAILED: Wrong Gmail App Password. Generate a new one at myaccount.google.com/apppasswords")
        return False
    except Exception as e:
        logger.error(f"❌ EMAIL FAILED: {e}")
        return False

def send_test_email():
    html = f"""
    <html><body style="font-family:Arial,sans-serif;padding:20px;">
    <h2 style="color:#2e7d32;">✅ GeM Tender Alert System — ACTIVE</h2>
    <p>Your tender monitoring system is <strong>running successfully</strong> on Railway.</p>
    <table style="border-collapse:collapse;width:100%;">
      <tr><td style="padding:8px;border:1px solid #ddd;background:#f5f5f5;"><b>Started at</b></td>
          <td style="padding:8px;border:1px solid #ddd;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}</td></tr>
      <tr><td style="padding:8px;border:1px solid #ddd;background:#f5f5f5;"><b>Check frequency</b></td>
          <td style="padding:8px;border:1px solid #ddd;">Every {CHECK_MINUTES} minutes</td></tr>
      <tr><td style="padding:8px;border:1px solid #ddd;background:#f5f5f5;"><b>Alert email</b></td>
          <td style="padding:8px;border:1px solid #ddd;">{TO_EMAIL}</td></tr>
    </table>
    <p style="color:#555;margin-top:20px;">You will receive alerts whenever new matching tenders are found.</p>
    </body></html>
    """
    return send_email("✅ GeM Alert System Started — Monitoring Active", html)

def send_tender_alert(tenders: list):
    rows = ""
    for t in tenders:
        rows += f"""
        <tr>
          <td style="padding:8px;border:1px solid #ddd;">{t.get('title','')[:120]}</td>
          <td style="padding:8px;border:1px solid #ddd;">{t.get('bid_no','—')}</td>
          <td style="padding:8px;border:1px solid #ddd;">{t.get('org','—')}</td>
          <td style="padding:8px;border:1px solid #ddd;">{t.get('value','—')}</td>
          <td style="padding:8px;border:1px solid #ddd;">{t.get('source','')}</td>
          <td style="padding:8px;border:1px solid #ddd;"><a href="{t.get('url','#')}">View</a></td>
        </tr>"""
    html = f"""
    <html><body style="font-family:Arial,sans-serif;padding:20px;">
    <h2 style="color:#1565c0;">🔔 {len(tenders)} New GeM Tender(s) Found</h2>
    <p>Found at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}</p>
    <table style="border-collapse:collapse;width:100%;font-size:13px;">
      <thead>
        <tr style="background:#1565c0;color:white;">
          <th style="padding:8px;">Tender Title</th>
          <th style="padding:8px;">Bid No</th>
          <th style="padding:8px;">Department</th>
          <th style="padding:8px;">Value</th>
          <th style="padding:8px;">Source</th>
          <th style="padding:8px;">Link</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    </body></html>
    """
    send_email(f"🔔 {len(tenders)} New GeM Tender Alert(s) — Action Required", html)

def keyword_match(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in KEYWORDS)

def run_cycle():
    logger.info(f"=== Scrape cycle started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    try:
        tenders = scrape_all_portals()
        logger.info(f"Total tenders fetched: {len(tenders)}")
        matched = [t for t in tenders if keyword_match(t.get("title", "") + " " + t.get("org", ""))]
        logger.info(f"Keyword-matched tenders: {len(matched)}")
        new_tenders = [t for t in matched if is_new(t.get("title", ""))]
        logger.info(f"New (unseen) tenders: {len(new_tenders)}")
        if new_tenders:
            send_tender_alert(new_tenders)
            logger.info(f"=== Cycle done: {len(new_tenders)} new alerts sent ===")
        else:
            logger.info("=== Cycle done: 0 new alerts (all tenders already seen) ===")
    except Exception as e:
        logger.error(f"Cycle error: {e}")

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  GeM Tender Alert System v3.1 — Starting")
    logger.info("=" * 60)
    logger.info(f"Email: {SMTP_USER} → {TO_EMAIL} via {SMTP_HOST}:{SMTP_PORT} (SSL)")
    init_db()
    logger.info("Sending startup test email...")
    send_test_email()
    logger.info("Running first scrape cycle now...")
    run_cycle()
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(run_cycle, "interval", minutes=CHECK_MINUTES)
    logger.info(f"Scheduler started — running every {CHECK_MINUTES} minutes")
    scheduler.start()
