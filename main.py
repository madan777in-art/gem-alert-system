"""
main.py — GeM Tender Alert System Entry Point
Wires together scraper, matcher, database, emailer, and scheduler.
"""

import logging
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load .env FIRST before any other imports that read env vars
load_dotenv()

from scraper import scrape_all_portals
from matcher import filter_tenders
from database import (
    init_db, is_new_tender, mark_tender_seen, mark_alerted,
    log_alert_error, log_scrape, get_recent_tenders, get_stats,
    get_consecutive_failures,
)
from emailer import send_tender_alert, send_daily_summary, send_admin_alert
from scheduler import create_scheduler, start_scheduler

# ── Logging setup ─────────────────────────────────────────────────────────────
def setup_logging():
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler("scraper.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

logger = logging.getLogger(__name__)

# ── Core job: scrape + match + alert ─────────────────────────────────────────
def run_scrape_cycle():
    """
    Full scrape cycle:
    1. Scrape all 3 portals
    2. Filter by keywords
    3. For each new match → send instant email alert
    4. Log results
    """
    cycle_start = datetime.now()
    logger.info(f"=== Scrape cycle started: {cycle_start.strftime('%Y-%m-%d %H:%M:%S')} ===")

    try:
        # Step 1: Scrape
        all_tenders = scrape_all_portals()
        logger.info(f"Total tenders fetched: {len(all_tenders)}")

        # Step 2: Match keywords
        matched = filter_tenders(all_tenders)
        logger.info(f"Keyword-matched tenders: {len(matched)}")

        # Step 3: Process new ones
        new_count = 0
        for tender in matched:
            bid_no = tender.get("bid_no", "")
            if not bid_no:
                continue

            if is_new_tender(bid_no):
                # Mark as seen immediately to prevent duplicate sends
                mark_tender_seen(tender)

                logger.info(f"NEW tender found: {bid_no} — {tender.get('title','')[:60]}")
                logger.info(f"  Keywords: {tender.get('matched_keywords', [])}")
                logger.info(f"  Source: {tender.get('source', '')}")

                # Send instant alert
                success = send_tender_alert(tender)

                if success:
                    mark_alerted(bid_no)
                    logger.info(f"Alert sent for: {bid_no}")
                else:
                    log_alert_error(bid_no, "Email send failed")
                    logger.error(f"Alert FAILED for: {bid_no}")

                new_count += 1
            else:
                logger.debug(f"Already seen: {bid_no}")

        # Step 4: Log this cycle
        log_scrape(
            portal="all",
            found=len(all_tenders),
            new=new_count,
            success=True,
        )

        elapsed = (datetime.now() - cycle_start).seconds
        logger.info(f"=== Cycle complete: {new_count} new alerts sent in {elapsed}s ===")

        # Check for repeated failures and send admin alert
        failures = get_consecutive_failures()
        if failures >= 3:
            send_admin_alert(
                f"The GeM scraper has failed {failures} consecutive cycles. "
                f"Please check scraper.log for details."
            )

    except Exception as e:
        logger.error(f"Scrape cycle crashed: {e}", exc_info=True)
        log_scrape(portal="all", found=0, new=0, success=False, error=str(e))


# ── Daily summary job ─────────────────────────────────────────────────────────
def run_daily_summary():
    """Send the 8 AM daily digest email."""
    logger.info("Sending daily summary email...")
    try:
        recent = get_recent_tenders(limit=50)
        stats = get_stats()
        success = send_daily_summary(recent, stats)
        if success:
            logger.info(f"Daily summary sent: {len(recent)} tender(s) included")
        else:
            logger.error("Daily summary email failed to send")
    except Exception as e:
        logger.error(f"Daily summary crashed: {e}", exc_info=True)


# ── Startup checks ────────────────────────────────────────────────────────────
def check_config():
    """Verify required environment variables are set."""
    required = ["SMTP_USER", "SMTP_PASSWORD", "TO_EMAIL"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        logger.error(f"Missing required .env variables: {', '.join(missing)}")
        logger.error("Please configure your .env file before running.")
        sys.exit(1)
    logger.info("Configuration OK")
    logger.info(f"Alerts will be sent to: {os.environ.get('TO_EMAIL')}")
    logger.info(f"SMTP: {os.environ.get('SMTP_HOST')}:{os.environ.get('SMTP_PORT')}")


# ── Main entry point ──────────────────────────────────────────────────────────
def main():
    setup_logging()
    logger.info("=" * 60)
    logger.info("  GeM Tender Alert System — Starting Up")
    logger.info("=" * 60)

    # Check config
    check_config()

    # Initialise database
    init_db()

    # Run one immediate cycle on startup so you get results right away
    logger.info("Running initial scrape cycle on startup...")
    run_scrape_cycle()

    # Start the scheduler (runs forever)
    scheduler = create_scheduler(run_scrape_cycle, run_daily_summary)
    start_scheduler(scheduler)


if __name__ == "__main__":
    main()
