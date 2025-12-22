import logging
from fnmatch import fnmatch
from flask import current_app
from .redis_client import RedisClient
from pymongo import MongoClient
from datetime import timedelta

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


def mongo_request(paramslist):
    """Build and run WFCatalog MongoDB queries using request query parameters

    Args:
        paramslist ([]): List of lists containing URL query parameters

    Returns:
        []: MongoDB queries used to obtain data
        []: List of metrics extracted from the MongoDB
    """
    db_host = current_app.config["MONGODB_HOST"]
    db_port = current_app.config["MONGODB_PORT"]
    db_usr = current_app.config["MONGODB_USR"]
    db_pwd = current_app.config["MONGODB_PWD"]
    db_name = current_app.config["MONGODB_NAME"]
    # db_max_rows = current_app.config["MONGODB_MAX_ROWS"]

    result = []

    # List of queries executed agains the DB, let's keep it for logging
    qries = []
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

        db = MongoClient(
            db_host,
            db_port,
            username=db_usr,
            password=db_pwd,
            authSource=db_name,
        ).get_database(db_name)

        qries.append(qry)

        cursor = db.availability.find(qry, projection=PROJ)

        # Eager query execution instead of a cursor
        result += _apply_restricted_bit(cursor, params.get("includerestricted", False))

    # Result needs to be sorted, this seems to be required by the fusion step
    result.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]))

    return qries, result


def crop_datetimes(params: dict):
    """Extract and crop start/end query parameters.

    Args:
        params (dict): Dictionary containing original query parameters.

    Returns:
        tuple: Tuple containing cropped start/end parameters.
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


def _apply_restricted_bit(data: list, include_restricted: bool = False) -> list:
    """Removes entries which do not appear in the station inventory and applies
    restricted bit information based on cross-section between rows obtained
    from the DB and list of SEED Identifiers having restricted epochs.

    Args:
        data (list): List of entries obtained from the DB.
        include_restricted (bool): If True, return all data. If False, return only open data.

    Returns:
        list: List of entries obtained from the DB, but filtered and having
        restricted information applied from cache.
    """

    results = []

    for segment in data:
        sid = ".".join([segment["net"], segment["sta"], segment["loc"], segment["cha"]])

        if sid not in RESTRICTED_INVENTORY._known_seedIDs:
            continue

        if sid in RESTRICTED_INVENTORY._restricted_seedIDs:
            segment["restr"] = _get_restricted_status(segment)
            if segment["restr"] == "RESTRICTED" and not include_restricted:
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


def _expand_wildcards(params):
    """Expand generic query parameters to actual ones based on cached inventory.

    Args:
        params (list): List of query parameters.

    Returns:
        list: List of expanded query parameters.
    """
    global RESTRICTED_INVENTORY

    if not RESTRICTED_INVENTORY:
        RESTRICTED_INVENTORY = RestrictionInventory(
            current_app.config["CACHE_HOST"],
            current_app.config["CACHE_PORT"],
            current_app.config["CACHE_INVENTORY_KEY"],
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


def _get_restricted_status(segment):
    """Gets the restricted status of provided daily stream.

    Args:
        daily_stream (dict): Daily stream dictionary from WFCatalog DB.

    Returns:
        string: Restricted status, `None` if unknown.
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


def collect_data(params):
    """Get the result of the Mongo query."""
    rc = RedisClient(current_app.config["CACHE_HOST"], current_app.config["CACHE_PORT"])

    CACHED_REQUEST_KEY = str(hash(str(params)))

    # Try to get cached response for given params
    cached = rc.get(CACHED_REQUEST_KEY)
    if cached:
        return cached

    data = None
    logging.debug("Start collecting data from WFCatalog DB...")
    qry, data = mongo_request(params)
    rc.set(CACHED_REQUEST_KEY, data, current_app.config["CACHE_RESP_PERIOD"])

    logging.debug(qry)

    return data
