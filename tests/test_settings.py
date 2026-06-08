import os
import pytest
from apps.settings import Settings, build_settings

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


class TestConfigPyVsEnvPrecedence:
    """Guard rails for the docker-compose ↔ config.py precedence bug.

    Until this commit, apps/settings.py removed any config.py value whose
    *key* appeared in os.environ. docker-compose blindly passed defaults
    like MONGODB_HOST=${MONGODB_HOST:-127.0.0.1}, so the key was always
    present, and config.py was silently ignored. The fix:
    - docker-compose no longer sets MONGODB_*/FDSNWS_STATION_URL,
    - build_settings() requires a *non-empty* env var to override config.py.

    Pydantic always reads aliases from the real ``os.environ`` for its own
    env-precedence layer, so these tests manipulate the process env directly
    and clean up in ``setup_method``/``teardown_method``.
    """

    @staticmethod
    def _clear():
        for k in ("MONGODB_HOST", "MONGODB_NAME"):
            os.environ.pop(k, None)

    def setup_method(self, method):
        self._clear()

    def teardown_method(self, method):
        self._clear()

    def test_config_py_wins_when_env_unset(self):
        """Operator edits config.py, env is clean — config.py value reaches Settings."""
        s = build_settings({"MONGODB_HOST": "mongo.lmu.example", "MONGODB_NAME": "wfrepo"})
        assert s.mongodb_host == "mongo.lmu.example"
        assert s.mongodb_name == "wfrepo"

    def test_env_var_wins_when_explicitly_set(self):
        """Power user exports MONGODB_HOST — env wins (existing override path)."""
        os.environ["MONGODB_HOST"] = "from-env"
        s = build_settings({"MONGODB_HOST": "from-config-py"})
        assert s.mongodb_host == "from-env"

    def test_empty_env_var_does_not_override_config(self):
        """Defense-in-depth: empty-string env (the old ``${VAR:-}`` shape)
        must NOT blow away the config.py value — this is what made
        Tobias's container connect to the wrong host."""
        os.environ["MONGODB_HOST"] = ""
        s = build_settings({"MONGODB_HOST": "mongo.lmu.example"})
        assert s.mongodb_host == "mongo.lmu.example"

    def test_none_legacy_value_does_not_clobber_default(self):
        """If config.py never set a key (None), build_settings leaves the
        Pydantic default alone."""
        s = build_settings({"MONGODB_HOST": None})
        assert s.mongodb_host == "localhost"  # Pydantic Field default


class TestConfigSampleHasSaferGetters:
    """Lock in Tobias Megies's PR #62: config.py.sample must use
    ``os.environ.get("X", X)`` — never the leaky ``os.environ.get("X") or X``
    pattern. The latter falls back to the default when env is the literal
    string ``"0"`` (in numeric contexts) or ``""``, silently ignoring an
    operator who genuinely wants to set that value.
    """

    def test_no_or_fallback_pattern_in_config_sample(self):
        from pathlib import Path
        sample = Path(__file__).resolve().parents[1] / "config.py.sample"
        text = sample.read_text()
        # The bad shape: os.environ.get("X")  or  …
        # The good shape: os.environ.get("X", default)
        import re
        bad = re.findall(r'os\.environ\.get\([^)]+\)\s+or\b', text)
        assert not bad, (
            f"config.py.sample uses the leaky pattern `os.environ.get(...) or X` "
            f"in {len(bad)} place(s): {bad}. Use `os.environ.get('X', X)` instead "
            f"(PR #62 by Tobias Megies)."
        )
