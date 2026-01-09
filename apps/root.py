"""
Core Request Handling Module for ws-availability.

This module orchestrates the processing of HTTP requests (GET and POST).
It handles parameter extraction, validation (via Pydantic), and delegates
data retrieval to the data access layer.
"""
import io
import logging
import multiprocessing as mp
import queue
import re
from typing import Any

from flask import request

from apps.data_access_layer import get_output
from apps.globals import HTTP, MAX_DATA_ROWS, MAX_DAYS, MAX_MERGEGAPS, TIMEOUT, Error
from apps.parameters import Parameters
from apps.models import QueryParameters
from pydantic import ValidationError
from apps.utils import (
    check_base_parameters,
    check_request,
    error_param,
    error_request,
)

mp.set_start_method("fork")


def check_parameters(params: dict) -> tuple[dict, dict]:
    """
    Validates request parameters using Pydantic models.

    Args:
        params: Dictionary of request parameters.

    Returns:
        A tuple containing:
        - params (dict): The validated and normalized parameters.
        - error (dict): An error dictionary (code 200 if valid, 400+ otherwise).
    """
    try:
        # check base parameters (handles aliases and required fields like starttime if not optional?)
        # Actually Pydantic handles required fields too, but check_base_parameters might handle legacy alias mapping?
        # Let's keep it for now as it maps "net" -> "network" etc.
        (params, error) = check_base_parameters(params, MAX_DAYS)
        if error["code"] != 200:
            return (params, error)

        params["extent"] = bool("/extent" in params["base_url"])

        # Pydantic Validation
        # QueryParameters model validates all fields (network, station, quality, starttime, etc.)
        # It handles type conversion (str -> int/float) and regex checks.
        
        qp = QueryParameters(**params)
        
        # Get validated values. 
        # by_alias=False ensures we use "network" instead of "net" if model defined aliases.
        # But wait, our model defined aliases: network = Field(alias="net").
        # If input has "network", Pydantic accepts it if populate_by_name=True is set (default False in V2?).
        # We need to ensure ConfigDict(populate_by_name=True) in model if we want to accept both.
        # The `check_base_parameters` function ALREADY normalizes aliases (maps "net" -> "network").
        # So `params` passed here has "network".
        # Pydantic will validate "network".
        
        validated = qp.model_dump()
        
        # Update params with validated/converted values (e.g. limit comes out as int)
        params.update(validated)

        # Legacy logic preservation:
        # 1. "orderby" lowercasing (handled by Pydantic validator?) -> Yes, we added validator.
        # 2. "show" split and validate -> Handled.
        # 3. "merge" split and validate -> Handled? 
        #    Wait, in `models.py` I defined `merge: str`. 
        #    Original code: `params["merge"] = params["merge"].split(",")`.
        #    My Pydantic model kept it as `str`. 
        #    I should update `models.py` to `merge: List[str]` or handle split in validator?
        #    Actually, keeping it as string in model might be safer for now if rest of app expects string?
        #    Original code at L83: `params["merge"][ind] = merge.lower()`. 
        #    It implies `params["merge"]` becomes a LIST.
        #    My Pydantic model defined `merge: str`.
        #    This is a mismatch. I need to fix `models.py` or manual fix here.
        #    Let's handle split manually here to be safe and match legacy `params` structure exactly.
        
        # Pydantic cleanup for specific List types the app expects:

        # Legacy logic note:
        # Original code split 'quality', 'show', 'merge' into lists here.
        # However, downstream logic (wfcatalog_client.py, data_access_layer.py)
        # expects these to be STRINGS and performs the split itself (e.g. .split(",")).
        # Therefore, we keep them as strings from the Pydantic model.


        # Derived logic
        if params["extent"]:
            params["showlastupdate"] = True
        elif "latestupdate" in params["show"] or (params["orderby"] and "latestupdate" in params["orderby"]):
            params["showlastupdate"] = True
        else:
            params["showlastupdate"] = False
            
        # MergeGaps logic
        if params["mergegaps"] and params["extent"]:
            return error_param(params, Error.MERGEGAPS_QUERY_ONLY)
            
        # Defaults
        if params["limit"] is None:
             params["limit"] = MAX_DATA_ROWS

        return (params, {"msg": HTTP._200_, "details": Error.VALID_PARAM, "code": 200})

    except ValidationError as e:
        # Format Pydantic errors to match FDSN style
        msg = []
        for err in e.errors():
            # Get the field name. 'loc' is a tuple like ('network',)
            field = str(err["loc"][0])
            msg.append(f"Invalid value for {field}: {err['msg']}")
        
        msg = "; ".join(msg)

        return error_param(params, msg)
    except Exception as e:
        return error_request(msg=str(e))


def checks_get() -> tuple[dict, dict]:
    """
    Handles parameter validation for GET requests.

    Extracts parameters from the query string, checks for unknown parameters,
    and validates them against the schema.

    Returns:
        A tuple containing:
        - parameters (dict)
        - result (dict): Validation result/error.
    """

    # get default parameters
    params = Parameters().todict()
    params["base_url"] = request.base_url

    # check if the parameters are unknown
    (p, result) = check_request(params)
    if result["code"] != 200:
        return (p, result)
    return check_parameters(params)


def checks_post(params: dict) -> tuple[dict, dict]:
    """
    Handles parameter validation for POST requests.

    Merges provided POST parameters with defaults before validation.

    Args:
        params: Dictionary of parameters parsed from the POST body.

    Returns:
        A tuple containing:
        - parameters (dict)
        - result (dict): Validation result/error.
    """

    for key, val in Parameters().todict().items():
        if key not in params:
            params[key] = val
    return check_parameters(params)


def get_post_params() -> list[dict]:
    """
    Parses parameters from the POST request body.

    Handles standard fdsnws-dataselect POST bodies (key=value pairs per line)
    and expands them into a list of parameter dictionaries.

    Returns:
        List[dict]: A list of parameter dictionaries, one for each line/request in the body.
    """
    rows = list()
    params = dict()
    paramslist = list()
    code = ("network", "station", "location", "channel")
    exclude = ("net", "sta", "cha", "loc", "starttime", "endtime", "constraints")
    post_params = [k for k in Parameters().todict() if k not in exclude]

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


def output() -> Any:
    """
    Main request handler for generating the response.

    Orchestrates the flow:
    1. Determines request method (GET/POST).
    2. Calls validation logic.
    3. Spawns a background process to fetch data (via `get_output`).
    4. returns the formatted response or an error.

    Returns:
        Flask Response object (or data content depending on direct return).
    """

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
