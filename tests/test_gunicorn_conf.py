"""Tests for gunicorn.conf.py.

Tobias's beta review (paraphrased): *"the number of workers should be
settable in the config, not by patching docker-compose.yml."* This file
locks in that contract:

1. ``gunicorn.conf.py`` reads ``workers`` from ``config.Config.GUNICORN_WORKERS``.
2. It falls back to 1 worker if ``config.py`` is missing — gunicorn must
   always be able to boot.
3. ``docker-compose.yml`` invokes gunicorn with ``-c gunicorn.conf.py``,
   not with a hardcoded ``--workers <n>``.
4. ``Dockerfile.api`` actually COPYs ``gunicorn.conf.py`` into the image.
"""
from pathlib import Path
import sys
import types

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
GUNICORN_CONF = REPO_ROOT / "gunicorn.conf.py"


def _exec_gunicorn_conf(fake_config_module=None):
    """Exec gunicorn.conf.py in an isolated namespace and return its globals.

    If ``fake_config_module`` is provided, register it as ``config`` in
    ``sys.modules`` for the duration of the exec so the ``from config import
    Config`` line inside gunicorn.conf.py picks it up.
    """
    original = sys.modules.get("config")
    try:
        if fake_config_module is None:
            sys.modules.pop("config", None)
        else:
            sys.modules["config"] = fake_config_module
        namespace: dict = {}
        exec(GUNICORN_CONF.read_text(), namespace)
        return namespace
    finally:
        # Restore whatever was there (including absence).
        if original is None:
            sys.modules.pop("config", None)
        else:
            sys.modules["config"] = original


def _fake_config(**attrs):
    mod = types.ModuleType("config")

    class Config:
        pass

    for k, v in attrs.items():
        setattr(Config, k, v)
    mod.Config = Config
    return mod


def test_workers_reads_from_config_py():
    """Operator sets GUNICORN_WORKERS in config.py → gunicorn picks it up."""
    ns = _exec_gunicorn_conf(_fake_config(GUNICORN_WORKERS=4))
    assert ns["workers"] == 4


def test_workers_defaults_to_one_when_attribute_missing():
    """config.py exists but doesn't define GUNICORN_WORKERS — fall back to 1."""
    ns = _exec_gunicorn_conf(_fake_config())  # no GUNICORN_WORKERS set
    assert ns["workers"] == 1


def test_workers_defaults_to_one_when_config_module_missing():
    """No config.py at all (e.g. fresh image, operator hasn't copied it yet).
    Gunicorn must still boot."""
    ns = _exec_gunicorn_conf(fake_config_module=None)
    assert ns["workers"] == 1


def test_workers_coerces_string_to_int():
    """If GUNICORN_WORKERS reached config.py via os.environ.get (returning a
    string), gunicorn.conf.py must still produce an int."""
    ns = _exec_gunicorn_conf(_fake_config(GUNICORN_WORKERS="3"))
    assert ns["workers"] == 3
    assert isinstance(ns["workers"], int)


# --- Plumbing checks ---------------------------------------------------------

def test_docker_compose_uses_gunicorn_conf_file():
    """The api service must invoke gunicorn with ``-c gunicorn.conf.py``,
    not with a hardcoded ``--workers <n>`` (would defeat the point)."""
    text = (REPO_ROOT / "docker-compose.yml").read_text()
    # Pull out the api command line.
    assert "-c gunicorn.conf.py" in text, (
        "docker-compose.yml api command must use `-c gunicorn.conf.py`."
    )
    # Ensure --workers isn't on the gunicorn command line anymore.
    import re
    leftover = re.search(r"gunicorn[^\n]*--workers\s+\S+", text)
    assert not leftover, (
        f"docker-compose.yml still passes a hardcoded `--workers` to gunicorn: "
        f"{leftover.group(0)!r}. Set GUNICORN_WORKERS in config.py instead."
    )


def test_dockerfile_api_copies_gunicorn_conf():
    """gunicorn.conf.py must end up inside the image, otherwise -c fails at
    container start."""
    text = (REPO_ROOT / "Dockerfile.api").read_text()
    assert "gunicorn.conf.py" in text, (
        "Dockerfile.api must COPY gunicorn.conf.py into the image."
    )
