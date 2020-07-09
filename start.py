import io
import logging
import os
import re

from flask import Flask, make_response, render_template, request

from apps.constants import POST_PARAMS, VERSION
from apps.root import output
from config import Config


app = Flask(__name__)

fmt = "[%(asctime)s] %(levelname)s [%(filename)s:%(lineno)d] [%(funcName)s] %(message)s"
loglevel = logging.INFO if os.environ.get("RUNMODE") == "prodution" else logging.DEBUG
logging.basicConfig(format=fmt, level=loglevel)

app.config.from_object(Config)
if app.config["RUNMODE"]:
    app.logger.debug("Configuration set with RUNMODE=%s", app.config["RUNMODE"])
app.logger.debug("Database URI : %s", app.config["DATABASE_URI"])

# **************************************************************************
# ********************** AVAILABILITY SERVICE ROUTES ***********************
# **************************************************************************


@app.route("/query", methods=["GET"])
def availability_root_get():
    return output(request, paramslist=[request])


@app.route("/query", methods=["POST"])
def availability_root_post():
    rows = list()
    params = dict()
    paramslist = list()
    code = ["network", "station", "location", "channel"]
    # Universal newline decoding :
    stream = io.StringIO(request.stream.read().decode("UTF8"), newline=None)

    for row in stream:
        row = row.strip()  # Remove leading and trailing whitespace.
        row = re.sub(r"[\s]+", " ", row)
        if re.search(r"[^a-zA-Z0-9_,* =?.:-]", row) is None:  # Is a valid row ?
            if re.search(r"=", row):  # parameter=value pairs
                key, val = row.replace(" ", "").split("=")
                if key in POST_PARAMS:
                    key = key.replace("starttime", "start").replace("endtime", "end")
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

    return output(request, paramslist)


@app.route("/extent", methods=["GET"])
def extent_get():
    return availability_root_get()


@app.route("/extent", methods=["POST"])
def extent_post():
    return availability_root_post()


@app.route("/application.wadl")
def availability_wadl():
    template = render_template("ws-availability.wadl.xml")
    response = make_response(template)
    response.headers["Content-Type"] = "application/xml"
    return response


@app.route("/version")
def version():
    response = make_response(VERSION)
    response.headers["Content-Type"] = "text/plain"
    return response


@app.route("/")
@app.route("/local=fr")
def availability_doc():
    return render_template("availability_doc.html")


@app.route("/local=en")
def availability_doc_en():
    return render_template("availability_doc_en.html")


# **** MAIN ****
if __name__ == "__main__":
    app.run()
