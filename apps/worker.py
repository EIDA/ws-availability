
import argparse
import logging
import time
from datetime import datetime, timedelta
from pymongo import MongoClient, UpdateOne
from apps.settings import settings

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def get_mongo_client():
    return MongoClient(
        settings.mongodb_host,
        settings.mongodb_port,
        username=settings.mongodb_usr,
        password=settings.mongodb_pwd,
        authSource=settings.mongodb_name
    )

def run_etl(networks=".*", stations=".*", start_date=None, end_date=None, days_back=1):
    """
    Main ETL function:
    1. Cleans up old availability data (Fix for Issue 27).
    2. Aggregates data from daily_streams / c_segments.
    3. Inserts fresh data into availability.
    """
    client = get_mongo_client()
    db = client[settings.mongodb_name]
    
    # Calculate dates if not provided
    # Default to "Yesterday" (00:00 to 00:00 next day)
    if start_date is None:
        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_back)
    
    if end_date is None:
         end_date = start_date + timedelta(days=1)

    logger.info(f"--- Starting ETL Job ---")
    logger.info(f"Scope: Net={networks}, Sta={stations}")
    logger.info(f"Time:  {start_date} -> {end_date}")

    # Filters matching main.js
    # ts >= start AND te <= end
    match_filter = {
        "net": {"$regex": networks},
        "sta": {"$regex": stations},
        "ts": {"$gte": start_date},
        "te": {"$lte": end_date}
    }

    # ---------------------------------------------------------
    # STEP 1: DELETE BEFORE WRITE (Fix for Issue 27)
    # ---------------------------------------------------------
    # We must delete any existing availability records that we are about to re-generate.
    # This ensures that if WFCatalog re-generated IDs, the old ones (with old IDs) are gone.
    logger.info("Cleaning up existing availability data...")
    del_result = db.availability.delete_many(match_filter)
    logger.info(f"Deleted {del_result.deleted_count} existing documents.")

    # ---------------------------------------------------------
    # STEP 2: Process Daily Streams (Avail >= 100)
    # ---------------------------------------------------------
    logger.info("Aggregating Daily Streams (Avail >= 100)...")
    pipeline_daily = [
        {
            "$match": {
                **match_filter,
                "avail": {"$gte": 100}
            }
        },
        {
            "$group": {
                "_id": "$_id",
                "net": {"$first": "$net"},
                "sta": {"$first": "$sta"},
                "loc": {"$first": "$loc"},
                "cha": {"$first": "$cha"},
                "qlt": {"$first": "$qlt"},
                "srate": {"$first": {"$arrayElemAt": ["$srate", 0]}},
                "ts": {"$first": "$ts"},
                "te": {"$first": "$te"},
                "created": {"$first": "$created"},
                "restr": {"$first": "OPEN"},
                "count": {"$first": 1}
            }
        }
    ]
    
    docs_daily = list(db.daily_streams.aggregate(pipeline_daily))
    if docs_daily:
        # Use bulk operations for performance and safety
        # Although we deleted, we use upsert=True just in case to be robust
        ops = [UpdateOne({"_id": d["_id"]}, {"$set": d}, upsert=True) for d in docs_daily]
        if ops:
            res = db.availability.bulk_write(ops)
            logger.info(f"Daily Streams: Matched {res.matched_count}, Inserted {res.upserted_count}, Modified {res.modified_count}")
    else:
        logger.info("No Daily Streams found.")

    # ---------------------------------------------------------
    # STEP 3: Process Continuous Streams (Avail < 100)
    # ---------------------------------------------------------
    logger.info("Aggregating Continuous Streams (Avail < 100)...")
    pipeline_continuous = [
        {
            "$match": {
                **match_filter,
                "avail": {"$lt": 100}
            }
        },
        {
            "$lookup": {
                "from": "c_segments",
                "localField": "_id",
                "foreignField": "streamId",
                "as": "c_segments"
            }
        },
        {"$unwind": "$c_segments"},
        {
            "$group": {
                "_id": "$c_segments._id",
                "net": {"$first": "$net"},
                "sta": {"$first": "$sta"},
                "loc": {"$first": "$loc"},
                "cha": {"$first": "$cha"},
                "qlt": {"$first": "$qlt"},
                "srate": {"$first": "$c_segments.srate"},
                "ts": {"$first": "$c_segments.ts"},
                "te": {"$first": "$c_segments.te"},
                "created": {"$first": "$created"},
                "restr": {"$first": "OPEN"},
                "count": {"$first": 1}
            }
        }
    ]
    
    docs_cont = list(db.daily_streams.aggregate(pipeline_continuous))
    if docs_cont:
        ops = [UpdateOne({"_id": d["_id"]}, {"$set": d}, upsert=True) for d in docs_cont]
        if ops:
            res = db.availability.bulk_write(ops)
            logger.info(f"Continuous Streams: Matched {res.matched_count}, Inserted {res.upserted_count}, Modified {res.modified_count}")
    else:
        logger.info("No Continuous Streams found.")
    
    logger.info("ETL Job Completed.")

def job():
    """Scheduled job wrapper"""
    try:
        run_etl(days_back=1) # Process yesterday
    except Exception as e:
        logger.exception("Job Failed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--networks", default=".*")
    parser.add_argument("--stations", default=".*")
    parser.add_argument("--start", help="ISO format YYYY-MM-DD")
    parser.add_argument("--end", help="ISO format YYYY-MM-DD")
    parser.add_argument("--days-back", type=int, default=1)
    parser.add_argument("--daemon", action="store_true", help="Run indefinitely (every 6 hours)")
    
    args = parser.parse_args()
    
    if args.daemon:
        logger.info("Starting Worker in Daemon Mode (Running every 6 hours)")
        
        while True:
            job()
            # Sleep for 6 hours (6 * 3600 seconds)
            time.sleep(6 * 3600)
    else:
        # One-off run
        s = datetime.fromisoformat(args.start) if args.start else None
        e = datetime.fromisoformat(args.end) if args.end else None
        
        run_etl(networks=args.networks, stations=args.stations, start_date=s, end_date=e, days_back=args.days_back)
