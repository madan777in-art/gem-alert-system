"""
scheduler.py — APScheduler Setup
Runs the scraper every 30 minutes and sends a daily summary at 8:00 AM IST.
"""

import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")


def create_scheduler(scrape_job, daily_summary_job) -> BlockingScheduler:
    """
    Create and configure the scheduler.
    scrape_job      — called every 30 minutes
    daily_summary_job — called every day at 08:00 IST
    """
    scheduler = BlockingScheduler(timezone=IST)

    # ── Every 30 minutes ──────────────────────────────────────────────────────
    scheduler.add_job(
        func=scrape_job,
        trigger=IntervalTrigger(minutes=30, timezone=IST),
        id="gem_scrape",
        name="GeM Portal Scrape",
        replace_existing=True,
        max_instances=1,          # Prevent overlap if one run is slow
        misfire_grace_time=120,   # Allow up to 2-min delay before skipping
    )

    # ── Daily summary at 08:00 IST ────────────────────────────────────────────
    scheduler.add_job(
        func=daily_summary_job,
        trigger=CronTrigger(hour=8, minute=0, timezone=IST),
        id="gem_daily_summary",
        name="GeM Daily Summary Email",
        replace_existing=True,
        max_instances=1,
    )

    logger.info("Scheduler configured: scrape every 30 min, summary at 08:00 IST")
    return scheduler


def start_scheduler(scheduler: BlockingScheduler):
    """Start the scheduler (blocking — runs forever)."""
    try:
        logger.info("Starting scheduler... Press Ctrl+C to stop.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user.")
        scheduler.shutdown(wait=False)
