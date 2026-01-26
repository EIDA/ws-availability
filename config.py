
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
    FDSNWS_STATION_URL = "https://eida.gein.noa.gr/fdsnws/station/1/query"

    # Cache
    CACHE_HOST = "localhost"
    CACHE_PORT = 6379
    CACHE_INVENTORY_KEY = "inventory"
    CACHE_INVENTORY_PERIOD = 0
    CACHE_RESP_PERIOD = 1200

    try:
        MONGODB_HOST = os.environ.get("MONGODB_HOST") or MONGODB_HOST
        MONGODB_PORT = os.environ.get("MONGODB_PORT") or MONGODB_PORT
        MONGODB_USR = os.environ.get("MONGODB_USR") or MONGODB_USR
        MONGODB_PWD = os.environ.get("MONGODB_PWD") or MONGODB_PWD
        MONGODB_NAME = os.environ.get("MONGODB_NAME") or MONGODB_NAME
        FDSNWS_STATION_URL = os.environ.get("FDSNWS_STATION_URL") or FDSNWS_STATION_URL
        CACHE_HOST = os.environ.get("CACHE_HOST") or CACHE_HOST
        CACHE_PORT = os.environ.get("CACHE_PORT") or CACHE_PORT
        CACHE_INVENTORY_KEY = (
            os.environ.get("CACHE_INVENTORY_KEY") or CACHE_INVENTORY_KEY
        )
        CACHE_INVENTORY_PERIOD = (
            os.environ.get("CACHE_INVENTORY_PERIOD") or CACHE_INVENTORY_PERIOD
        )
        CACHE_RESP_PERIOD = (
            os.environ.get("CACHE_SHORT_INV_PERIOD") or CACHE_RESP_PERIOD
        )
    except NameError:
        print("Missing environment variables.")
        raise
