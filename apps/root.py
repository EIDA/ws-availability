import io
import logging
import multiprocessing as mp
import queue
import re

from flask import request

from apps.data_access_layer import get_output
from apps.globals import (HTTP, MAX_DATA_ROWS, MAX_DAYS, MAX_MERGEGAPS,
                          TIMEOUT, Error)
from apps.parameters import Parameters
from apps.utils import (check_base_parameters, check_request, error_param,
                        error_request, is_valid_float, is_valid_integer,
                        is_valid_merge, is_valid_nodata, is_valid_orderby,
                        is_valid_output, is_valid_quality, is_valid_show)

mp.set_start_method("fork")


def check_parameters(params):

    # check base parameters
    (params, error) = check_base_parameters(params, MAX_DAYS)
    if error["code"] != 200:
        return (params, error)

    params["extent"] = bool("/extent" in params["base_url"])

    quality = params["quality"].split(",")
    for q in quality:
        logging.debug(q)
        if not is_valid_quality(q):
            return error_param(params, Error.QUALITY + q)

    # Integer parameter validations.
    if is_valid_integer(params["limit"]):
        params["limit"] = int(params["limit"])
    elif params["limit"] is not None:
        return error_param(params, Error.ROWLIMIT + str(params["limit"]))
    elif params["limit"] is None:
        params["limit"] = MAX_DATA_ROWS

    # orderby parameter validation
    if params["orderby"] is not None:
        if not is_valid_orderby(params["orderby"]):
            return error_param(params, Error.ORDERBY + str(params["orderby"]))
        params["orderby"] = params["orderby"].lower()
    else:
        params["orderby"] = "nslc_time_quality_samplerate"

    # show parameter validation
    if params["show"]:
        params["show"] = params["show"].split(",")
        for ind, show in enumerate(params["show"]):
            if not is_valid_show(show):
                return error_param(params, Error.SHOW + str(show))
            params["show"][ind] = show.lower()

    if params["extent"]:
        params["showlastupdate"] = True
    elif "latestupdate" in params["show"] or "latestupdate" in params["orderby"]:
        params["showlastupdate"] = True
    else:
        params["showlastupdate"] = False

    # merge parameter validation
    if params["merge"]:
        params["merge"] = params["merge"].split(",")
        for ind, merge in enumerate(params["merge"]):
            if not is_valid_merge(merge):
                return error_param(params, Error.MERGE + str(merge))
            params["merge"][ind] = merge.lower()

    # mergegaps parameter validation
    if params["mergegaps"] and params["extent"]:
        return error_param(params, Error.MERGEGAPS_QUERY_ONLY)
    if is_valid_float(params["mergegaps"], 0.0, MAX_MERGEGAPS):
        params["mergegaps"] = float(params["mergegaps"])
    elif params["mergegaps"] is not None:
        return error_param(params, Error.MERGEGAPS + str(params["mergegaps"]))

    # output parameter validation
    if not is_valid_output(params["format"]):
        return error_param(params, Error.OUTPUT + str(params["format"]))
    params["format"] = params["format"].lower()

    # nodata parameter validation
    if not is_valid_nodata(params["nodata"]):
        return error_param(params, Error.NODATA_CODE + str(params["nodata"]))
    params["nodata"] = params["nodata"].lower()

    for key, val in params.items():
        logging.debug(key + ": " + str(val))

    return (params, {"msg": HTTP._200_, "details": Error.VALID_PARAM, "code": 200})


def checks_get():

    # get default parameters
    params = Parameters().todict()
    params["base_url"] = request.base_url

    # check if the parameters are unknown
    (p, result) = check_request(params)
    if result["code"] != 200:
        return (p, result)
    return check_parameters(params)


def checks_post(params):

    for key, val in Parameters().todict().items():
        if key not in params:
            params[key] = val
    return check_parameters(params)


def get_post_params():
    rows = list()
    params = dict()
    paramslist = list()
    code = ("network", "station", "location", "channel")
    exclude = ("net", "sta", "cha", "loc", "starttime", "endtime", "constraints")
    post_params = (k for k in Parameters().todict() if k not in exclude)

    # Universal newline decoding :
    stream = io.StringIO(request.stream.read().decode("UTF8"), newline=None)
    for row in stream:
        row = row.strip()  # Remove leading and trailing whitespace.
        row = re.sub(r"[\s]+", " ", row)
        if re.search(r"[^a-zA-Z0-9_,* =?.:-]", row) is None:  # Is a valid row ?
            if re.search(r"=", row):  # parameter=value pairs
                key, val = row.replace(" ", "").split("=")
                if key in post_params:
                    params[key] = val
            else:
                rows.append(row)
    for row in rows:
        row = row.split(" ")
        if len(row) >= 4:
            paramslist.append({code[i]: row[i] for i in range(0, 4)})
            paramslist[-1].update(params)
            if len(row) == 6:  # Per line start time and end time.
                paramslist[-1].update({"start": row[4], "end": row[5]})
    return paramslist


def output():

    try:
        process = None
        valid_param_dicts = list()
        result = {"msg": HTTP._400_, "details": Error.UNKNOWN_PARAM, "code": 400}
        logging.debug(request.url)

        if request.method == "POST":
            for params in get_post_params():
                params["base_url"] = request.base_url
                (params, result) = checks_post(params)
                if result["code"] == 200:
                    valid_param_dicts.append(params)
        else:
            (params, result) = checks_get()
            if result["code"] == 200:
                valid_param_dicts.append(params)

        if valid_param_dicts:

            def put_response(q):
                q.put(get_output(valid_param_dicts))

            q = mp.Queue()
            process = mp.Process(target=put_response, args=(q,))
            process.start()
            resp = q.get(timeout=TIMEOUT)

            if resp:
                return resp
            else:
                raise Exception

    except queue.Empty:
        result = {"msg": HTTP._408_, "details": Error.TIMEOUT, "code": 408}

    except Exception as excep:
        result = {"msg": HTTP._500_, "details": Error.UNSPECIFIED, "code": 500}
        logging.exception(str(excep))

    finally:
        if process:
            process.terminate()

    return error_request(
        msg=result["msg"], details=result["details"], code=result["code"]
    )
