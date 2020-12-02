import time
import logging
import re

from flask import current_app

from apps.utils import tictac

from pymongo import MongoClient
from bson.objectid import ObjectId


def mongo_request(paramslist):
    """Build and run WFCatalog MongoDB request using request query parameters

    Args:
        paramslist ([]): List of URL query parameters

    Returns:
        string: MongoDB query used to obtain data
        []: List of metrics extracted from the MongoDB
    """
    db_host = current_app.config["MONGODB_HOST"]
    db_port = current_app.config["MONGODB_PORT"]
    db_usr = current_app.config["MONGODB_USR"]
    db_pwd = current_app.config["MONGODB_PWD"]
    db_name = current_app.config["MONGODB_NAME"]

    result = []
    network = "*"
    station = "*"
    location = "*"
    channel = "*"
    quality = "*"

    qry = {}

    for params in paramslist:
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
            qry["cha"] = _query_params_to_regex(params["channel"])
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
        password=db_pwd
    ).get_database(db_name)

    d_streams = db.daily_streams.find(qry)
    for ds in d_streams:
        ds_id = ObjectId(ds["_id"])
        ds_avail = float(ds["avail"])

        if ds_avail >= 100:
            # If availability = 100, just add it to the set (no c_segments present)
            ds_elem = _parse_daily_stream_to_list(ds)
            result.append(ds_elem)
        else:
            # If availability < 100, collect the continuous segments
            c_segs = db.c_segments.find({"streamId": ds_id})
            for cs in c_segs:
                c_seg_elem = _parse_c_segment_to_list(ds, cs)
                result.append(c_seg_elem)

    return qry, result


def _query_params_to_regex(str):
    """Parse list of params into a regular expression

    Args:
        str (string): Comma-separated parameters

    Returns:
        obj: Compiled regular expression
    """
    # Split the string by comma and put in in a list
    split = str.split(",")
    # Replace question marks with commas (regex any char)
    wildcards = [s.replace("?", ".") for s in split]
    # Add start and end of string
    regex = "^" + "|".join(wildcards) + "$"
    # Compile and return
    return re.compile(regex, re.IGNORECASE)


def _parse_daily_stream_to_list(daily_stream):
    """Parse the daily stream JSON document

    Args:
        daily_stream (string): Daily stream representation in JSON format

    Returns:
        []: List with daily stream metrics
    """
    result = [
        daily_stream["net"],
        daily_stream["sta"],
        daily_stream["loc"],
        daily_stream["cha"],
        daily_stream["qlt"],
        daily_stream["srate"][0],
        daily_stream["ts"],
        daily_stream["te"],
        daily_stream["created"],
        daily_stream["status"].upper(),
        1,
    ]
    return result


def _parse_c_segment_to_list(daily_stream, c_segment):
    """Parse the daily stream and continuous segments JSON documents

    Args:
        daily_stream (string): Daily stream representation in JSON format
        c_segment (string): Continuous segment representation in JSON format

    Returns:
        []: List with continuous segment metrics wrapped around daily stream
    """
    result = [
        daily_stream["net"],
        daily_stream["sta"],
        daily_stream["loc"],
        daily_stream["cha"],
        daily_stream["qlt"],
        c_segment["srate"],
        c_segment["ts"],
        c_segment["te"],
        daily_stream["created"],
        daily_stream["status"].upper(),
        1,
    ]
    return result


def collect_data(params):
    """ Get the result of the Mongo query. """
    data = None
    logging.debug("Start collecting data from WFCatalog DB...")

    qry, data = mongo_request(params)
    logging.debug(qry)

    return data
