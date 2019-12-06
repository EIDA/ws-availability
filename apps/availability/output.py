import logging
import re
import time
import zipfile
from tempfile import NamedTemporaryFile
from datetime import datetime, timedelta

import psycopg2
from flask import make_response, jsonify

from apps.availability.constants import SCHEMA
from apps.globals import Error, MAX_DATA_ROWS, SCHEMAVERSION
from apps.utils import config
from apps.utils import overflow_error


output_log = logging.getLogger("availability")

END = 7
START = 6
STATUS = 9
COUNT = 10  # timespancount
UPDATE = 8
SAMPLERATE = 5
QUALITY = 4
LOCATION = 2


def get_max_rows(params):
    rowlimit = params["limit"]
    if params["mergegaps"] is not None or params["extent"]:
        rowlimit = MAX_DATA_ROWS
    return min(rowlimit, MAX_DATA_ROWS) + 1


def is_like_or_equal(params, key):
    """ Built the condition for the specified key in the "where" clause taking into account lists or wilcards """

    subquery = list()
    for param in params[key].split(","):
        op = "LIKE" if re.search(r"[*?]", param) else "="
        subquery.append(f"{key} {op} '{param}'")
    return " OR ".join(subquery)


def sql_request(paramslist):
    """ Built the PostgreSQL request.
        (mergeid is used here to store timespancount later)"""

    select = list()
    for params in paramslist:
        s = f"""SELECT network, station, location, channel, quality, samplerate, starttime, endtime, lastupdated, policy, mergeid FROM {SCHEMA}.traces WHERE"""
        s = f"""{s} ({is_like_or_equal(params, "network")})"""
        if params["station"] != "*":
            s = f"""{s} AND ({is_like_or_equal(params, "station")})"""
        if params["location"] != "*":
            s = f"""{s} AND ({is_like_or_equal(params, "location")})"""
        if params["channel"] != "*":
            s = f"""{s} AND ({is_like_or_equal(params, "channel")})"""
        if params["quality"] != "*":
            s = f"""{s} AND ({is_like_or_equal(params, "quality")})"""

        start = "-infinity" if params["start"] is None else params["start"]
        end = "infinity" if params["end"] is None else params["end"]
        s = f"""{s} AND (starttime , endtime) OVERLAPS ('{start}', '{end}')"""

        select.append(s.replace("?", "_").replace("*", "%"))
    select = " UNION ".join(select)
    nrows = get_max_rows(paramslist[0])
    return f"""{select} ORDER BY network, station, location, channel, quality, samplerate, starttime, endtime LIMIT {nrows};"""


def collect_data(params):
    """ Connect to the PostgreSQL RESIF database """

    start = time.time()
    conn = None
    output_log.debug("Start collecting data...")

    try:
        conf = config()  # read connection parameters
        conn = psycopg2.connect(**conf)  # connect to the RESIF database
        cursor = conn.cursor()  # cursor to execute SQL command
        output_log.info(conn.get_dsn_parameters())
        output_log.info(f"Postgres version : {conn.server_version}")

        SQL_SELECT = sql_request(params)
        output_log.info(f"{SQL_SELECT}")

        localstart = time.time()
        cursor.execute(SQL_SELECT)
        output_log.debug(cursor.statusmessage)
        output_log.debug(f"Execute in {round(time.time() - localstart, 2)} seconds.")

        localstart = time.time()

        data = list()
        for row in cursor.fetchall():
            if not params[0]["includerestricted"] and row[STATUS] == "RESTRICTED":
                continue
            data.append(list(row))
        cursor.close()  # close this communication
        output_log.debug(f"Fetchall in {round(time.time() - localstart, 2)} seconds.")
        return data
    except (Exception, psycopg2.DatabaseError) as error:
        output_log.exception(str(error))
    finally:
        if conn is not None:
            conn.close()
            output_log.debug("Database connection closed.")
        output_log.info(f"Data collected in {round(time.time() - start, 2)} seconds.")


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
    text += "#" + "|".join(get_header(params)) + "\n"
    return text


def get_column_widths(data, header=None):
    """ Find the maximum width of each column"""
    ncols = range(len(data[0]))
    colwidths = [max([len(r[i]) for r in data]) for i in ncols]
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
        for row in data:
            row[:] = [val.ljust(sz) for val, sz in zip(row, sizes)]

    if params["format"] in ["geocsv", "zip"]:
        text = get_geocsv_header(params)
    elif params["format"] != "request":
        text = sep.join(header) + "\n"

    data = [f"{sep.join(row)}\n" for row in data]
    text += "".join(data)
    return text


def records_to_dictlist(params, data):
    header = get_header(params)
    dictlist = []
    for row in data:
        dictlist.append({k: r for k, r in zip(header, row)})
    return {
        "created": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "schemaVersion": SCHEMAVERSION,
        "datasources": dictlist,
    }


def sort_records(params, data):
    if params["orderby"] != "nslc_time_quality_samplerate":
        if params["extent"] and params["orderby"] == "timespancount":
            data.sort(key=lambda x: x[COUNT])
        elif params["extent"] and params["orderby"] == "timespancount_desc":
            data.sort(key=lambda x: x[COUNT], reverse=True)
        elif params["orderby"] == "latestupdate":
            data.sort(key=lambda x: x[UPDATE])
        elif params["orderby"] == "latestupdate_desc":
            data.sort(key=lambda x: x[UPDATE], reverse=True)
        else:
            data.sort(key=lambda x: (x[QUALITY], x[SAMPLERATE]))
            data.sort(key=lambda x: (x[START], x[END]), reverse=True)
            data.sort(key=lambda x: x[:QUALITY])


#    else:
#        data.sort(key=lambda x: x[:UPDATE])


def select_columns(params, data):
    start = time.time()
    indexes = get_indexes(params) + [START, END]
    if params["showlastupdate"]:
        indexes = indexes + [UPDATE]
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

        if params["format"] != "request":
            if params["showlastupdate"]:
                row[UPDATE] = row[UPDATE].isoformat(timespec="microseconds") + "Z"
        row[:] = [str(row[i]) for i in indexes]

    output_log.debug(f"Data selected in {round(time.time() - start, 2)} seconds.")
    return data


def fusion(params, data, indexes):
    """:param data: ordered data list
       :k: list or range of indexes of the parameters to be grouped
       :tol: timespans which are separated by gaps smaller than or equal to tol are merged together (query)
       :returns: produces a list of available time extents (extent) or contiguous time spans (query)"""

    start = time.time()
    merge = list()
    timespancount = 0
    tol = params["mergegaps"] if params["mergegaps"] is not None else 0.0

    # The fusion step needs the rows to be sorted.
    #    data.sort(key=lambda x: x[:UPDATE]) # done by postgres

    for row in data:
        if merge and [row[i] for i in indexes] == [merge[-1][i] for i in indexes]:
            sample_size = 1.0 / float(merge[-1][SAMPLERATE])
            tol2 = timedelta(seconds=max([tol, sample_size]))
            sametrace = (
                row[START] - merge[-1][END] <= tol2
                and merge[-1][START] <= row[END] + tol2  # (never occurs if sorted ?)
            )
            if not sametrace:
                timespancount += 1
            merge[-1][COUNT] = timespancount

            if params["extent"] or sametrace:
                if row[UPDATE] > merge[-1][UPDATE]:
                    merge[-1][UPDATE] = row[UPDATE]
                # if row[START] < merge[-1][START]:  # never occurs if sorted
                #    merge[-1][START] = row[START]
                if row[END] > merge[-1][END]:
                    merge[-1][END] = row[END]
            else:
                merge.append(list(row))
        else:
            merge.append(list(row))
            timespancount = 1
            merge[-1][COUNT] = 1

    output_log.debug(f"Data merged in {round(time.time() - start, 2)} seconds.")
    return merge


def get_indexes(params):
    """Get column indexes to display according to requested params
    :param params: Parameters object (network, station, ...)
    :returns: indexes : list of column indexes """

    indexes = [0, 1, 2, 3, 4, 5]
    if "quality" in params["merge"] and "samplerate" in params["merge"]:
        indexes = [0, 1, 2, 3]
    elif "quality" in params["merge"]:
        indexes = [0, 1, 2, 3, 5]
    elif "samplerate" in params["merge"]:
        indexes = [0, 1, 2, 3, 4]
    return indexes


def get_response(params, data):
    start = time.time()
    fname = "resifws-availability"
    headers = {"Content-type": "text/plain"}
    if params["format"] == "text":
        response = make_response(records_to_text(params, data), headers)
    elif params["format"] == "request":
        response = make_response(records_to_text(params, data), headers)
    elif params["format"] == "sync":
        response = make_response(records_to_text(params, data, "|"), headers)
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
        response = jsonify(records_to_dictlist(params, data))
    output_log.debug(f"Response builts in {round(time.time() - start, 2)} seconds.")
    return response


def get_output(validparamslist):
    """Availability output (geocsv, json, request, sync, text, zip)
    :param validparamslist: List of validated parameter dictionaries.
    :returns: text, json or csv with data availability"""

    try:
        start = time.time()
        data = collect_data(validparamslist)
        if not data:
            return data  # empty (no data) or None (error)

        nrows = len(data)
        output_log.info(f"Number of collected rows: {nrows}")
        if nrows > MAX_DATA_ROWS:
            return overflow_error(Error.TOO_MUCH_ROWS)

        params = validparamslist[0]
        if params["mergegaps"] is not None or params["extent"]:
            data = fusion(params, data, get_indexes(params))
        data = data[: params["limit"]]

        if params["orderby"] != "nslc_time_quality_samplerate":
            sort_records(params, data)

        data = select_columns(params, data)
        output_log.info(f"Final row number: {len(data)}")
        response = get_response(params, data)
        return response
    except Exception as ex:
        output_log.exception(str(ex))
    finally:
        if data:
            if response:
                bytes = response.headers.get("Content-Length")
                working_time = round(time.time() - start, 2)
                output_log.info(f"{bytes} bytes rendered in {working_time} seconds.")
