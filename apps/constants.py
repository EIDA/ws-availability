VERSION = "1.0.1"
SCHEMA = "wsavailability"


class Parameters:
    def __init__(self):
        self.network = None
        self.station = None
        self.location = None
        self.channel = None
        self.starttime = None
        self.endtime = None
        self.net = "*"
        self.sta = "*"
        self.loc = "*"
        self.cha = "*"
        self.start = None
        self.end = None
        self.quality = "*"
        self.merge = ""
        self.mergegaps = None
        self.orderby = None
        self.show = ""
        self.rowlimit = None
        self.format = "text"
        self.includerestricted = "f"
        self.format = None
        self.nodata = "204"
        self.constraints = {
            "booleans": ["includerestricted"],
            "floats": [],
            "not_none": [],
        }

    def todict(self):
        return self.__dict__


POST_PARAMS = [
    k for k in Parameters().todict().keys() if k not in ("net", "sta", "cha", "loc")
]

ALIAS = [
    ("network", "net"),
    ("station", "sta"),
    ("location", "loc"),
    ("channel", "cha"),
    ("starttime", "start"),
    ("endtime", "end"),
]
