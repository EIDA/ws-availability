import logging

from flask import current_app
from pymemcache import serde
from pymemcache.client import base
from pymongo import MongoClient

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

    # NO REGEX
    for params in paramslist:
        qry = {"$and": []}
        if params["network"] != "*":
            qry["$and"].append(
                {"$or": [{"net": n} for n in params["network"].split(",")]}
            )
        if params["station"] != "*":
            qry["$and"].append(
                {"$or": [{"sta": s} for s in params["station"].split(",")]}
            )
        if params["location"] != "*":
            qry["$and"].append(
                {"$or": [{"loc": l} for l in params["location"].split(",")]}
            )
        if params["channel"] != "*":
            qry["$and"].append(
                {"$or": [{"cha": c} for c in params["channel"].split(",")]}
            )
        if params["quality"] != "*":
            qry["$and"].append(
                {"$or": [{"qlt": q} for q in params["quality"].split(",")]}
            )
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

        cursor = db.availability.find(qry, projection=PROJ)
        result = list(cursor)

        # Assign restricted data information from cache
        # for c in cursor:
        # c["restr"] = _get_restricted_status(c)
        # result.append([c[key] for key in c.keys()])

    # Result needs to be sorted, this seems to be required by the fusion step
    result.sort(key=lambda x: (x["net"], x["sta"], x["loc"], x["cha"], x["ts"]))

    return qries, result


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


def _get_restricted_status(segment):
    """Gets the restricted status of provided daily stream.

    Args:
        daily_stream (dict): Daily stream dictionary from WFCatalog DB.

    Returns:
        string: Restricted status, `None` if unknown.
    """
    global RESTRICTED_INVENTORY

    if not RESTRICTED_INVENTORY:
        fdsnws_station_url = current_app.config["FDSNWS_STATION_URL"]
        RESTRICTED_INVENTORY = RestrictionInventory(fdsnws_station_url)

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
