import logging
import os

import sentry_sdk
from flask import Flask, make_response, render_template

from apps.globals import VERSION
from apps.root import output
from config import Config

# Initialize Sentry before creating the Flask app
if Config.SENTRY_DSN:
    sentry_sdk.init(
        dsn=Config.SENTRY_DSN,
        traces_sample_rate=Config.SENTRY_TRACES_SAMPLE_RATE,
        # Add data like request headers and IP for users
        send_default_pii=True,
    )

app = Flask(__name__)

FMT = "[%(asctime)s] %(levelname)s [%(filename)s:%(lineno)d] [%(funcName)s] %(message)s"
LOGLEVEL = logging.INFO if os.environ.get("RUNMODE") == "production" else logging.DEBUG
logging.basicConfig(format=FMT, level=LOGLEVEL)

app.config.from_object(Config)
if app.config["RUNMODE"]:
    app.logger.debug("Configuration set with RUNMODE=%s", app.config["RUNMODE"])

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


@app.route("/")
def doc():
    return render_template("doc.html")


# **** MAIN ****
if __name__ == "__main__":
    app.run()
