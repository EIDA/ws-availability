import logging
import os

from flask import Flask, make_response, render_template

from apps.globals import VERSION
from apps.root import output
from apps.settings import settings
# from config import Config


app = Flask(__name__)

FMT = "[%(asctime)s] %(levelname)s [%(filename)s:%(lineno)d] [%(funcName)s] %(message)s"
# Use 'runmode' from validated settings
LOGLEVEL = logging.INFO if settings.runmode == "production" else logging.DEBUG
logging.basicConfig(format=FMT, level=LOGLEVEL)

# Load validated settings into Flask config (for compatibility)
# This allows 'current_app.config["KEY"]' to still work during transition if needed,
# though we plan to replace usages with 'settings' logic.
# settings.model_dump() requires pydantic V2
app.config.from_mapping(settings.model_dump())

if app.config.get("runmode"):
    app.logger.debug("Configuration set with RUNMODE=%s", app.config["runmode"])

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
