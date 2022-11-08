import json
import logging
import time
import zipfile
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile

from flask import make_response

from apps.globals import (CHANNEL, COUNT, END, LOCATION, MAX_DATA_ROWS,
                          NETWORK, QUALITY, SAMPLERATE, SCHEMAVERSION, START,
                          STATION, STATUS, UPDATED, Error)
from apps.utils import error_request, overflow_error, tictac
from apps.wfcatalog_client import collect_data


def get_header(params):
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


def get_geocsv_header(params):
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


def get_column_widths(data, header=None):
    """Find the maximum width of each column"""
    keys = data[0].keys()
    colwidths = [max([len(str(r[i])) for r in data]) for i in keys]
    if header:
        colwidths = [max(len(h), cw) for h, cw in zip(header, colwidths)]
    return colwidths


def records_to_text(params, data, sep=" "):
    text = ""
    header = get_header(params)
    if params["format"] == "text":
        sizes = get_column_widths(data, header)
        # pad header and rows according to the maximum column width
        header = [val.ljust(sz) for val, sz in zip(header, sizes)]
        for idx, row in enumerate(data):
            data[idx] = [str(row[val]).ljust(sz) for val, sz in zip(row, sizes)]

    if params["format"] in ["geocsv", "zip"]:
        text = get_geocsv_header(params)
    elif params["format"] != "request":
        text = sep.join(header) + "\n"

    # data = [f"{sep.join(row)}\n" for row in data]
    data = [sep.join([str(row[k]) for k in row.keys()]) + "\n" for row in data]
    text += "".join(data)
    return text


def records_to_dictlist(params, data):
    """Create json output according to the fdsnws specification schema:
    http://www.fdsn.org/webservices/fdsnws-availability-1.0.schema.json"""

    dictlist = list()
    header = get_header(params)
    header = [h.lower() for h in header]
    if params["extent"]:
        header[header.index("timespans")] = "timespanCount"
        for row in data:
            dictlist.append(dict(zip(header, [row[k] for k in row.keys()])))
    else:
        start = -3 if params["showlastupdate"] else -2
        prev_row = [data[0][k] for k in list(data[0].keys())[:8]]
        for idx, row in enumerate(data):
            row = [data[idx][k] for k in list(data[0].keys())[:8]]
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


def sort_records(params, data):
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


def select_columns(params, data, indexes):
    tic = time.time()
    indexes = indexes + [START, END]
    if params["showlastupdate"]:
        indexes = indexes + [UPDATED]
    if params["extent"]:
        indexes = indexes + [COUNT, STATUS]
    if params["format"] == "request":
        indexes = [NETWORK, STATION, LOCATION, CHANNEL] + [START, END]

    for row in data:
        if params["start"] and row[START] < params["start"]:
            row[START] = params["start"]
        if params["end"] and row[END] > params["end"]:
            row[END] = params["end"]
        row[START] = row[START].isoformat(timespec="microseconds") + "Z"
        row[END] = row[END].isoformat(timespec="microseconds") + "Z"

        if params["showlastupdate"] and params["format"] != "request":
            row[UPDATED] = row[UPDATED].isoformat(timespec="seconds") + "Z"

        # TODO
        # if params["format"] != "json":
        #     row[:] = [str(row[i]) for i in indexes]
        # else:
        #     row[:] = [row[i] for i in indexes]

    logging.debug(f"Columns selection in {tictac(tic)} seconds.")
    return data


def fusion(params, data, indexes):
    """:param data: ordered data list
    :k: list or range of indexes of the parameters to be grouped
    :tol: timespans which are separated by gaps smaller than or equal to tol are merged together (query)
    :returns: produces a list of available time extents (extent) or contiguous time spans (query)"""

    tic = time.time()
    merge = list()
    timespancount = 0
    tol = params["mergegaps"] if params["mergegaps"] is not None else 0.0

    # The fusion step needs the rows to be sorted.
    #    data.sort(key=lambda x: x[:UPDATED]) # done by postgres

    for row in data:
        if merge and row == merge[-1]:
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
                # if row[START] < merge[-1][START]:  # never occurs if sorted
                #    merge[-1][START] = row[START]
                if row[END] > merge[-1][END]:
                    merge[-1][END] = row[END]
            else:
                merge += [{i: row[i] for i in indexes}]
        else:
            merge += [{i: row[i] for i in indexes}]
            timespancount = 1
            merge[-1][COUNT] = 1

    logging.debug(f"Data merged in {tictac(tic)} seconds.")
    return merge


def get_indexes(params):
    """Get column indexes to display according to requested params
    :param params: parameter dictionary (network, station, ...)
    :returns: indexes : list of column indexes"""

    indexes = [NETWORK, STATION, LOCATION, CHANNEL, QUALITY, SAMPLERATE, START, END, UPDATED]
    if "quality" in params["merge"] and "samplerate" in params["merge"]:
        indexes = [NETWORK, STATION, LOCATION, CHANNEL, START, END]
    elif "quality" in params["merge"]:
        indexes = [NETWORK, STATION, LOCATION, CHANNEL, SAMPLERATE, START, END]
    elif "samplerate" in params["merge"]:
        indexes = [NETWORK, STATION, LOCATION, CHANNEL, QUALITY, START, END]
    return indexes


def get_response(params, data):
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


def get_output(param_dic_list):
    """
    Availability output (geocsv, json, request, text, zip)

    Parameters:
        param_dic_list: list of parameter dictionaries
    Returns:
        response: response with text, json or csv with data availability
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
        if params["mergegaps"] is not None or params["extent"]:
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
