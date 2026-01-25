import json
import logging
import time
import zipfile
from tempfile import NamedTemporaryFile
from datetime import datetime, timedelta
from typing import Any

from flask import make_response

from apps.globals import Error
from apps.globals import MAX_DATA_ROWS
from apps.globals import SCHEMAVERSION
from apps.globals import QUALITY, SAMPLERATE, START, END, UPDATED, STATUS, COUNT
from apps.utils import error_request
from apps.utils import overflow_error
from apps.utils import tictac

from apps.wfcatalog_client import collect_data


"""
Data Access Layer for ws-availability.

This module is responsible for formatting and transforming the data retrieved
from the backend (MongoDB via wfcatalog_client). It handles:
- Generating headers for various output formats (Text, GeoCSV).
- Converting raw data records into target formats (Text, JSON, Zip).
- Sorting, filtering columns, and merging time spans.
"""

def get_header(params: dict) -> list[str]:
    """
    Generates the column header list based on request parameters.

    Args:
        params: Dictionary of request parameters.

    Returns:
        List of header strings (e.g., ["Network", "Station", ...]).
    """
    header = ["Network", "Station", "Location", "Channel"]
    if params["format"] == "text":
        header[0] = "#" + header[0]
    if "quality" not in params["merge"]:
        header.append("Quality")
    if "samplerate" not in params["merge"]:
        header.append("SampleRate")
    header.extend(["Earliest", "Latest"])
    if params["showlastupdate"]:
        header.append("Updated")
    if params["extent"]:
        header.append("TimeSpans")
        header.append("Restriction")
    return header


def get_geocsv_header(params: dict) -> str:
    """
    Generates the GeoCSV header string.

    Constructs the metadata headers (#dataset, #field_unit, #field_type) required
    by the GeoCSV 2.0 specification.

    Args:
        params: Dictionary of request parameters.

    Returns:
        The formatted GeoCSV header string including column names.
    """
    geocsv_header = [("unitless", "string") for i in range(4)]
    if "quality" not in params["merge"]:
        geocsv_header.append(("unitless", "string"))
    if "samplerate" not in params["merge"]:
        geocsv_header.append(("hertz", "float"))
    geocsv_header.extend([("ISO_8601", "datetime"), ("ISO_8601", "datetime")])
    if params["showlastupdate"]:
        geocsv_header.append(("ISO_8601", "datetime"))
    if params["extent"]:
        geocsv_header.append(("unitless", "integer"))
        geocsv_header.append(("unitless", "string"))

    text = "#dataset: GeoCSV 2.0\n#delimiter: |\n"
    text += "#field_unit: " + "|".join([h[0] for h in geocsv_header]) + "\n"
    text += "#field_type: " + "|".join([h[1] for h in geocsv_header]) + "\n"
    text += "|".join(get_header(params)) + "\n"
    return text


def get_column_widths(data: list[list[str]], header: list[str] | None = None) -> list[int]:
    """
    Calculates the maximum width for each column to align text output.

    Args:
        data: List of data rows (strings).
        header: Optional list of header strings.

    Returns:
        List of integers representing the maximum width for each column.
    """
    ncols = range(len(data[0]))
    colwidths = [max([len(r[i]) for r in data]) for i in ncols]
    if header:
        colwidths = [max(len(h), cw) for h, cw in zip(header, colwidths)]
    return colwidths


def records_to_text(params: dict, data: list[list[Any]], sep: str = " ") -> str:
    """
    Converts data records into a formatted text string.

    Handles 'text', 'geocsv', 'zip', and 'request' formats.

    Args:
        params: Dictionary of request parameters.
        data: List of data records.
        sep: Separator string (default " ").

    Returns:
        The complete formatted response body as a string.
    """
    text = ""
    header = get_header(params)
    if params["format"] == "text":
        sizes = get_column_widths(data, header)
        # pad header and rows according to the maximum column width
        header = [val.ljust(sz) for val, sz in zip(header, sizes)]
        for row in data:
            # Replace empty location code with "--"
            if row[2] == "":
                row[2] = "--"
            row[:] = [val.ljust(sz) for val, sz in zip(row, sizes)]

    if params["format"] in ["geocsv", "zip"]:
        text = get_geocsv_header(params)
    elif params["format"] != "request":
        text = sep.join(header) + "\n"

    data = [f"{sep.join(row)}\n" for row in data]
    text += "".join(data)
    return text


def records_to_dictlist(params: dict, data: list[list[Any]]) -> dict:
    """
    Converts data records into a dictionary structure (JSON).

    Follows the FDSNWS-Availability 1.0 schema specification.
    http://www.fdsn.org/webservices/fdsnws-availability-1.0.schema.json

    Args:
        params: Dictionary of request parameters.
        data: List of data records.

    Returns:
        A dictionary containing version, creation time, and the list of datasources.
    """

    dictlist = list()
    header = get_header(params)
    header = [h.lower() for h in header]
    if params["extent"]:
        header[header.index("timespans")] = "timespanCount"
        for row in data:
            dictlist.append(dict(zip(header, row)))
    else:
        start = -3 if params["showlastupdate"] else -2
        prev_row = data[0]
        for row in data:
            if not dictlist or row[:start] != prev_row[:start]:
                dictlist.append(dict(zip(header[:start], row[:start])))
                dictlist[-1]["timespans"] = list()
                if params["showlastupdate"]:
                    dictlist[-1]["updated"] = row[-1]
            dictlist[-1]["timespans"].append([row[start], row[start + 1]])
            prev_row = row

    return {
        "created": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "version": SCHEMAVERSION,
        "datasources": dictlist,
    }


def sort_records(params: dict, data: list[list[Any]]) -> None:
    """
    Sorts data records in-place based on the 'orderby' parameter.

    Args:
        params: Dictionary of request parameters.
        data: List of data records (modified in-place).
    """
    if params["orderby"] != "nslc_time_quality_samplerate":
        if params["extent"] and params["orderby"] == "timespancount":
            data.sort(key=lambda x: x[COUNT])
        elif params["extent"] and params["orderby"] == "timespancount_desc":
            data.sort(key=lambda x: x[COUNT], reverse=True)
        elif params["orderby"] == "latestupdate":
            data.sort(key=lambda x: x[UPDATED])
        elif params["orderby"] == "latestupdate_desc":
            data.sort(key=lambda x: x[UPDATED], reverse=True)
        else:
            data.sort(key=lambda x: (x[QUALITY], x[SAMPLERATE]))
            data.sort(key=lambda x: (x[START], x[END]), reverse=True)
            data.sort(key=lambda x: x[:QUALITY])


#    else:
#        data.sort(key=lambda x: x[:UPDATED])


def select_columns(
    params: dict, data: list[list[Any]], indexes: list[int]
) -> list[list[Any]]:
    """
    Filters and formats columns in the data records.

    Selects specific columns based on 'indexes' and formats datetime objects
    to ISO8601 strings.

    Args:
        params: Dictionary of request parameters.
        data: List of data records.
        indexes: List of column indexes to keep.

    Returns:
        The processed data list with selected and formatted columns.
    """
    tic = time.time()
    indexes = indexes + [START, END]
    if params["showlastupdate"]:
        indexes = indexes + [UPDATED]
    if params["extent"]:
        indexes = indexes + [COUNT, STATUS]
    if params["format"] == "request":
        indexes = [0, 1, 2, 3] + [START, END]

    for row in data:
        if params["start"] and row[START] < params["start"]:
            row[START] = params["start"]
        if params["end"] and row[END] > params["end"]:
            row[END] = params["end"]
        row[START] = row[START].isoformat(timespec="microseconds") + "Z"
        row[END] = row[END].isoformat(timespec="microseconds") + "Z"

        if params["showlastupdate"] and params["format"] != "request":
            row[UPDATED] = row[UPDATED].isoformat(timespec="seconds") + "Z"

        if params["format"] != "json":
            row[:] = [str(row[i]) for i in indexes]
        else:
            row[:] = [row[i] for i in indexes]

    logging.debug(f"Columns selection in {tictac(tic)} seconds.")
    return data


def fusion(
    params: dict, data: list[list[Any]], indexes: list[int]
) -> list[list[Any]]:
    """
    Merges adjacent time spans or groups data based on strict parameter equality.

    Args:
        params: Dictionary of request parameters (used for 'mergegaps' tolerance).
        data: List of ordered data records.
        indexes: List of column indexes to check for equality when grouping.

    Returns:
        A new list of merged data records.
    """

    tic = time.time()
    merge = list()
    timespancount = 0
    tol = params["mergegaps"] if params["mergegaps"] is not None else 0.0

    # The fusion step needs the rows to be sorted.
    #    data.sort(key=lambda x: x[:UPDATED]) # done by postgres

    for row in data:
        if merge and [row[i] for i in indexes] == [merge[-1][i] for i in indexes]:
            sample_size = 1.0 / float(merge[-1][SAMPLERATE])
            tol2 = timedelta(seconds=max([tol, sample_size]))
            sametrace = (
                row[START] - merge[-1][END] <= tol2
                # (never occurs if sorted ?)
                and merge[-1][START] <= row[END] + tol2
            )
            if not sametrace:
                timespancount += 1
            merge[-1][COUNT] = timespancount

            if params["extent"] or sametrace:
                if row[UPDATED] > merge[-1][UPDATED]:
                    merge[-1][UPDATED] = row[UPDATED]
                if row[START] < merge[-1][START]:
                   merge[-1][START] = row[START]
                if row[END] > merge[-1][END]:
                    merge[-1][END] = row[END]
            else:
                merge.append(list(row))
        else:
            merge.append(list(row))
            timespancount = 1
            merge[-1][COUNT] = 1

    logging.debug(f"Data merged in {tictac(tic)} seconds.")
    return merge


def get_indexes(params: dict) -> list[int]:
    """
    Determines which columns to include based on merge parameters.

    Args:
        params: Dictionary of request parameters.

    Returns:
        List of column indexes to output.
    """

    indexes = [0, 1, 2, 3, 4, 5]
    if "quality" in params["merge"] and "samplerate" in params["merge"]:
        indexes = [0, 1, 2, 3]
    elif "quality" in params["merge"]:
        indexes = [0, 1, 2, 3, 5]
    elif "samplerate" in params["merge"]:
        indexes = [0, 1, 2, 3, 4]
    return indexes


def get_response(params: dict, data: list[list[Any]]) -> Any:
    """
    Constructs the final Flask Response object.

    Formats the data into the requested content type (text/plain, application/json,
    text/csv, application/zip) and sets appropriate headers (Content-Disposition).

    Args:
        params: Dictionary of request parameters.
        data: List of processed data records.

    Returns:
        A Flask Response object containing the formatted data.
    """
    tic = time.time()
    fname = "resifws-availability"
    headers = {"Content-type": "text/plain"}
    if params["format"] == "text":
        response = make_response(records_to_text(params, data), headers)
    elif params["format"] == "request":
        response = make_response(records_to_text(params, data), headers)
    elif params["format"] == "geocsv":
        headers = {"Content-Disposition": f"attachment; filename={fname}.csv"}
        response = make_response(records_to_text(params, data, "|"), headers)
        response.headers["Content-type"] = "text/csv"
    elif params["format"] == "zip":
        headers = {"Content-Disposition": f"attachment; filename={fname}.zip"}
        tmp_zip = NamedTemporaryFile(delete=True)
        with zipfile.ZipFile(tmp_zip.name, "w", zipfile.ZIP_DEFLATED) as zipcsv:
            zipcsv.writestr(f"{fname}.csv", records_to_text(params, data, "|"))
        response = make_response(tmp_zip.read(), headers)
        response.headers["Content-type"] = "application/x-zip-compressed"
    elif params["format"] == "json":
        headers = {"Content-type": "application/json"}
        response = make_response(
            json.dumps(records_to_dictlist(params, data), sort_keys=False), headers
        )
    logging.debug(f"Response built in {tictac(tic)} seconds.")
    return response


def get_output(param_dic_list: list[dict]) -> Any:
    """
    Main entry point for generating the output response.

    Orchestrates the data retrieval pipeline:
    1. Collects data from wfcatalog (via `wfcatalog_client.collect_data`).
    2. Checks for no-data conditions.
    3. Merges and sorts data.
    4. Selects columns and formats output.
    5. Builds the HTTP response.

    Args:
        param_dic_list: List of parameter dictionaries (usually one, or multiple for POST).

    Returns:
        A Flask Response object or an Error Response.
    """

    try:
        tic = time.time()
        data = None
        response = None
        params = param_dic_list[0]

        data = collect_data(param_dic_list)

        if data is None:
            return data
        if not data:
            code = params["nodata"]
            return error_request(msg=f"HTTP._{code}_", details=Error.NODATA, code=code)

        nrows = len(data)
        logging.info(f"Number of collected rows: {nrows}")
        if nrows > MAX_DATA_ROWS:
            return overflow_error(Error.TOO_MUCH_ROWS)

        indexes = get_indexes(params)
        
        # Sort by NSLC + Quality + SampleRate + StartTime to ensure fusion works correctly
        # This fixes issues where out-of-order segments caused data loss or failed merges
        data.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4], x[5], x[START]))

        if params["mergegaps"] is not None or params["extent"] or "overlap" in params["merge"]:
             data = fusion(params, data, indexes)
        data = data[: params["limit"]]

        if params["orderby"] != "nslc_time_quality_samplerate":
            sort_records(params, data)

        data = select_columns(params, data, indexes)
        logging.info(f"Final row number: {len(data)}")
        response = get_response(params, data)
        logging.debug(f"Processing in {tictac(tic)} seconds.")
        return response
    except Exception as ex:
        logging.exception(str(ex))
    finally:
        if data:
            if response:
                nbytes = response.headers.get("Content-Length")
                logging.info(f"{nbytes} bytes rendered in {tictac(tic)} seconds.")
