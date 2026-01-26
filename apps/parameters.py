class Parameters:
    def __init__(self) -> None:
        self.network: str | None = None
        self.station: str | None = None
        self.location: str | None = None
        self.channel: str | None = None
        self.starttime: str | None = None
        self.endtime: str | None = None
        self.net: str = "*"
        self.sta: str = "*"
        self.loc: str = "*"
        self.cha: str = "*"
        self.start: str | None = None
        self.end: str | None = None
        self.quality: str = "*"
        self.merge: str = ""
        self.mergegaps: float | None = None
        self.orderby: str | None = None
        self.show: str = ""
        self.limit: int | None = None
        self.includerestricted: str = "false"
        self.format: str = "text"
        self.nodata: str = "204"
        self.constraints: dict[str, list] = {
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

    def todict(self) -> dict:
        return self.__dict__
