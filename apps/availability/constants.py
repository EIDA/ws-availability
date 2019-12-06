VERSION = "1.0.0"
MAIN_VERSION = VERSION.split(".")[0]
SCHEMA = "wsavailability"


class Args:
    NETWORK = ("network", None)
    STATION = ("station", None)
    LOCATION = ("location", None)
    CHANNEL = ("channel", None)
    STARTTIME = ("starttime", None)
    ENDTIME = ("endtime", None)
    NET = ("net", "*")
    STA = ("sta", "*")
    LOC = ("loc", "*")
    CHA = ("cha", "*")
    START = ("start", None)
    END = ("end", None)
    QUALITY = ("quality", "*")

    MERGE = ("merge", "")
    MERGEGAPS = ("mergegaps", None)

    ORDERBY = ("orderby", None)
    SHOW = ("show", "")
    ROWLIMIT = ("limit", None)
    FORMAT = ("format", "text")

    INCLUDERESTRICTED = ("includerestricted", "F")
    NODATA = ("nodata", "204")


class Empty:
    pass


PARAMS = [v[0] for (k, v) in Args.__dict__.items() if k not in Empty.__dict__.keys()]
MAX_PARAMS = len(PARAMS)
POST_PARAMS = [p for p in PARAMS if p not in ("net", "sta", "cha", "loc")]

ALIAS_PARAMS = [
    (Args.NETWORK[0], Args.NET[0]),
    (Args.STATION[0], Args.STA[0]),
    (Args.LOCATION[0], Args.LOC[0]),
    (Args.CHANNEL[0], Args.CHA[0]),
    (Args.STARTTIME[0], Args.START[0]),
    (Args.ENDTIME[0], Args.END[0]),
]

BOOL_PARAMS = [Args.INCLUDERESTRICTED[0]]
