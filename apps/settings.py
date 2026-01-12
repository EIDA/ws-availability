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
            
            if self.mongodb_host == "localhost":
                self.mongodb_host = "host.docker.internal"
                
            if self.cache_host == "localhost":
                self.cache_host = "cache" 

        return self

settings = Settings()
