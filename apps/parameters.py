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
        self.limit = None
        self.includerestricted = "false"
        self.format = "text"
        self.nodata = "204"
        self.constraints = {
            "alias": [
                ("network", "net"),
                ("station", "sta"),
                ("location", "loc"),
                ("channel", "cha"),
                ("starttime", "start"),
                ("endtime", "end"),
            ],
            "booleans": ["includerestricted"],
            "floats": [],
            "not_none": [],
        }

    def todict(self):
        return self.__dict__
