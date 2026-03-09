import logging
import os
import smtplib
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from apps.updater import AvailabilityUpdater
from apps.wfcatalog_client import get_db_client
from cache import Cache

# Set up logging for the scheduler
logging.basicConfig(
    handlers=[logging.StreamHandler()],
    level=logging.INFO,
    format="[%(asctime)s] [SCHEDULER] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S +0000",
)
logger = logging.getLogger(__name__)


def run_inventory_cache():
    """Builds the inventory cache stored in Redis."""
    logger.info("Starting scheduled task: Rebuild Inventory Cache")
    try:
        cache = Cache()
        cache.build_cache()
    except Exception as e:
        logger.exception("Failed to build inventory cache: %s", e)


def run_materialized_view_update():
    """Updates the MongoDB materialized view from daily_streams."""
    logger.info("Starting scheduled task: Update Availability Materialized View")
    try:
        # We initialized the updater with our global DB client
        db_client = get_db_client()
        # Ensure we use the correct database name passed via environment, defaulting to 'wfrepo'
        db_name = os.getenv("MONGODB_NAME", "wfrepo")
        db = db_client.get_database(db_name)
        
        updater = AvailabilityUpdater(db)
        
        # We run the updates using the default (last 1 day) behavior, matching the former bash script logic
        updater.run_updates()
        
    except Exception as e:
        logger.exception("Failed to update availability materialized view: %s", e)


if __name__ == "__main__":
    logger.info("Initializing APScheduler...")
    scheduler = BlockingScheduler()

    # Schedule cache rebuilding every day at 3:00 AM (Equivalent to 0 3 * * * cron)
    scheduler.add_job(
        run_inventory_cache,
        CronTrigger(hour=3, minute=0),
        id="rebuild_inventory_cache_job",
        name="Rebuilds the cache mapping seed IDs to restriction data from FDSNWS Station",
        replace_existing=True,
    )

    # Schedule DB view update every day at 6:00 AM (Equivalent to 0 6 * * * cron)
    scheduler.add_job(
        run_materialized_view_update,
        CronTrigger(hour=6, minute=0),
        id="update_availability_view_job",
        name="Builds the daily_streams aggregation into the availability materialized view",
        replace_existing=True,
    )

    logger.info("Scheduler started successfully. Waiting for jobs to execute...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
