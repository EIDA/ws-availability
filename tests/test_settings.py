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
        """Test that production mode no longer overrides cache_host (host networking)"""
        os.environ["RUNMODE"] = "production"
        # Ensure we don't have overrides set
        if "MONGODB_HOST" in os.environ: del os.environ["MONGODB_HOST"]
        if "CACHE_HOST" in os.environ: del os.environ["CACHE_HOST"]

        settings = Settings()
        assert settings.runmode == "production"
        # We removed the auto-switch to host.docker.internal for Linux compatibility
        assert settings.mongodb_host == "localhost"
        # Host networking: cache_host stays as localhost (no longer auto-changed to "cache")
        assert settings.cache_host == "localhost"

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

    def test_auth_source_default_fallback(self):
        """Test that missing MONGODB_AUTH_SOURCE defaults to None (backward compatibility)"""
        if "MONGODB_AUTH_SOURCE" in os.environ: del os.environ["MONGODB_AUTH_SOURCE"]

        settings = Settings()
        assert settings.mongodb_auth_source is None
        assert settings.mongodb_name == "wfrepo"

        # Simulating the fallback logic used in wfcatalog_client
        auth_source = settings.mongodb_auth_source or settings.mongodb_name
        assert auth_source == "wfrepo"

    def test_auth_source_explicit_override(self):
        """Test that explicit MONGODB_AUTH_SOURCE is respected"""
        os.environ["MONGODB_AUTH_SOURCE"] = "admin"
        os.environ["MONGODB_NAME"] = "wfrepo"

        settings = Settings()
        assert settings.mongodb_auth_source == "admin"

        # Simulating the logic used in wfcatalog_client
        auth_source = settings.mongodb_auth_source or settings.mongodb_name
        assert auth_source == "admin"

        del os.environ["MONGODB_AUTH_SOURCE"]
        del os.environ["MONGODB_NAME"]
