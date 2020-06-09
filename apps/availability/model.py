import logging

from apps.globals import Error, HTTP
from apps.globals import MAX_DATA_ROWS, MAX_MERGEGAPS
from apps.utils import check_base_parameters
from apps.utils import error_param
from apps.utils import is_valid_integer
from apps.utils import is_valid_float
from apps.utils import is_valid_merge
from apps.utils import is_valid_nodata
from apps.utils import is_valid_orderby
from apps.utils import is_valid_output
from apps.utils import is_valid_quality
from apps.utils import is_valid_show
from apps.availability.constants import BOOL_PARAMS


model_log = logging.getLogger("availability")


def check_parameters(params):

    try:
        # Check base parameters.
        (params, error) = check_base_parameters(params, booleans=BOOL_PARAMS)
        if error["code"] != 200:
            return (params, error)

        params["extent"] = True if "/extent" in params["base_url"] else False

        quality = params["quality"].split(",")
        for q in quality:
            model_log.debug(q)
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
            model_log.debug(key + ": " + str(val))

        return (params, error)

    except Exception as e:
        model_log.exception(str(e))
        return (params, {"msg": HTTP._500_, "details": Error.PROCESSING, "code": 500})
