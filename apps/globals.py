STRING_TRUE = ("yes", "true", "t", "y", "1", "")
STRING_FALSE = ("no", "false", "f", "n", "0")
SHOW = "latestupdate"
MERGE = ("quality", "samplerate", "overlap")
ORDERBY = (
    "nslc_time_quality_samplerate",
    "timespancount",
    "timespancount_desc",
    "latestupdate",
    "latestupdate_desc",
)
OUTPUT = ("geocsv", "json", "request", "text", "zip")
NODATA_CODE = ("204", "404")
TIMEOUT = 120
MAX_DAYS_AVAILABILITY = 10 ** 9 - 1
MAX_ROWS = "2_500_000"
MAX_DATA_ROWS = int(MAX_ROWS.replace(",", ""))
MAX_MERGEGAPS = 10000000000
SCHEMAVERSION = 1.0  # version string of the json format
DOCUMENTATION_URI = "http://ws.resif.fr/fdsnws/availability/1/"
SERVICE = "fdsnws-availability"


class Error:
    LEN_ARGS = "Too much arguments in URL."
    UNKNOWN_PARAM = "Unknown query parameter: "
    MULTI_PARAM = "Duplicate query parameter: "
    VALID_PARAM = "Valid parameters. "
    START_LATER = "The starttime cannot be later than the endtime: "
    TOO_LONG_DURATION = "Too many days requested (greater than "
    TOO_MUCH_ROWS = f"The request exceeds the limit of {MAX_ROWS} rows."
    PROCESSING = "Error processing your request."
    NO_CONNECTION = "No services could be discovered at http://ws.resif.fr.\n\
                  This could be due to a temporary service outage, an invalid FDSN service address,\n\
                  an inactive internet connection or a blocking firewall rule."
    OK_CONNECTION = "Connection OK. "
    NODATA = "Your query doesn't match any available data."
    TIMEOUT = f"Your query exceeds timeout ({TIMEOUT} seconds)."
    MISSING = "Missing parameter: "
    BAD_VAL = " Invalid value: "
    CHAR = "White space(s) or invalid string. Invalid value for: "
    EMPTY = "Empty string. Invalid value for: "
    BOOL = "(Valid boolean values are: true/false, yes/no, t/f or 1/0)"
    NETWORK = "Invalid network code: "
    STATION = "Invalid station code: "
    LOCATION = "Invalid location code: "
    CHANNEL = "Invalid channel code: "
    QUALITY = "Invalid quality code: "
    TIME = "Bad date value: "
    ROWLIMIT = "The limit parameter must be an integer." + BAD_VAL
    MERGE = f"Accepted merge values are: {MERGE}." + BAD_VAL
    SHOW = f"Accepted show values: {SHOW}." + BAD_VAL
    ORDERBY = f"Accepted orderby values are: {ORDERBY}." + BAD_VAL
    MERGEGAPS = (
        f"The mergegaps parameter must be a float inside range [0, {MAX_MERGEGAPS}]."
        + BAD_VAL
    )
    MERGEGAPS_QUERY_ONLY = (
        "The mergegaps option is not available with extent mode but with query mode."
    )
    OUTPUT = f"Accepted output values are: {OUTPUT}." + BAD_VAL
    NODATA_CODE = f"Accepted nodata values are: {NODATA_CODE}." + BAD_VAL
    NO_WILDCARDS = "Wildcards or lists are not allowed in network parameter if there are wildcards (* or more than one ?) in station parameters."
    NO_SELECTION = "Request contains no selections."


class HTTP:
    _200_ = "Successful request. "
    _204_ = "No data matches the selection. "
    _400_ = "Bad request due to improper value. "
    _401_ = "Authentication is required. "
    _403_ = "Forbidden access. "
    _404_ = "No data matches the selection. "
    _408_ = "Request exceeds timeout. "
    _409_ = "Too much data. "
    _413_ = "Request too large. "
    _414_ = "Request URI too large. "
    _500_ = "Internal server error. "
    _503_ = "Service unavailable. "
