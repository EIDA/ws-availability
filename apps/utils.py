"""
Utility Module for ws-availability.

This module contains shared utility functions used across the application for:
- Parameter validation (legacy and Pydantic helpers).
- Date and time parsing/manipulation.
- Error handling and standard response generation.
- Request parameter normalization (aliases, defaults).
"""
import re
import sys
import time
from difflib import SequenceMatcher
from datetime import datetime, timedelta
from typing import Any

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


def is_valid_integer(
    dimension: Any, mini: int = 0, maxi: int = sys.maxsize
) -> bool:
    """
    Checks if a value can be converted to an integer within a specified range.

    Args:
        dimension: The value to check.
        mini: Minimum valid value (default 0).
        maxi: Maximum valid value (default sys.maxsize).

    Returns:
        True if valid, False otherwise.
    """
    # by default valid for positive integers
    try:
        dimension = int(dimension)
    except Exception:
        return False
    return bool(mini <= dimension <= maxi)


def is_valid_float(
    dimension: Any,
    mini: float = sys.float_info.epsilon,
    maxi: float = sys.float_info.max,
) -> bool:
    """
    Checks if a value can be converted to a float within a specified range.

    Args:
        dimension: The value to check.
        mini: Minimum valid value.
        maxi: Maximum valid value.

    Returns:
        True if valid, False otherwise.
    """
    # by default valid for strictly positive floats
    try:
        dimension = float(dimension)
    except Exception:
        return False
    return bool(mini <= dimension <= maxi)


def is_valid_datetime(date: str) -> datetime | None:
    """
    Parses a string into a datetime object using supported formats.

    Supported formats: "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f".

    Args:
        date: The date string to parse.

    Returns:
        A datetime object if successful, None otherwise.
    """
    for df in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(date.replace("Z", ""), df)
        except (ValueError, TypeError):
            pass


def is_valid_starttime(date: str) -> bool | datetime | None:
    """
    Validates a start time string.

    Args:
        date: Date string or literal "currentutcday".

    Returns:
        datetime object, True (special keyword), or None/False if invalid.
    """
    return is_valid_datetime(date) or date == "currentutcday"


def is_valid_endtime(date: str | int) -> bool | datetime | None:
    """
    Validates an end time string.

    Args:
        date: Date string, duration integer, or "currentutcday".

    Returns:
        datetime object, valid integer check result, or None/False.
    """
    return is_valid_datetime(date) or date == "currentutcday" or is_valid_integer(date)


def is_valid_bool_string(string: str | None) -> bool:
    """
    Checks if a string represents a valid boolean value.

    Args:
        string: String to check (e.g., "true", "FALSE", "1", "0").

    Returns:
        True if the string maps to a boolean, False otherwise.
    """
    if string is None:
        return False
    return bool(string.lower() in STRING_TRUE + STRING_FALSE)





def currentutcday() -> datetime:
    """
    Returns the current UTC date with time reset to midnight (00:00:00).

    Returns:
        datetime corresponding to the start of the current UTC day.
    """
    return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def tictac(tic: float) -> float:
    """
    Calculates elapsed time since a reference epoch.

    Args:
        tic: Reference start time (from time.time()).

    Returns:
        Elapsed time in seconds, rounded to 2 decimal places.
    """
    return round(time.time() - tic, 2)


# Result HTTP code 400 shortcut function
def error_param(params: dict, dmesg: str) -> tuple[dict, dict]:
    """
    Constructs a standard error response for parameter validation failures.

    Args:
        params: The request parameters.
        dmesg: Detailed error message.

    Returns:
        Tuple of (params, error_dict) where error_dict contains code 400.
    """
    return (params, {"msg": HTTP._400_, "details": dmesg, "code": 400})


# Error request function
def error_request(msg: str = "", details: str = "", code: int = 500) -> Response:
    """
    Creates a Flask Response for general API errors.

    Args:
        msg: Short error message/code description.
        details: Detailed error explanation.
        code: HTTP status code.

    Returns:
        Flask Response object with text/plain body.
    """
    request_date = datetime.utcnow().strftime("%Y-%b-%d %H:%M:%S UTC")
    message_error = f"""Error {code}: {msg}\n
{details}\n
Usage details are available from {DOCUMENTATION_URI}\n
Request:
{request.full_path}\n
Request Submitted:
{request_date}\n
Service version:
Service: {SERVICE}  version:{VERSION}"""
    return Response(message_error, status=code, mimetype="text/plain")


# Error 413 response alias
def overflow_error(dmesg: str) -> Response:
    return error_request(msg=HTTP._413_, details=dmesg, code=413)


# Error 500 response alias
def error_500(dmesg: str) -> Response:
    return error_request(msg=HTTP._500_, details=dmesg, code=500)


def check_request(params: dict) -> tuple[dict, dict]:
    """
    Performs preliminary validation of the request object.

    Checks for:
    - Unknown parameters (provides "Did you mean?" hints).
    - Invalid characters in input.
    - Duplicate parameters.
    - Constraint alias mapping.

    Args:
        params: Dictionary of parameters with defaults and constraints.

    Returns:
        Tuple of (params, result_dict), where result_dict has code 200 on success.
    """
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


def check_base_parameters(
    params: dict, max_days: int | None = None
) -> tuple[dict, dict]:
    """
    Validates parameter types, required fields, and logical constraints.

    Note: This function performs logic that Pydantic alone might not fully cover
    without complex validators, such as:
    - "Temporary" network expansion logic.
    - Start/End relative time calculations.
    - Cross-field validation (Start > End).
    - Global duration limits (max_days).

    Args:
        params: Dictionary of parameters.
        max_days: Optional limit on the time range duration in days.

    Returns:
        Tuple of (params, result_dict).
    """

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
