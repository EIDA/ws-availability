import logging
import queue
from multiprocessing import Process, Queue

from apps.availability.constants import ALIAS_PARAMS
from apps.availability.constants import Args
from apps.availability.constants import PARAMS
from apps.availability.model import check_parameters
from apps.availability.output import get_output
from apps.globals import Error, HTTP, TIMEOUT
from apps.utils import check_request, error_request


def checks_get(request):
    # check if the parameters are unknown
    (params, result) = check_request(request, PARAMS, ALIAS_PARAMS)
    if result["code"] != 200:
        return (params, result)

    # determine selected features
    params = {}
    params["base_url"] = request.base_url
    params["network"] = request.args.get(*Args.NETWORK)
    params["station"] = request.args.get(*Args.STATION)
    params["location"] = request.args.get(*Args.LOCATION)
    params["channel"] = request.args.get(*Args.CHANNEL)
    params["start"] = request.args.get(*Args.STARTTIME)
    params["end"] = request.args.get(*Args.ENDTIME)

    if params["network"] is None:
        params["network"] = request.args.get(*Args.NET)
    if params["station"] is None:
        params["station"] = request.args.get(*Args.STA)
    if params["location"] is None:
        params["location"] = request.args.get(*Args.LOC)
    if params["channel"] is None:
        params["channel"] = request.args.get(*Args.CHA)
    if params["start"] is None:
        params["start"] = request.args.get(*Args.START)
    if params["end"] is None:
        params["end"] = request.args.get(*Args.END)

    params["quality"] = request.args.get(*Args.QUALITY)
    params["merge"] = request.args.get(*Args.MERGE)
    params["orderby"] = request.args.get(*Args.ORDERBY)
    params["show"] = request.args.get(*Args.SHOW)
    params["limit"] = request.args.get(*Args.ROWLIMIT)
    params["mergegaps"] = request.args.get(*Args.MERGEGAPS)
    params["nodata"] = request.args.get(*Args.NODATA)
    params["includerestricted"] = request.args.get(*Args.INCLUDERESTRICTED)
    params["format"] = request.args.get(*Args.FORMAT)
    return check_parameters(params)


def checks_post(params):

    if "starttime" in params and "start" not in params:
        params["start"] = params.pop("starttime")
    if "endtime" in params and "end" not in params:
        params["end"] = params.pop("endtime")

    if "start" not in params:
        params["start"] = None
    if "end" not in params:
        params["end"] = None
    if "quality" not in params:
        params["quality"] = "*"
    if "merge" not in params:
        params["merge"] = ""
    if "orderby" not in params:
        params["orderby"] = None
    if "show" not in params:
        params["show"] = ""
    if "limit" not in params:
        params["limit"] = None
    if "mergegaps" not in params:
        params["mergegaps"] = None
    if "format" not in params:
        params["format"] = "request"
    if "nodata" not in params:
        params["nodata"] = "204"
    if "includerestricted" not in params:
        params["includerestricted"] = "T"
    return check_parameters(params)


def availability(request, paramslist):

    main_log = logging.getLogger("availability")
    validparamslist = list()
    try:
        result = {"msg": HTTP._400_, "details": Error.UNKNOWN_PARAM, "code": 400}
        for params in paramslist:
            if request.method == "POST":
                args = "&".join(["=".join(kv) for kv in list(params.items())])
                main_log.info(request.base_url + "?" + args)
                params["base_url"] = request.base_url
                (params, result) = checks_post(params)
            else:
                main_log.info(request.url)
                (params, result) = checks_get(request)

            if result["code"] == 200:
                validparamslist.append(params)

        if validparamslist:

            def put_response(q):
                q.put(get_output(validparamslist))

            q = Queue()
            process = Process(target=put_response, args=(q,))
            process.start()
            resp = q.get(timeout=TIMEOUT)

            if resp:
                return resp
            if resp is None:
                raise Exception
            # resp empty (no data)
            result = {
                "msg": f'HTTP._{params["nodata"]}_',
                "details": Error.NO_DATA,
                "code": int(params["nodata"]),
            }

    except queue.Empty:
        result = {"msg": HTTP._408_, "details": Error.TIMEOUT, "code": 408}
        process.terminate()

    except Exception as excep:
        result = {"msg": HTTP._500_, "details": Error.PROCESSING, "code": 500}
        main_log.exception(str(excep))

    return error_request(
        msg=result["msg"], details=result["details"], code=result["code"]
    )
