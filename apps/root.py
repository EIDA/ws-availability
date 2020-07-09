import logging
import queue
from multiprocessing import Process, Queue

from apps.constants import ALIAS
from apps.constants import Parameters
from apps.globals import Error
from apps.globals import HTTP
from apps.globals import MAX_DATA_ROWS
from apps.globals import MAX_DAYS
from apps.globals import MAX_MERGEGAPS
from apps.globals import TIMEOUT
from apps.output import get_output
from apps.utils import check_base_parameters
from apps.utils import check_request
from apps.utils import error_param
from apps.utils import error_request
from apps.utils import is_valid_integer
from apps.utils import is_valid_float
from apps.utils import is_valid_merge
from apps.utils import is_valid_nodata
from apps.utils import is_valid_orderby
from apps.utils import is_valid_output
from apps.utils import is_valid_quality
from apps.utils import is_valid_show


def check_parameters(params):

    # check base parameters
    (params, error) = check_base_parameters(params, MAX_DAYS)
    if error["code"] != 200:
        return (params, error)

    params["extent"] = True if "/extent" in params["base_url"] else False

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


def checks_get(request):

    # get default parameters
    params = Parameters().todict()

    # check if the parameters are unknown
    (p, result) = check_request(request, params, ALIAS)
    if result["code"] != 200:
        return (p, result)

    # determine selected features
    params["base_url"] = request.base_url

    for key, val in params.items():
        params[key] = request.args.get(key, val)

    for key, alias in ALIAS:
        if params[key] is None:
            params[key] = request.args.get(alias, params[alias])
        else:
            params[alias] = params[key]

    return check_parameters(params)


def checks_post(params):

    for key, val in Parameters().todict().items():
        if key not in params:
            params[key] = val

    return check_parameters(params)


def output(request, paramslist):

    try:
        process = None
        param_dic_list = list()
        result = {"msg": HTTP._400_, "details": Error.UNKNOWN_PARAM, "code": 400}
        for pdic in paramslist:
            if request.method == "POST":
                # builds the full url corresponding to a line of post request (debug)
                args = "&".join(["=".join(kv) for kv in list(pdic.items())])
                logging.debug(request.base_url + "?" + args)
                pdic["base_url"] = request.base_url
                (pdic, result) = checks_post(pdic)
            else:
                logging.debug(request.url)
                (pdic, result) = checks_get(request)

            if result["code"] == 200:
                param_dic_list.append(pdic)

        if param_dic_list:

            def put_response(q):
                q.put(get_output(param_dic_list))

            q = Queue()
            process = Process(target=put_response, args=(q,))
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
