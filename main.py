"""
main.py — Entry point
"""
import logging
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from scraper import scrape_all_portals
from matcher import filter_tenders
from database import (init_db, is_new_tender, mark_tender_seen, mark_alerted,
                      log_alert_error, log_scrape, get_recent_tenders, get_stats,
                      get_consecutive_failures)
from emailer import send_tender_alert, send_daily_summary, send_admin_alert
from scheduler import create_scheduler, start_scheduler


def setup_logging():
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO, format=fmt,
        handlers=[
            logging.FileHandler("scraper.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ]
    )


logger = logging.getLogger(__name__)


def run_scrape_cycle():
    start = datetime.now()
    logger.info(f"=== Scrape cycle started: {start.strftime('%Y-%m-%d %H:%M:%S')} ===")
    try:
        all_tenders = scrape_all_portals()
        logger.info(f"Total tenders fetched: {len(all_tenders)}")
        matched = filter_tenders(all_tenders)
        logger.info(f"Keyword-matched tenders: {len(matched)}")
        new_count = 0
        for t in matched:
            bid = t.get("bid_no","")
            if not bid:
                continue
            if is_new_tender(bid):
                mark_tender_seen(t)
                logger.info(f"NEW: {bid} — {t.get('title','')[:60]}")
                logger.info(f"  Keywords: {t.get('matched_keywords',[])}")
                if send_tender_alert(t):
                    mark_alerted(bid)
                    logger.info(f"  Alert sent ✓")
                else:
                    log_alert_error(bid, "Email failed")
                    logger.error(f"  Alert FAILED for {bid}")
                new_count += 1
        log_scrape("all", len(all_tenders), new_count, True)
        elapsed = (datetime.now() - start).seconds
        logger.info(f"=== Cycle done: {new_count} new alerts in {elapsed}s ===")
        if get_consecutive_failures() >= 3:
            send_admin_alert("Scraper failed 3 consecutive cycles. Check scraper.log.")
    except Exception as e:
        logger.error(f"Cycle crashed: {e}", exc_info=True)
        log_scrape("all", 0, 0, False, str(e))


def run_daily_summary():
    logger.info("Sending daily summary ...")
    try:
        recent = get_recent_tenders(50)
        stats = get_stats()
        if send_daily_summary(recent, stats):
            logger.info(f"Daily summary sent: {len(recent)} tenders")
        else:
            logger.error("Daily summary failed")
    except Exception as e:
        logger.error(f"Daily summary error: {e}", exc_info=True)


def check_config():
    missing = [k for k in ["SMTP_USER","SMTP_PASSWORD","TO_EMAIL"] if not os.environ.get(k)]
    if missing:
        logger.error(f"Missing .env variables: {', '.join(missing)}")
        sys.exit(1)
    logger.info(f"Config OK — alerts → {os.environ.get('TO_EMAIL')}")


def main():
    setup_logging()
    logger.info("=" * 55)
    logger.info("  GeM Tender Alert System v5 — Starting")
    logger.info("=" * 55)
    check_config()
    init_db()
    logger.info("Running first scrape cycle now ...")
    run_scrape_cycle()
    scheduler = create_scheduler(run_scrape_cycle, run_daily_summary)
    start_scheduler(scheduler)


if __name__ == "__main__":
    main()
