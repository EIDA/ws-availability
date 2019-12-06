import os
import re
import sys

from difflib import SequenceMatcher
from datetime import datetime, timedelta
from configparser import ConfigParser

from flask import Response, request

from apps.globals import DATABASE_CONFIG_FILE
from apps.globals import Error
from apps.globals import HTTP
from apps.globals import MERGE
from apps.globals import NODATA
from apps.globals import ORDERBY
from apps.globals import OUTPUT
from apps.globals import SHOW
from apps.globals import STRING_FALSE
from apps.globals import STRING_TRUE

from apps.availability.constants import VERSION


def is_valid_integer(dimension, mini=0, maxi=sys.maxsize):
    try:
        dimension = int(dimension)
        if mini <= dimension <= maxi:
            return True
    except Exception:
        return False


def is_valid_float(dimension, mini=sys.float_info.epsilon, maxi=sys.maxsize):
    try:
        dimension = float(dimension)
        if mini <= dimension <= maxi:
            return True
    except Exception:
        return False


def is_valid_datetime(date):
    for df in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(date, df)
        except (ValueError, TypeError):
            pass


def is_valid_starttime(date):
    return is_valid_datetime(date) or date == "currentutcday"


def is_valid_endtime(date):
    return is_valid_datetime(date) or date == "currentutcday" or is_valid_integer(date)


def is_valid_network(network):
    return re.match("[A-Za-z0-9*?]{1,2}$", network) if network else False


def is_valid_station(station):
    return re.match("[A-Za-z0-9*?]{1,5}$", station) if station else False


def is_valid_location(location):
    return re.match("([A-Za-z0-9*?-]{1,2})$", location) if location else False


def is_valid_channel(channel):
    return re.match("([A-Za-z0-9*?]{1,3})$", channel) if channel else False


def is_valid_quality(quality):
    return re.match("[DMQR*?]{1}$", quality) if quality else False


def is_valid_bool_string(string):
    if string is None:
        return False
    return True if string.lower() in (STRING_TRUE + STRING_FALSE) else False


def is_valid_output(output):
    return output.lower() in OUTPUT if output else False


def is_valid_orderby(orderby):
    return orderby.lower() in ORDERBY if orderby else False


def is_valid_show(show):
    return show.lower() in SHOW if show else False


def is_valid_merge(merge):
    return merge.lower() in MERGE if merge else False


def is_valid_nodata(nodata):
    return nodata.lower() in NODATA if nodata else False


def currentutcday():
    return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


# Result HTTP code 400 shortcut function
def error_param(params, dmesg):
    return (params, {"msg": HTTP._400_, "details": dmesg, "code": 400})


# Error request function
def error_request(msg=" ", details=" ", code=" "):
    request_date = datetime.utcnow().strftime("%Y-%b-%d %H:%M:%S UTC")
    message_error = f"Error {code}: {msg} Please mention your request URL when asking for support\n\n\
    More Details: {details}\n\n\
    Request: {request.url}\n\
    Request Submitted: {request_date} \n\
    Service version: version {VERSION}"
    return Response(message_error, status=code, mimetype="*/*")


# Error 413 response alias
def overflow_error(dmesg):
    return error_request(msg=HTTP._413_, details=dmesg, code=413)


# Error 500 response alias
def error_500(dmesg):
    return error_request(msg=HTTP._500_, details=dmesg, code=500)


# Read database config
def config(filename=DATABASE_CONFIG_FILE, section="postgresql"):
    if os.path.isfile(filename):
        parser = ConfigParser()
        parser.read(filename)
        db = {}
        if parser.has_section(section):
            params = parser.items(section)
            for param in params:
                db[param[0]] = param[1]
        else:
            raise Exception(f"Section {section} not found in the {filename} file")
        return db
    else:
        print(f"{DATABASE_CONFIG_FILE} not found")


# check request
def check_request(request, params, alias):
    for key, val in request.args.items():
        if key not in params:
            ratios = [SequenceMatcher(None, key, p).ratio() for p in params]
            guess = max([(v, params[ind]) for ind, v in enumerate(ratios)])
            hint = ". Did you mean " + guess[1] + " ?" if guess[0] > 0.7 else ""
            return error_param(params, Error.UNKNOWN_PARAM + key + hint)

        # find non word char except :
        # "," for lists "*?" for wilcards and ".:-" for date
        if re.search(r"[^a-zA-Z0-9_,*?.:-]", val):
            return error_param(params, Error.CHAR + key)

    for key in params:
        if len(request.args.getlist(key)) > 1:
            return error_param(params, Error.MULTI_PARAM + str(key))

    for key in alias:
        if len([v for v in key if v in request.args]) > 1:
            return error_param(params, Error.MULTI_PARAM + str(key))

    return (params, {"msg": HTTP._200_, "details": Error.VALID_PARAM, "code": 200})


def check_base_parameters(
    params, max_days=None, not_none=None, booleans=None, floats=None
):

    if max_days is None:
        max_days = 10 ** 9 - 1

    # Search for missing mandatory parameters
    if not_none is not None:
        for key in not_none:
            if params[key] is None:
                return error_param(params, Error.MISSING + key)

    # Boolean parameter validations
    if booleans is not None:
        for key in booleans:
            val = params[key]
            if not is_valid_bool_string(val):
                return error_param(params, f"Invalid {key} value: {val} {Error.BOOL}.")
            params[key] = True if val.lower() in STRING_TRUE else False

    # Float parameter validations
    if floats is not None:
        for key in floats:
            val = params[key]
            if is_valid_float(val):
                params[key] = float(val)
            elif val is not None:
                return error_param(params, f"Invalid {key} value: {val}")

    # Station validations
    if params["network"].lower() == "temporary":
        params["network"] = "0?,1?,2?,3?,4?,5?,6?,7?,8?,9?,X?,Y?,Z?"

    network = params["network"].split(",")
    station = params["station"].split(",")
    location = params["location"].split(",")
    channel = params["channel"].split(",")

    for n in network:
        if not is_valid_network(n):
            return error_param(params, Error.NETWORK + n)
    for s in station:
        if not is_valid_station(s):
            return error_param(params, Error.STATION + s)
    for l in location:
        if not is_valid_location(l):
            return error_param(params, Error.LOCATION + l)
    for c in channel:
        if not is_valid_channel(c):
            return error_param(params, Error.CHANNEL + c)

    # Start time and end time validations
    if params["start"] is not None:
        if not is_valid_starttime(params["start"]):
            return error_param(params, Error.TIME + str(params["start"]))

        if is_valid_datetime(params["start"]):
            params["start"] = is_valid_datetime(params["start"])
        elif params["start"] == "currentutcday":
            params["start"] = currentutcday()

    if params["end"] is not None:
        if not is_valid_endtime(params["end"]):
            return error_param(params, Error.TIME + str(params["end"]))

        if is_valid_datetime(params["end"]):
            params["end"] = is_valid_datetime(params["end"])
        elif params["end"] == "currentutcday":
            params["end"] = currentutcday()

    if params["start"] is not None and params["end"] is not None:
        if is_valid_integer(params["start"]) and is_valid_integer(params["end"]):
            params["start"] = currentutcday() - timedelta(seconds=int(params["start"]))
            params["end"] = currentutcday() + timedelta(seconds=int(params["end"]))

        if is_valid_integer(params["end"]):
            params["end"] = params["start"] + timedelta(seconds=int(params["end"]))

        if params["start"] > params["end"]:
            start = str(params["start"])
            end = str(params["end"])
            return error_param(params, Error.START_LATER + start + " > " + end)

        if params["end"] - params["start"] > timedelta(days=max_days):
            return error_param(params, Error.TOO_LONG_DURATION + f"{max_days} days).")

    # Search for empty selection
    if params["network"] == params["station"] == params["channel"] == "*":
        return error_param(params, Error.NO_SELECTION)

    return (params, {"msg": HTTP._200_, "details": Error.VALID_PARAM, "code": 200})
