import os
from typing import Literal
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application Settings using Pydantic.
    
    Reads from environment variables.
    Adapts defaults based on RUNMODE to match legacy behavior.
    """
    runmode: Literal["test", "production"] = Field("test", alias="RUNMODE")
    
    # WFCatalog MongoDB
    mongodb_host: str = Field("localhost", alias="MONGODB_HOST")
    mongodb_port: int = Field(27017, alias="MONGODB_PORT")
    mongodb_usr: str = Field("", alias="MONGODB_USR")
    mongodb_pwd: str = Field("", alias="MONGODB_PWD")
    mongodb_name: str = Field("wfrepo", alias="MONGODB_NAME")
    
    # FDSNWS-Station cache source
    fdsnws_station_url: str = Field("https://orfeus-eu.org/fdsnws/station/1/query", alias="FDSNWS_STATION_URL")
    
    # Cache
    cache_host: str = Field("localhost", alias="CACHE_HOST")
    cache_port: int = Field(6379, alias="CACHE_PORT")
    cache_inventory_key: str = Field("inventory", alias="CACHE_INVENTORY_KEY")
    cache_inventory_period: int = Field(0, alias="CACHE_INVENTORY_PERIOD")
    cache_resp_period: int = Field(1200, alias="CACHE_RESP_PERIOD")

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    @model_validator(mode='after')
    def set_production_defaults(self):
        """
        If RUNMODE is production, override localhost defaults with production defaults
        (host.docker.internal, etc.) UNLESS they were explicitly set (which we can't easily check here,
        so we check if they are still at the 'test' default).
        """
        if self.runmode == "production":
            # Legacy config logic: if production, DB host is host.docker.internal
            # We match this behavior if the value is currently 'localhost' (the test default)
            
            # if self.mongodb_host == "localhost":
            #     self.mongodb_host = "host.docker.internal"
                
            # Host networking: CACHE_HOST env var is used directly (localhost/127.0.0.1)
            # if self.cache_host == "localhost":
            #     self.cache_host = "cache"
            pass 

        return self

def load_legacy_config():
    """Attempt to import Config from config.py and return as dict."""
    try:
        from config import Config
        return {
            "RUNMODE": getattr(Config, "RUNMODE", "test"),
            "MONGODB_HOST": getattr(Config, "MONGODB_HOST", None),
            "MONGODB_PORT": getattr(Config, "MONGODB_PORT", None),
            "MONGODB_USR": getattr(Config, "MONGODB_USR", None),
            "MONGODB_PWD": getattr(Config, "MONGODB_PWD", None),
            "MONGODB_NAME": getattr(Config, "MONGODB_NAME", None),
            "FDSNWS_STATION_URL": getattr(Config, "FDSNWS_STATION_URL", None),
            "CACHE_HOST": getattr(Config, "CACHE_HOST", None),
            "CACHE_PORT": getattr(Config, "CACHE_PORT", None),
            "CACHE_INVENTORY_KEY": getattr(Config, "CACHE_INVENTORY_KEY", None),
            "CACHE_INVENTORY_PERIOD": getattr(Config, "CACHE_INVENTORY_PERIOD", None),
            "CACHE_RESP_PERIOD": getattr(Config, "CACHE_RESP_PERIOD", None),
        }
    except ImportError:
        return {}


# Load legacy config options and filter out None values
legacy_defaults = {k: v for k, v in load_legacy_config().items() if v is not None}

# Remove keys from legacy_defaults if they are set in environment variables
# This ensures Docker environment variables (e.g. MONGODB_HOST) take precedence
# over values hardcoded in config.py (like "localhost")
for key in list(legacy_defaults.keys()):
    if key in os.environ:
        del legacy_defaults[key]

# Instantiate settings with remaining legacy defaults
settings = Settings(**legacy_defaults)
