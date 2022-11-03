# version string of the json format
SCHEMAVERSION = 1.0

# postgresql schema
SCHEMA = "wsavailability"

# Response
NETWORK = "net"  # 0
STATION = "sta"  # 1
LOCATION = "loc"  # 2
CHANNEL = "cha"  # 3
QUALITY = "qlt"  # 4
SAMPLERATE = "srate"  # 5
START = "ts"  # 6
END = "te"  # 7
UPDATED = "created"  # 8
STATUS = "restr"  # 9
COUNT = "count"  # 10

# limitations
TIMEOUT = 600
MAX_DAYS = None
MAX_ROWS = "2_500_000"
MAX_DATA_ROWS = int(MAX_ROWS.replace(",", ""))
MAX_MERGEGAPS = 10000000000

# available parameter values
OUTPUT = ("geocsv", "json", "request", "text", "zip")
NODATA_CODE = ("204", "404")
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

# error message constants
DOCUMENTATION_URI = "http://www.fdsn.org/webservices/fdsnws-availability-1.0.pdf"
SERVICE = "fdsnws-availability"
VERSION = "1.0.1"


class Error:
    UNKNOWN_PARAM = "Unknown query parameter: "
    MULTI_PARAM = "Multiple entries for query parameter: "
    VALID_PARAM = "Valid parameters."
    START_LATER = "The starttime cannot be later than the endtime: "
    TOO_LONG_DURATION = "Too many days requested (greater than "
    TOO_MUCH_ROWS = f"The request exceeds the limit of {MAX_ROWS} rows."
    UNSPECIFIED = "Error processing your request."
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
    _413_ = "Request too large. "
    _414_ = "Request URI too large. "
    _500_ = "Internal server error. "
    _503_ = "Service unavailable. "
