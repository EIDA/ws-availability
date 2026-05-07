import logging
from datetime import datetime, timedelta
from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database

logger = logging.getLogger(__name__)


class AvailabilityUpdater:
    def __init__(self, db: Database):
        self.db = db

    def update_availability_daily(
        self,
        networks: str,
        stations: str,
        start_date: datetime,
        end_date: datetime,
    ):
        """
        Equivalent to `updateAvailabilityDaily` in views/main.js
        """
        pipeline = [
            {
                "$match": {
                    "net": {"$regex": networks},
                    "sta": {"$regex": stations},
                    "ts": {"$gte": start_date},
                    "te": {"$lte": end_date},
                    "avail": {"$gte": 100},
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
                    "count": {"$first": 1},
                }
            },
            {"$merge": {"into": "availability", "on": "_id", "whenMatched": "replace"}},
        ]
        
        logger.info(f"Running daily update for net:{networks} sta:{stations} ts:{start_date} te:{end_date}")
        self.db.daily_streams.aggregate(pipeline)

    def update_availability_continuous(
        self,
        networks: str,
        stations: str,
        start_date: datetime,
        end_date: datetime,
    ):
        """
        Equivalent to `updateAvailabilityContinuous` in views/main.js
        """
        pipeline = [
            {
                "$match": {
                    "net": {"$regex": networks},
                    "sta": {"$regex": stations},
                    "ts": {"$gte": start_date},
                    "te": {"$lte": end_date},
                    "avail": {"$lt": 100},
                }
            },
            {
                "$lookup": {
                    "from": "c_segments",
                    "localField": "_id",
                    "foreignField": "streamId",
                    "as": "c_segments",
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
                    "count": {"$first": 1},
                }
            },
            {"$merge": {"into": "availability", "on": "_id", "whenMatched": "replace"}},
        ]
        
        logger.info(f"Running continuous update for net:{networks} sta:{stations} ts:{start_date} te:{end_date}")
        self.db.daily_streams.aggregate(pipeline)

    def run_updates(
        self,
        networks: str = "^.*$",
        stations: str = "^.*$",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        days_back: Optional[int] = None,
    ):
        """
        Main runner function replicating the logic at the bottom of main.js.
        """
        now = datetime.utcnow()
        if days_back is not None:
            # Replicate getPastDate behavior (end_date isn't changed if daysBack is passed in JS script context, but we handle it uniformly)
            # Actually, in JS: `if (typeof daysBack !== "undefined") ts = getPastDate(daysBack);`
            # and te is kept as getPastDate(0)
            target_start = now - timedelta(days=days_back)
            start_date = datetime(target_start.year, target_start.month, target_start.day)
            end_date = end_date or datetime(now.year, now.month, now.day)
        else:
            if start_date is None:
                target_start = now - timedelta(days=1)
                start_date = datetime(target_start.year, target_start.month, target_start.day)
            if end_date is None:
                end_date = datetime(now.year, now.month, now.day)

        logger.info(
            f"Processing WFCatalog entries using networks: '{networks}', stations: '{stations}', start: '{start_date.isoformat()}', end: '{end_date.isoformat()}' started!"
        )

        self.update_availability_daily(networks, stations, start_date, end_date)
        self.update_availability_continuous(networks, stations, start_date, end_date)

        logger.info(
            f"Processing WFCatalog entries using networks: '{networks}', stations: '{stations}', start: '{start_date.isoformat()}', end: '{end_date.isoformat()}' completed!"
        )
