"""
main.py — Tender Monitor v5
Runs every 2 hours. Daily summary at 8:00 AM IST.
"""

import logging
import time
import os
from datetime import datetime
import pytz

from scraper  import scrape_all
from matcher  import filter_tenders
from database import init_db, filter_new
from emailer  import send_alert, send_startup_email

# ── Logging ──────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────
IST = pytz.timezone("Asia/Kolkata")
SCAN_INTERVAL_HOURS = int(os.environ.get("SCAN_INTERVAL_HOURS", 2))
DAILY_SUMMARY_HOUR  = int(os.environ.get("DAILY_SUMMARY_HOUR", 8))   # 8 AM IST

KEYWORDS = [
    "e-learning", "elearning", "iGOT", "igot", "karmayogi",
    "LMS", "learning management system",
    "AR VR", "augmented reality", "virtual reality", "immersive",
    "content development", "storyboarding", "instructional design",
    "digital learning", "online training", "simulation",
    "SCORM", "courseware", "multimedia content",
]


def run_cycle(daily_summary=False):
    logger.info("=" * 60)
    logger.info(f"SCAN CYCLE — {'DAILY SUMMARY' if daily_summary else 'INSTANT ALERT'}")
    logger.info("=" * 60)

    start = time.time()
    raw       = scrape_all(KEYWORDS)
    matched   = filter_tenders(raw, KEYWORDS)
    new_ones  = filter_new(matched)

    logger.info(f"Total fetched: {len(raw)}")
    logger.info(f"Keyword-matched: {len(matched)}")
    logger.info(f"New (unseen): {len(new_ones)}")

    if new_ones:
        send_alert(new_ones, is_daily=daily_summary)
    else:
        logger.info("No new tenders this cycle — no email sent")

    elapsed = int(time.time() - start)
    logger.info(f"=== Cycle done: {len(new_ones)} new alerts in {elapsed}s ===")
    return new_ones


def main():
    logger.info("🚀 Tender Monitor v5 starting up...")
    init_db()
    send_startup_email()

    last_daily_date = None

    while True:
        now_ist = datetime.now(IST)

        # Daily summary at 8 AM IST
        today = now_ist.date()
        if now_ist.hour == DAILY_SUMMARY_HOUR and last_daily_date != today:
            run_cycle(daily_summary=True)
            last_daily_date = today
        else:
            run_cycle(daily_summary=False)

        logger.info(f"Sleeping {SCAN_INTERVAL_HOURS}h until next scan...")
        time.sleep(SCAN_INTERVAL_HOURS * 3600)


if __name__ == "__main__":
    main()
