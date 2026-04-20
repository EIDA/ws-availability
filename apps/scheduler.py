import logging
import os

import sentry_sdk
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from apps.sentry import init_sentry
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


@sentry_sdk.monitor(
    monitor_slug="rebuild-inventory-cache",
    monitor_config={
        "schedule": {"type": "crontab", "value": "0 3 * * *"},
        "checkin_margin": 10,
        "max_runtime": 60,
        "timezone": "UTC",
    },
)

def run_inventory_cache():
    """Builds the inventory cache stored in Redis.

    Wrapped with @sentry_sdk.monitor so that Sentry Crons tracks:
    - When the job starts and finishes (check-in: IN_PROGRESS → OK)
    - When the job fails (check-in: ERROR) with full exception details
    - When the job never runs (check-in: MISSED) e.g. if the container goes down
    """
    logger.info("Starting scheduled task: Rebuild Inventory Cache")
    try:
        cache = Cache()
        cache.build_cache()
        logger.info("Completed scheduled task: Rebuild Inventory Cache")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.exception("Failed to build inventory cache: %s", e)
        raise  # Re-raise so the Sentry monitor registers this run as ERROR


@sentry_sdk.monitor(
    monitor_slug="update-availability-view",
    monitor_config={
        "schedule": {"type": "crontab", "value": "0 6 * * *"},
        "checkin_margin": 10,
        "max_runtime": 60,
        "timezone": "UTC",
    },
)
def run_materialized_view_update():
    """Updates the MongoDB materialized view from daily_streams.

    Wrapped with @sentry_sdk.monitor so that Sentry Crons tracks:
    - When the job starts and finishes (check-in: IN_PROGRESS → OK)
    - When the job fails (check-in: ERROR) with full exception details
    - When the job never runs (check-in: MISSED) e.g. if the container goes down
    """
    logger.info("Starting scheduled task: Update Availability Materialized View")
    try:
        db_client = get_db_client()
        db_name = os.getenv("MONGODB_NAME", "wfrepo")
        db = db_client.get_database(db_name)

        updater = AvailabilityUpdater(db)

        # Run the updates using the default (last 1 day) behavior
        updater.run_updates()
        logger.info("Completed scheduled task: Update Availability Materialized View")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.exception("Failed to update availability materialized view: %s", e)
        raise  # Re-raise so the Sentry monitor registers this run as ERROR


if __name__ == "__main__":
    # Initialize Sentry before starting the scheduler so all events are captured.
    # Reuses the shared init_sentry() from apps/sentry.py (same as the API).
    # No-op if SENTRY_DSN is not set.
    init_sentry()
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

    # Run jobs once on startup to ensure persistence/freshness after a restart
    logger.info("Running initial startup tasks...")
    try:
        run_inventory_cache()
        run_materialized_view_update()
    except Exception as e:
        logger.error("Initial startup tasks failed: %s", e)

    logger.info("Scheduler started successfully. Waiting for jobs to execute...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
