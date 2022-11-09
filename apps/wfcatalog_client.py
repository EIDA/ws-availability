import logging
from fnmatch import fnmatch

from flask import current_app
from pymemcache import serde
from pymemcache.client import base
from pymongo import MongoClient

from .restriction import RestrictionInventory, Restriction

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
        if params["start"]:
            ts = {"$gte": params["start"]}
            qry["ts"] = ts
        if params["end"]:
            te = {"$lte": params["end"]}
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
        data = list(cursor)

        # Assign restricted data information from cache
        for d in data:
            d["restr"] = _get_restricted_status(d)
            if d["restr"]:
                result.append([d[key] for key in d.keys()])
            else:
                logging.debug(f"Metadata mismatch for {d=}")

    # Result needs to be sorted, this seems to be required by the fusion step
    # result = [[row[k] for k in row.keys()] for row in result]
    result.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]))

    return qries, result


def _apply_restricted_bit(data):
    restricted = [
        RESTRICTED_INVENTORY._inv[r]
        for r in RESTRICTED_INVENTORY._inv
        if r in set([f"{r['net']}.{r['sta']}.{r['loc']}.{r['cha']}" for r in data])
    ]
    restricted = [
        [d for d in r if d.restriction == Restriction.RESTRICTED] for r in restricted
    ]
    raise NotImplementedError


def _query_params_to_regex(str):
    """Parse list of params into a regular expression
    Args:
        str (string): Comma-separated parameters
    Returns:
        obj: Compiled regular expression
    """
    # Split the string by comma and put in in a list
    split = str.split(",")
    # Replace question marks with regexp equivalent
    split = [s.replace("?", ".") for s in split]
    # Replace wildcards marks with regexp equivalent
    split = [s.replace("*", ".*") for s in split]
    # Add start and end of string
    regex = "|".join(split)
    # Compile and return
    # return re.compile(regex, re.IGNORECASE)
    return f"{regex}"


def _expand_wildcards(params):
    global RESTRICTED_INVENTORY

    if not RESTRICTED_INVENTORY:
        RESTRICTED_INVENTORY = RestrictionInventory()

    _net = []
    _sta = []
    _loc = []
    _cha = []

    for net in params["network"].split(","):
        _net += [e for e in RESTRICTED_INVENTORY._inv if fnmatch(e.split(".")[0], net)]

    for sta in params["station"].split(","):
        _sta += [e for e in _net if fnmatch(e.split(".")[1], sta)]

    for loc in params["location"].split(","):
        _loc += [e for e in _sta if fnmatch(e.split(".")[2], loc)]

    for cha in params["channel"].split(","):
        _cha += [e for e in _loc if fnmatch(e.split(".")[3], cha)]

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
        f"{segment['net']}.{segment['sta']}..{segment['cha']}",
        segment["ts"].date(),
        segment["te"].date(),
    )

    if r:
        return r.name
    else:
        return None


def collect_data(params):
    """Get the result of the Mongo query."""
    cache_host = current_app.config["CACHE_HOST"]
    cache_port = current_app.config["CACHE_PORT"]
    cache_resp_period = current_app.config["CACHE_RESP_PERIOD"]

    client = base.Client((cache_host, cache_port), serde=serde.pickle_serde)
    CACHED_REQUEST_KEY = str(hash(str(params)))

    # Try to get cached response for given params
    if client.get(CACHED_REQUEST_KEY):
        return client.get(CACHED_REQUEST_KEY)

    data = None
    logging.debug("Start collecting data from WFCatalog DB...")
    qry, data = mongo_request(params)
    client.set(CACHED_REQUEST_KEY, data, cache_resp_period)

    logging.debug(qry)

    return data
