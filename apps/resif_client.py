import logging
import time
import psycopg2
import re
from flask import current_app
from apps.utils import tictac
from apps.globals import SCHEMA
from apps.globals import MAX_DATA_ROWS
from apps.globals import QUALITY, SAMPLERATE, START, END, UPDATED, STATUS, COUNT


def get_max_rows(params):
    rowlimit = params["limit"]
    if params["mergegaps"] is not None or params["extent"]:
        rowlimit = MAX_DATA_ROWS
    return min(rowlimit, MAX_DATA_ROWS) + 1


def is_like_or_equal(params, key):
    """ Builds the condition for the specified key in the "where" clause taking into account lists or wildcards. """

    subquery = list()
    for param in params[key].split(","):
        op = "LIKE" if re.search(r"[*?]", param) else "="
        subquery.append(f"{key} {op} '{param}'")
    return " OR ".join(subquery)


def sql_request(paramslist):
    """Builds the PostgreSQL request.
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
    return f"""SET random_page_cost=1; {select} ORDER BY network, station, location, channel, quality, samplerate, starttime, endtime LIMIT {nrows};"""


def collect_data(params):
    """ Get the result of the SQL query. """

    tic = time.time()
    data = list()
    logging.debug("Start collecting data...")
    with psycopg2.connect(current_app.config["DATABASE_URI"]) as conn:
        logging.debug(conn.get_dsn_parameters())
        logging.debug(f"Postgres version : {conn.server_version}")
        with conn.cursor() as curs:
            select = sql_request(params)
            logging.debug(select)
            curs.execute(select)
            logging.debug(curs.statusmessage)
            for row in curs.fetchall():
                if not params[0]["includerestricted"] and row[STATUS] == "RESTRICTED":
                    continue
                data.append(list(row))
            logging.info(f"Get data in {tictac(tic)} seconds.")
    return data


def get_output(param_dic_list):
    """
    Availability output (geocsv, json, request, text, zip)

    Parameters:
        param_dic_list: list of parameter dictionaries
    Returns:
        response: response with text, json or csv with data availability
    """
    data = None
    response = None
    params = param_dic_list[0]

    data = collect_data(param_dic_list)
    if data is None:
        return data
