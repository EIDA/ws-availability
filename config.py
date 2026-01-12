
import os

class Config:
    """
    Classic configuration file.
    You can edit values here directly on the server.
    """
    
    # Default RUNMODE (can be overriden by env var)
    RUNMODE = "production"

    # WFCatalog MongoDB
    MONGODB_HOST = "localhost" # User must change this to their gateway IP if using Docker
    MONGODB_PORT = 27017
    MONGODB_USR = "wfrepouser"
    MONGODB_PWD = "2023wf"
    MONGODB_NAME = "wfrepo"

    # FDSNWS-Station cache source
    FDSNWS_STATION_URL = "https://orfeus-eu.org/fdsnws/station/1/query"

    # Cache
    CACHE_HOST = "cache"
    CACHE_PORT = 6379
    CACHE_INVENTORY_KEY = "inventory"
    CACHE_INVENTORY_PERIOD = 0
    CACHE_RESP_PERIOD = 1200
