"""
WFCatalog Client Module for ws-availability.

This module handles interactions with the WFCatalog (MongoDB) and the Station
Inventory (for restriction checks). It constructs MongoDB queries, retrieves
availability metrics, and applies access restrictions based on cached inventory data.
It also manages caching logic using Redis.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from fnmatch import fnmatch
# from flask import current_app (Removed)
from .redis_client import RedisClient
from pymongo import MongoClient, ASCENDING
from datetime import datetime, timedelta
from typing import Any

from .restriction import RestrictionInventory
from .globals import Error

try:
    import sentry_sdk
except ImportError:  # pragma: no cover - sentry_sdk is an optional runtime dep
    sentry_sdk = None


@contextmanager
def _sentry_span(op: str, name: str, **tags: str):
    """Open a Sentry span if the SDK is available; no-op otherwise."""
    if sentry_sdk is None:
        yield None
        return
    with sentry_sdk.start_span(op=op, name=name) as span:
        for k, v in tags.items():
            try:
                span.set_tag(k, v)
            except Exception:  # pragma: no cover - tag failures must not break the request
                pass
        yield span

RESTRICTED_INVENTORY = None

PROJ = {
    "_id": 0,
    "net": 1,
    "sta": 1,
    "loc": 1,
    "cha": 1,
    "qlt": 1,
    "srate": 1,
    "ts": 1,
    "te": 1,
    "created": 1,
    "count": 1,
    "restr": 1,
}


from apps.settings import settings


# Global DB Client to prevent thread exhaustion
DB_CLIENT = None

def get_db_client():
    global DB_CLIENT
    if DB_CLIENT is None:
        # When fan-out is enabled, each worker may run up to fanout_max_workers
        # cursors in parallel — give the pool enough connections to serve them.
        pool_size = (
            max(1, settings.fanout_max_workers) if settings.fanout_enabled else 1
        )
        DB_CLIENT = MongoClient(
            settings.mongodb_host,
            settings.mongodb_port,
            username=settings.mongodb_usr,
            password=settings.mongodb_pwd,
            authSource=settings.mongodb_auth_source or settings.mongodb_name,
            maxPoolSize=pool_size,
            connect=False,
            directConnection=True,
            retryReads=False,
            retryWrites=False
        )
        try:
            db = DB_CLIENT.get_database(settings.mongodb_name)
            db.availability.create_index(
                [("net", ASCENDING), ("sta", ASCENDING), ("loc", ASCENDING), 
                 ("cha", ASCENDING), ("ts", ASCENDING), ("te", ASCENDING)],
                background=True
            )
            logging.getLogger(__name__).info("Ensured MongoDB compound index is present on 'availability' collection.")
        except Exception as e:
            logging.getLogger(__name__).warning("Failed to verify/create MongoDB indexes: %s", e)
            
    return DB_CLIENT

def mongo_request(paramslist: list[dict]) -> tuple[list[dict], list[list[Any]]]:
    """
    Constructs and executes MongoDB queries to retrieve availability metrics.

    Args:
        paramslist: List of dictionaries containing URL query parameters.

    Returns:
        A tuple containing:
        - qries (list): List of executed MongoDB query objects (for logging).
        - result (list): Aggregated list of metric records extracted from the DB.
    """
    db_name = settings.mongodb_name

    result = []

    # List of queries executed agains the DB, let's keep it for logging
    qries = []

    # Use GLOBAL client (Fix for Connection Churn & Thread Exhaustion)
    client = get_db_client()
    db = client.get_database(db_name)

    with _sentry_span("db.mongo", "mongo_request"):
        for params in paramslist:
            params = _expand_wildcards(params)
            # Crop datetimes to accomodate sub-segment queries.
            # e.g. net=NL&sta=HGN&start=2018-01-06T06:00:00&end=2018-01-06T12:00:00
            # when we have one 24h segment for 2018-01-06
            start, end = crop_datetimes(params)
            qry = _build_query(params, start, end)

            qries.append(qry)
            include_restricted = params.get("includerestricted", False)

            if _should_fanout(start, end):
                shard_results = _run_fanout(db, qry, start, end, include_restricted)
                for shard in shard_results:
                    result += shard
                    if len(result) > settings.max_data_rows:
                        # Stop early: the row cap is enforced in get_output().
                        break
            else:
                # LAYER 4: Cap the MongoDB cursor
                cursor = db.availability.find(
                    qry, projection=PROJ
                ).limit(settings.max_data_rows + 1)
                result += _apply_restricted_bit(cursor, include_restricted)

    # Result needs to be sorted, this seems to be required by the fusion step
    result.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]))

    return qries, result


def _build_query(params: dict, start: datetime | None, end: datetime | None) -> dict:
    """Build the MongoDB filter dict shared by single-shot and fan-out paths.

    Field insertion order is intentional: it matches the compound index
    {net, sta, loc, cha, ts, te} so MongoDB's planner picks it up implicitly
    (Issue #51). `qlt` is not in the index, so it goes last.
    """
    qry: dict = {}
    if params["network"] != "*":
        qry["net"] = {"$in": params["network"].split(",")}
    if params["station"] != "*":
        qry["sta"] = {"$in": params["station"].split(",")}
    if params["location"] != "*":
        qry["loc"] = {"$in": params["location"].split(",")}
    if params["channel"] != "*":
        qry["cha"] = {"$in": params["channel"].split(",")}
    if end is not None:
        qry["ts"] = {"$lt": end}
    if start is not None:
        qry["te"] = {"$gt": start}
    if params["quality"] != "*":
        qry["qlt"] = {"$in": params["quality"].split(",")}
    return qry


def _should_fanout(start: datetime | None, end: datetime | None) -> bool:
    """Decide whether to split this query across parallel time shards."""
    if not settings.fanout_enabled:
        return False
    if start is None or end is None:
        return False
    if (end - start).days < settings.fanout_min_days:
        return False
    return True


def _split_windows(
    start: datetime, end: datetime, window_days: int
) -> list[tuple[datetime, datetime]]:
    """Slice [start, end) into day-aligned windows of at most window_days each."""
    if window_days <= 0:
        window_days = 1
    step = timedelta(days=window_days)
    windows: list[tuple[datetime, datetime]] = []
    cur = start
    while cur < end:
        nxt = min(cur + step, end)
        windows.append((cur, nxt))
        cur = nxt
    return windows


def _run_shard(
    db: Any,
    qry_base: dict,
    w_start: datetime,
    w_end: datetime,
    include_restricted: bool,
) -> list[list[Any]]:
    """Execute a single time-window shard and return restricted-filtered rows."""
    shard_qry = dict(qry_base)
    shard_qry["te"] = {"$gt": w_start}
    shard_qry["ts"] = {"$lt": w_end}

    with _sentry_span(
        "db.mongo.shard",
        "availability.find",
        ts_start=w_start.isoformat(),
        ts_end=w_end.isoformat(),
    ):
        cursor = db.availability.find(shard_qry, projection=PROJ).limit(
            settings.max_data_rows + 1
        )
        return _apply_restricted_bit(cursor, include_restricted)


def _run_fanout(
    db: Any,
    qry_base: dict,
    start: datetime,
    end: datetime,
    include_restricted: bool,
) -> list[list[list[Any]]]:
    """Dispatch shards onto a thread pool and return their results in order."""
    windows = _split_windows(start, end, settings.fanout_window_days)
    workers = min(settings.fanout_max_workers, len(windows)) or 1
    logging.debug(
        "Fanning out mongo_request across %d windows with %d workers",
        len(windows),
        workers,
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(
            pool.map(
                lambda w: _run_shard(db, qry_base, w[0], w[1], include_restricted),
                windows,
            )
        )


def crop_datetimes(params: dict) -> tuple[datetime | None, datetime | None]:
    """
    Extracts and normalizes start/end datetimes for querying.

    Crops time by rounding to the nearest day start/end if necessary, 
    to accommodate sub-segment queries logic.

    Args:
        params: Dictionary containing original query parameters.

    Returns:
        A tuple containing cropped (start, end) datetimes.
    """
    start_cropped, end_cropped = None, None

    if params["start"]:
        start_cropped = params["start"].replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    if params["end"]:
        end_cropped = params["end"].replace(hour=0, minute=0, second=0, microsecond=0)
        end_cropped += timedelta(days=1)

    return start_cropped, end_cropped


def _apply_restricted_bit(data: Any, include_restricted: bool = False) -> list[list[Any]]:
    """
    Filters data based on restricted status from the inventory.

    Checks each data segment against the restricted inventory cache. If data
    is restricted and `include_restricted` is False, it is excluded.

    Args:
        data: Cursor or list of availability documents from MongoDB.
        include_restricted: If True, restricted data is included. 
                           If False, only "OPEN" data is returned.

    Returns:
        List of filtered availability records with restriction status applied.
    """

    results = []

    for segment in data:
        sid = ".".join([segment["net"], segment["sta"], segment["loc"], segment["cha"]])

        if sid not in RESTRICTED_INVENTORY._known_seedIDs:
            continue
            
        # FIX Issue #23: Filter out invalid data where Start Time > End Time
        # This prevents merge logic failures due to negative duration segments
        if segment["ts"] > segment["te"]:
            continue

        if sid in RESTRICTED_INVENTORY._restricted_seedIDs:
            segment["restr"] = _get_restricted_status(segment)
            if segment["restr"] in ["RESTRICTED", "PARTIAL"] and not include_restricted:
                continue

        results.append(
            [
                segment["net"],
                segment["sta"],
                segment["loc"] if segment["loc"] else "--",  # Convert empty location to '--'
                segment["cha"],
                segment["qlt"],
                segment["srate"],
                segment["ts"],
                segment["te"],
                segment["created"],
                segment["restr"],
                segment["count"],
            ]
        )

    return results


def _expand_wildcards(params: dict) -> dict:
    """
    Expands wildcard query parameters based on cached inventory.

    Matches wildcards (e.g., "H?N", "*") against the known inventory to produce
    explicit lists of networks, stations, etc., for the database query.

    Args:
        params: Dictionary of query parameters.

    Returns:
        Dictionary with expanded parameters (wildcards replaced by concrete lists).
    """
    global RESTRICTED_INVENTORY

    if not RESTRICTED_INVENTORY:
        RESTRICTED_INVENTORY = RestrictionInventory(
            settings.cache_host,
            settings.cache_port,
            settings.cache_inventory_key,
        )

    _net = []
    _sta = []
    _loc = []
    _cha = []

    # Filter the cached inventory on network level.
    for net in params["network"].split(","):
        _net += [e for e in RESTRICTED_INVENTORY._inv if fnmatch(e.split(".")[0], net)]

    # Filter the cached inventory on station level.
    for sta in params["station"].split(","):
        _sta += [e for e in _net if fnmatch(e.split(".")[1], sta)]

    # Filter the cached inventory on location level.
    for loc in params["location"].split(","):
        if loc == '--':
            loc = ''
        _loc += [e for e in _sta if fnmatch(e.split(".")[2], loc)]

    # Filter the cached inventory on channel level.
    for cha in params["channel"].split(","):
        _cha += [e for e in _loc if fnmatch(e.split(".")[3], cha)]

    # Replace original query parameters with ones filtered out from the cached inventory.
    stream_count = len(_cha)
    
    # LAYER 3: Breadth Check
    # Rule A: Hard limit on number of streams
    if stream_count > settings.max_streams:
        raise ValueError(Error.TOO_MANY_STREAMS)
        
    # Rule B: Broad query (many streams + no time range)
    # Using 500 as the "broadness" threshold as discussed
    no_time_range = params.get("start") is None and params.get("end") is None
    if stream_count > 500 and no_time_range:
        raise ValueError(Error.BROAD_QUERY)

    params["network"] = ",".join(set([e.split(".")[0] for e in _cha]))
    params["station"] = (
        "*"
        if params["station"] == "*"
        else ",".join(set([e.split(".")[1] for e in _cha]))
    )
    params["location"] = (
        "*"
        if params["location"] == "*"
        else ",".join(set([e.split(".")[2] for e in _cha]))
    )
    params["channel"] = (
        "*"
        if params["channel"] == "*"
        else ",".join(set([e.split(".")[3] for e in _cha]))
    )

    return params


def _get_restricted_status(segment: dict) -> str | None:
    """
    Retrieves the restricted status for a specific data segment.

    Args:
        segment: Dictionary representing a data segment (must contain 'net',
                 'sta', 'loc', 'cha', 'ts', 'te').

    Returns:
        String status ("OPEN", "RESTRICTED", etc.) or None if unknown.
    """
    global RESTRICTED_INVENTORY

    if not RESTRICTED_INVENTORY:
        RESTRICTED_INVENTORY = RestrictionInventory()

    r = RESTRICTED_INVENTORY.is_restricted(
        f"{segment['net']}.{segment['sta']}.{segment['loc']}.{segment['cha']}",
        segment["ts"].date(),
        segment["te"].date(),
    )

    if r:
        return r.name
    else:
        return None


def collect_data(params: dict) -> list[list[Any]] | None:
    """
    Orchestrates the data collection process with caching.

    First checks Redis cache for the given parameters. If not found, executes
    the MongoDB query, caches the result, and returns it.

    Args:
        params: list of parameter dictionaries.

    Returns:
        List of data records or None.
    """
    rc = RedisClient(settings.cache_host, settings.cache_port)

    CACHED_REQUEST_KEY = str(hash(str(params)))

    # Try to get cached response for given params
    cached = rc.get(CACHED_REQUEST_KEY)
    if cached:
        return cached

    data = None
    logging.debug("Start collecting data from WFCatalog DB...")
    qry, data = mongo_request(params)
    rc.set(CACHED_REQUEST_KEY, data, settings.cache_resp_period)

    logging.debug(qry)

    return data
