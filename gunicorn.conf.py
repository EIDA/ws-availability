"""Gunicorn configuration for ws-availability.

Reads `workers` from ``config.Config.GUNICORN_WORKERS`` so operators can
tune the worker count by editing ``config.py`` instead of patching
``docker-compose.yml``. Falls back to 1 worker if ``config.py`` is missing
or doesn't define the key — gunicorn must always be able to boot.

Anything *not* settable per-operator (bind address, timeout) stays on
gunicorn's command line in ``docker-compose.yml`` so this file remains
short and orthogonal.
"""
try:
    from config import Config
    workers = int(getattr(Config, "GUNICORN_WORKERS", 1) or 1)
except Exception:
    workers = 1
