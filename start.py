import logging
import os

import sentry_sdk
from flask import Flask, make_response, render_template

from apps.globals import VERSION
from apps.root import output
from config import Config


def before_send(event, hint):
    """
    Scrub sensitive data from Sentry events before sending.
    This prevents passwords, API keys, and other secrets from being exposed.
    """
    # List of sensitive field names to scrub (case-insensitive)
    sensitive_keys = {
        "password", "passwd", "pwd", "secret", "api_key", "apikey", 
        "token", "auth", "authorization", "credentials", "private_key",
        "access_token", "refresh_token", "session", "cookie"
    }
    
    def scrub_dict(data):
        """Recursively scrub sensitive data from dictionaries."""
        if not isinstance(data, dict):
            return
        
        for key in list(data.keys()):
            key_lower = str(key).lower()
            # Check if key contains any sensitive keyword
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                data[key] = "[Filtered]"
            elif isinstance(data[key], dict):
                scrub_dict(data[key])
            elif isinstance(data[key], list):
                for item in data[key]:
                    if isinstance(item, dict):
                        scrub_dict(item)
    
    # Scrub request data
    if "request" in event:
        scrub_dict(event["request"])
    
    # Scrub extra context
    if "extra" in event:
        scrub_dict(event["extra"])
    
    # Scrub user context
    if "user" in event:
        scrub_dict(event["user"])
    
    # Scrub breadcrumbs
    if "breadcrumbs" in event:
        for breadcrumb in event["breadcrumbs"].get("values", []):
            scrub_dict(breadcrumb)
    
    # Scrub local variables from stack traces
    if "exception" in event:
        for exception in event["exception"].get("values", []):
            if "stacktrace" in exception:
                for frame in exception["stacktrace"].get("frames", []):
                    if "vars" in frame:
                        scrub_dict(frame["vars"])
    
    return event


# Initialize Sentry before creating the Flask app
if Config.SENTRY_DSN:
    sentry_sdk.init(
        dsn=Config.SENTRY_DSN,
        traces_sample_rate=Config.SENTRY_TRACES_SAMPLE_RATE,
        # Add data like request headers and IP for users
        send_default_pii=True,
        # Scrub sensitive data before sending
        before_send=before_send,
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
