"""
scheduler.py — APScheduler setup
"""
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")


def create_scheduler(scrape_job, daily_job) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=IST)
    scheduler.add_job(scrape_job, IntervalTrigger(minutes=30, timezone=IST),
                      id="gem_scrape", name="GeM Portal Scrape",
                      replace_existing=True, max_instances=1, misfire_grace_time=120)
    scheduler.add_job(daily_job, CronTrigger(hour=8, minute=0, timezone=IST),
                      id="gem_daily", name="GeM Daily Summary",
                      replace_existing=True, max_instances=1)
    logger.info("Scheduler ready: every 30 min + daily summary at 08:00 IST")
    return scheduler


def start_scheduler(scheduler: BlockingScheduler):
    try:
        logger.info("Scheduler started. Press Ctrl+C to stop.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
