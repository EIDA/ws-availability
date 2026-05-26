# FDSNWS-Availability

A Flask implementation of the [FDSN Availability web service 1.0](http://www.fdsn.org/webservices/fdsnws-availability-1.0.pdf). It reports the time spans for which time-series data exist, served from a WFCatalog MongoDB.

It runs as three Docker containers: the **API** (Flask + gunicorn, port 9001), a **Redis** cache, and a **cacher** that keeps the restriction inventory and the `availability` view up to date on a built-in daily schedule.

> **Installing or upgrading to v1.1.0-beta.1?** Follow [`BETA.md`](BETA.md) for the exact commands.

## Run it

```bash
git clone https://github.com/EIDA/ws-availability.git
cd ws-availability
cp config.py.sample config.py        # edit MongoDB creds, FDSNWS_STATION_URL, SENTRY_ENVIRONMENT
docker-compose up -d --build
```

Check it:

```bash
curl "127.0.0.1:9001/extent?net=NA&start=2023-02-01"
```

That's the whole install for a node that already has a populated WFCatalog. Requires MongoDB ≥ 4.2.

## Endpoints

API on port `9001`. `/query` (time spans per channel) and `/extent` (one row per channel) accept GET and POST. Also `/version`, `/application.wadl`, and `/` (landing page).

```bash
curl "127.0.0.1:9001/extent?net=NA&start=2023-02-01"
#Network Station Location Channel Quality SampleRate Earliest                    Latest                      Updated              TimeSpans Restriction
NA       SABA             BHZ     D       40.0       2023-02-01T00:00:00.000000Z 2023-02-14T00:00:00.000000Z 2023-02-14T07:41:41Z 1         OPEN
```

## Configuration

Everything lives in `config.py` (copied from `config.py.sample`, gitignored so upgrades never touch it). Set these in the `RUNMODE == "production"` block:

| Key | Description |
|-----|-------------|
| `MONGODB_HOST` / `PORT` / `USR` / `PWD` / `NAME` | WFCatalog MongoDB connection. |
| `FDSNWS_STATION_URL` | FDSNWS-Station endpoint to harvest restriction info from. |
| `CACHE_HOST` / `CACHE_PORT` | Redis location. |
| `CACHE_RESP_PERIOD` | Response cache TTL in seconds (default 1200). |
| `SENTRY_DSN` | Sentry DSN; empty disables Sentry. |
| `SENTRY_ENVIRONMENT` | **Unique per-node tag** (e.g. `noa_production`) so Sentry can tell deployments apart. |

## What runs daily

The cacher runs a built-in scheduler — no host cron needed:

- **03:00 UTC** — refresh the restriction inventory from FDSNWS-Station into Redis.
- **06:00 UTC** — update the `availability` view from the last 4 days of WFCatalog data.
- **On startup** — both run once, so a restart leaves data fresh.

## First-time database setup

*Skip this if you already run ws-availability — the view and index already exist.*

For a brand-new WFCatalog database, build the materialized view once and add the index:

```bash
# Build the availability view (adjust daysBack to how far back you want)
mongosh -u USER -p PASSWORD --authenticationDatabase wfrepo --eval "daysBack=365" views/main.js

# Index — without it, every query is a full collection scan
mongosh -u USER -p PASSWORD --authenticationDatabase wfrepo --eval '
  db.availability.createIndex({ net: 1, sta: 1, loc: 1, cha: 1, ts: 1, te: 1 })'
```

## Serving publicly

The API speaks plain HTTP on 9001. To serve it at the standard FDSN URL with HTTPS, put it behind your existing reverse proxy. Apache example:

```apache
ProxyPass        /fdsnws/availability/1 http://127.0.0.1:9001 timeout=600
ProxyPassReverse /fdsnws/availability/1 http://127.0.0.1:9001 timeout=600
```

## Tuning (optional)

- **Workers** — default `--workers 1` in `docker-compose.yml`; raise if you have CPU/RAM headroom.
- **Row/stream caps** — `MAX_DATA_ROWS` (default 2.5M) and `MAX_STREAMS` (default 2000) env vars guard against oversized requests (HTTP 413).
- **Parallel fan-out** — set `FANOUT_ENABLED=true` to speed up long multi-month queries by running them as parallel time-window cursors. Off by default; identical results when off.

## Development

Requires Python ≥ 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
cp config.py.sample config.py        # edit for RUNMODE=test
uv sync
docker run -p 6379:6379 -d redis:7.0-alpine     # Redis is required
uv run python cache.py               # build the restriction inventory
RUNMODE=test uv run gunicorn --bind 0.0.0.0:9001 start:app
```

Tests: `uv run pytest tests/`

## References

Forked from [gitlab.com/resif/ws-availability](https://gitlab.com/resif/ws-availability) — thanks to our colleagues at RESIF for sharing their FDSNWS-Availability implementation. 💐
