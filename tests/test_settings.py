import os
import pytest
from apps.settings import Settings

class TestSettings:
    def test_default_values(self):
        """Test authentication defaults for localhost/test mode"""
        # Unset env vars to ensure we test defaults
        if "RUNMODE" in os.environ: del os.environ["RUNMODE"]
        
        settings = Settings()
        assert settings.runmode == "test"
        assert settings.mongodb_host == "localhost"
        assert settings.fdsnws_station_url == "https://orfeus-eu.org/fdsnws/station/1/query"

    def test_production_override(self):
        """Test that production mode forces specific hostnames if defaults were used"""
        os.environ["RUNMODE"] = "production"
        # Ensure we don't have overrides set
        if "MONGODB_HOST" in os.environ: del os.environ["MONGODB_HOST"]
        
        settings = Settings()
        assert settings.runmode == "production"
        # We removed the auto-switch to host.docker.internal for Linux compatibility
        assert settings.mongodb_host == "localhost" 
        assert settings.cache_host == "cache"
        
        del os.environ["RUNMODE"]

    def test_production_explicit_override(self):
        """Test that explicit env vars are respected even in production"""
        os.environ["RUNMODE"] = "production"
        os.environ["MONGODB_HOST"] = "custom-mongo"
        
        settings = Settings()
        assert settings.runmode == "production"
        assert settings.mongodb_host == "custom-mongo"
        
        del os.environ["RUNMODE"]
        del os.environ["MONGODB_HOST"]
