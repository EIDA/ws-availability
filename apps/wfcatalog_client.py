"""
WFCatalog Client Module for ws-availability.

This module handles interactions with the WFCatalog (MongoDB) and the Station
Inventory (for restriction checks). It constructs MongoDB queries, retrieves
availability metrics, and applies access restrictions based on cached inventory data.
It also manages caching logic using Redis.
"""
import logging
from fnmatch import fnmatch
# from flask import current_app (Removed)
from .redis_client import RedisClient
from pymongo import MongoClient
from datetime import datetime, timedelta
from typing import Any

from .restriction import RestrictionInventory

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
    db_host = settings.mongodb_host
    db_port = settings.mongodb_port
    db_usr = settings.mongodb_usr
    db_pwd = settings.mongodb_pwd
    db_name = settings.mongodb_name

    result = []

    # List of queries executed agains the DB, let's keep it for logging
    qries = []
    
    # Initialize DB connection ONCE (Fix for Connection Churn)
    with MongoClient(
        db_host,
        db_port,
        username=db_usr,
        password=db_pwd,
        authSource=db_name,
        maxPoolSize=1,
        connect=False,
        directConnection=True,
        retryReads=False,
        retryWrites=False
    ) as client:
        db = client.get_database(db_name)
        
        for params in paramslist:
            params = _expand_wildcards(params)
            # Crop datetimes to accomodate sub-segment queries.
            # e.g. net=NL&sta=HGN&start=2018-01-06T06:00:00&end=2018-01-06T12:00:00
            # when we have one 24h segment for 2018-01-06
            start, end = crop_datetimes(params)
            qry = {}
            if params["network"] != "*":
                network = {"$in": params["network"].split(",")}
                qry["net"] = network
            if params["station"] != "*":
                station = {"$in": params["station"].split(",")}
                qry["sta"] = station
            if params["location"] != "*":
                location = {"$in": params["location"].split(",")}
                qry["loc"] = location
            if params["channel"] != "*":
                qry["cha"] = {"$in": params["channel"].split(",")}
            if params["quality"] != "*":
                quality = {"$in": params["quality"].split(",")}
                qry["qlt"] = quality
            if start:
                ts = {"$gte": start}
                qry["ts"] = ts
            if end:
                te = {"$lte": end}
                qry["te"] = te

            qries.append(qry)

            cursor = db.availability.find(qry, projection=PROJ)

            # Eager query execution instead of a cursor
            result += _apply_restricted_bit(cursor, params.get("includerestricted", False))

        # Result needs to be sorted, this seems to be required by the fusion step
        result.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]))

    return qries, result


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

        if sid in RESTRICTED_INVENTORY._restricted_seedIDs:
            segment["restr"] = _get_restricted_status(segment)
            if segment["restr"] in ["RESTRICTED", "PARTIAL"] and not include_restricted:
                continue

        results.append(
            [
                segment["net"],
                segment["sta"],
                segment["loc"],
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
