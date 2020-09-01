import re
import sys
import time
from difflib import SequenceMatcher
from datetime import datetime, timedelta

from flask import Response, request

from apps.globals import DOCUMENTATION_URI
from apps.globals import Error
from apps.globals import HTTP
from apps.globals import MERGE
from apps.globals import NODATA_CODE
from apps.globals import ORDERBY
from apps.globals import OUTPUT
from apps.globals import SERVICE
from apps.globals import SHOW
from apps.globals import STRING_FALSE
from apps.globals import STRING_TRUE
from apps.globals import VERSION


def is_valid_integer(dimension, mini=0, maxi=sys.maxsize):
    # by default valid for positive integers
    try:
        dimension = int(dimension)
    except Exception:
        return False
    return bool(mini <= dimension <= maxi)


def is_valid_float(dimension, mini=sys.float_info.epsilon, maxi=sys.float_info.max):
    # by default valid for strictly positive floats
    try:
        dimension = float(dimension)
    except Exception:
        return False
    return bool(mini <= dimension <= maxi)


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


def is_valid_bool_string(string):
    if string is None:
        return False
    return bool(string.lower() in STRING_TRUE + STRING_FALSE)


def is_valid_output(output):
    return output.lower() in OUTPUT if output else False


def is_valid_quality(quality):
    return re.match("[DMQR*?]{1}$", quality) if quality else False


def is_valid_orderby(orderby):
    return orderby.lower() in ORDERBY if orderby else False


def is_valid_show(show):
    return show.lower() in SHOW if show else False


def is_valid_merge(merge):
    return merge.lower() in MERGE if merge else False


def is_valid_nodata(nodata):
    return nodata.lower() in NODATA_CODE if nodata else False


def currentutcday():
    return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def tictac(tic):
    return round(time.time() - tic, 2)


# Result HTTP code 400 shortcut function
def error_param(params, dmesg):
    return (params, {"msg": HTTP._400_, "details": dmesg, "code": 400})


# Error request function
def error_request(msg="", details="", code=500):
    request_date = datetime.utcnow().strftime("%Y-%b-%d %H:%M:%S UTC")
    message_error = f"""Error {code}: {msg}\n
{details}\n
Usage details are available from {DOCUMENTATION_URI}\n
Request:
{request.url}\n
Request Submitted:
{request_date}\n
Service version:
Service: {SERVICE}  version:{VERSION}"""
    return Response(message_error, status=code, mimetype="text/plain")


# Error 413 response alias
def overflow_error(dmesg):
    return error_request(msg=HTTP._413_, details=dmesg, code=413)


# Error 500 response alias
def error_500(dmesg):
    return error_request(msg=HTTP._500_, details=dmesg, code=500)


def check_request(params):
    # preliminary parameter checks

    for key, val in request.args.items():
        # stops at the first unknown parameter meet:
        if key not in params:
            ratios = ((SequenceMatcher(None, key, p).ratio(), p) for p in params)
            guess = max(ratios)
            hint = ". Did you mean " + guess[1] + " ?" if guess[0] > 0.7 else ""
            return error_param(params, Error.UNKNOWN_PARAM + key + hint)

        # find nonword chars except :
        # "," for lists "*?" for wildcards and ".:-" for date
        if re.search(r"[^a-zA-Z0-9_,*?.:-]", val):
            return error_param(params, Error.CHAR + key)

    for key, val in params.items():
        if len(request.args.getlist(key)) > 1:
            return error_param(params, Error.MULTI_PARAM + key)
        params[key] = request.args.get(key, val)

    for key, alias in params["constraints"]["alias"]:
        if key in request.args and alias in request.args:
            return error_param(
                params, f"{Error.MULTI_PARAM}{key} (and is shorthand {alias})"
            )
        if params[key] is None or params[key] == "false":
            params[key] = request.args.get(alias, params[alias])
        else:
            params[alias] = params[key]

    return (params, {"msg": HTTP._200_, "details": Error.VALID_PARAM, "code": 200})


def check_base_parameters(params, max_days=None):

    # Search for missing mandatory parameters
    for key in params["constraints"]["not_none"]:
        if params[key] is None:
            return error_param(params, Error.MISSING + key)

    # Boolean parameter validations
    for key in params["constraints"]["booleans"]:
        val = params[key]
        if not is_valid_bool_string(val):
            return error_param(params, f"Invalid {key} value: {val} {Error.BOOL}.")
        params[key] = bool(val.lower() in STRING_TRUE)

    # Float parameter validations
    for key in params["constraints"]["floats"]:
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

    for net in network:
        if not is_valid_network(net):
            return error_param(params, Error.NETWORK + net)
    for sta in station:
        if not is_valid_station(sta):
            return error_param(params, Error.STATION + sta)
    for loc in location:
        if not is_valid_location(loc):
            return error_param(params, Error.LOCATION + loc)
    for cha in channel:
        if not is_valid_channel(cha):
            return error_param(params, Error.CHANNEL + cha)

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

        if max_days and params["end"] - params["start"] > timedelta(days=max_days):
            return error_param(params, Error.TOO_LONG_DURATION + f"{max_days} days).")

    # Search for empty selection
    if params["network"] == params["station"] == params["channel"] == "*":
        return error_param(params, Error.NO_SELECTION)

    return (params, {"msg": HTTP._200_, "details": Error.VALID_PARAM, "code": 200})
