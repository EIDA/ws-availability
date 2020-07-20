import logging
import os

from flask import Flask, make_response, render_template

from apps.constants import VERSION
from apps.root import output
from config import Config


app = Flask(__name__)

FMT = "[%(asctime)s] %(levelname)s [%(filename)s:%(lineno)d] [%(funcName)s] %(message)s"
LOGLEVEL = logging.INFO if os.environ.get("RUNMODE") == "prodution" else logging.DEBUG
logging.basicConfig(format=FMT, level=LOGLEVEL)

app.config.from_object(Config)
if app.config["RUNMODE"]:
    app.logger.debug("Configuration set with RUNMODE=%s", app.config["RUNMODE"])
app.logger.debug("Database URI: %s", app.config["DATABASE_URI"])

# ************************************************************************
# **************************** SERVICE ROUTES ****************************
# ************************************************************************


@app.route("/extent", methods=["GET", "POST"])
def extent():
    return output()


@app.route("/query", methods=["GET", "POST"])
def query():
    return output()


@app.route("/application.wadl")
def wadl():
    template = render_template("wadl.xml")
    response = make_response(template)
    response.headers["Content-Type"] = "application/xml"
    return response


@app.route("/version", strict_slashes=False)
def version():
    response = make_response(VERSION)
    response.headers["Content-Type"] = "text/plain"
    return response


@app.route("/commit", strict_slashes=False)
def commit():
    try:
        with open("./static/commit.txt") as commit_file:
            COMMIT_SHORT_SHA = commit_file.readline()
    except Exception:
        COMMIT_SHORT_SHA = "unspecified"
    response = make_response(COMMIT_SHORT_SHA)
    response.headers["Content-Type"] = "text/plain"
    return response


@app.route("/")
@app.route("/local=fr")
def doc():
    return render_template("doc.html")


@app.route("/local=en")
def doc_en():
    return render_template("doc_en.html")


# **** MAIN ****
if __name__ == "__main__":
    app.run()
