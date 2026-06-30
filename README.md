# FDSNWS-Availability

A Flask implementation of the [FDSN Availability web service 1.0](http://www.fdsn.org/webservices/fdsnws-availability-1.0.pdf). It reports the time spans for which time-series data exist, served from a WFCatalog MongoDB.

It runs as three Docker containers: the **API** (Flask + gunicorn, port 9001), a **Redis** cache, and a **cacher** that keeps the restriction inventory and the `availability` view up to date on a built-in daily schedule.

> **Upgrading from v1.0.x?** See [Upgrading from v1.0.x](#upgrading-from-v10x) for the exact `config.py` changes — it's a quick, self-contained checklist.

## Deployment

First, get and configure the repo (needed either way):

```bash
git clone https://github.com/EIDA/ws-availability.git
cd ws-availability
cp config.py.sample config.py        # edit MongoDB creds, FDSNWS_STATION_URL, SENTRY_ENVIRONMENT
```

Then pick one of:

### Option A — Build locally

Builds the images on your host. No registry access needed.

```bash
docker-compose up -d --build
```

### Option B — Pull pre-built images

Each **tagged release** publishes images to GHCR, so you can skip the build. Replace `<version>` with a release tag (e.g. `1.1.0`, or `1.1` for the latest 1.1.x):

```yaml
# docker-compose.override.yml
services:
  api:
    image: ghcr.io/eida/ws-availability/api:<version>
  cacher:
    image: ghcr.io/eida/ws-availability/cacher:<version>
```

```bash
docker-compose pull
docker-compose up -d
```

> Pre-built images exist only for tagged releases. To build from an untagged branch instead, use Option A (build locally).

Either way, three containers come up. Check it:

```bash
curl "127.0.0.1:9001/version"        # -> 1.1.0
curl "127.0.0.1:9001/extent?net=NA&start=2023-02-01"
```

For a node that already has a populated WFCatalog, that's the whole install. A brand-new database also needs the one-time [database setup](#first-time-database-setup). Requires MongoDB ≥ 4.2.

## Upgrading from v1.0.x

Upgrading reuses the same containers and the same `config.py`. The only manual step is making sure `config.py` has the keys the new version expects, then rebuilding.

> **What changed for operators:** `config.py` is now the **only** place to set MongoDB, FDSNWS-Station and Sentry settings. `docker-compose.yml` no longer passes them to the container, so your edits in `config.py` actually take effect.

1. **Get the new code.** Your `config.py` is gitignored, so this won't touch it:

   ```bash
   git fetch && git checkout v1.1.0
   ```

2. **Add any missing `config.py` keys.** `MONGODB_*`, `CACHE_*` and `FDSNWS_STATION_URL` are unchanged — keep your values. What to add depends on the version you're coming from (add the lines inside the `try:` block, next to the other `os.environ.get(...)` lines):

   - **From v1.0.5 or v1.0.4** — add one line:

     ```python
     SENTRY_ENVIRONMENT = "yournode_production"
     ```

   - **From v1.0.3 or earlier** (predates Sentry) — add all three:

     ```python
     SENTRY_DSN = os.environ.get("SENTRY_DSN", "")          # your Sentry DSN, or "" to disable
     SENTRY_TRACES_SAMPLE_RATE = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "1.0"))
     SENTRY_ENVIRONMENT = "yournode_production"
     ```

   **`SENTRY_ENVIRONMENT` is required and must be unique per node** (e.g. `noa_production`, `resif_production`) so your events are distinguishable in Sentry. Not sure what's missing? Diff against the sample — see [Troubleshooting](#troubleshooting).

3. **Rebuild and restart:**

   ```bash
   docker-compose up -d --build          # or: docker-compose pull && docker-compose up -d
   ```

4. **Remove the old host cron**, if you had one triggering `views/main.js` — it's now redundant, replaced by the [built-in scheduler](#what-runs-daily):

   ```bash
   crontab -l | grep -v "ws-availability.*views.*main.js" | crontab -
   ```

Then re-run the `curl` checks above; `/version` should report `1.1.0`.

## Endpoints

API on port `9001`. `/query` (time spans per channel) and `/extent` (one row per channel) accept GET and POST. Also `/version`, `/application.wadl`, and `/` (landing page).

```bash
curl "127.0.0.1:9001/extent?net=NA&start=2023-02-01"
#Network Station Location Channel Quality SampleRate Earliest                    Latest                      Updated              TimeSpans Restriction
NA       SABA             BHZ     D       40.0       2023-02-01T00:00:00.000000Z 2023-02-14T00:00:00.000000Z 2023-02-14T07:41:41Z 1         OPEN
```

## Configuration

Everything lives in `config.py` (copied from `config.py.sample`, gitignored so upgrades never touch it). Set these in the `RUNMODE == "production"` block:

| Key | Default | Description |
|-----|---------|-------------|
| `MONGODB_HOST` | `host.docker.internal` | WFCatalog MongoDB host. |
| `MONGODB_PORT` | `27017` | MongoDB port. |
| `MONGODB_USR` / `MONGODB_PWD` | empty | MongoDB credentials (leave empty if no auth). |
| `MONGODB_NAME` | `wfrepo` | Database name; also used as `authSource` unless `MONGODB_AUTH_SOURCE` is set. |
| `MONGODB_AUTH_SOURCE` | `None` | Optional. Mongo auth database when it differs from `MONGODB_NAME` (e.g. `admin`). Falls back to `MONGODB_NAME` when unset. |
| `FDSNWS_STATION_URL` | `https://orfeus-eu.org/fdsnws/station/1/query` | FDSNWS-Station endpoint to harvest restriction info from. |
| `CACHE_HOST` | `cache` | Redis host. |
| `CACHE_PORT` | `6379` | Redis port. |
| `CACHE_INVENTORY_KEY` | `inventory` | Redis key for the restriction inventory. |
| `CACHE_INVENTORY_PERIOD` | `0` | Inventory cache TTL in seconds; `0` = never expire. |
| `CACHE_RESP_PERIOD` | `1200` | Response cache TTL in seconds. |
| `SENTRY_DSN` | empty | Sentry DSN; empty disables Sentry. |
| `SENTRY_TRACES_SAMPLE_RATE` | `1.0` | Fraction of requests traced, `0.0`–`1.0`. |
| `SENTRY_ENVIRONMENT` | `{{node}}_production` | **Unique per-node tag** (e.g. `noa_production`) so Sentry can tell deployments apart. Must be changed from the placeholder. |
| `GUNICORN_WORKERS` | `1` | Number of gunicorn worker processes. Raise (2–3, or `(2 × CPU cores) + 1`) if you have CPU/RAM headroom. Read by `gunicorn.conf.py` at container start. |

## What runs daily

The cacher runs a built-in scheduler — no host cron needed:

- **03:00 UTC** — refresh the restriction inventory from FDSNWS-Station into Redis.
- **06:00 UTC** — update the `availability` view from the last 4 days of WFCatalog data.
- **On startup** — both run once, so a restart leaves recent data fresh.

This covers only the recent window. To repair an older date (e.g. after a backfill), see [Back-processing](#back-processing-historical--scoped-rebuild).

## Tuning (optional)

- **Workers** — set `GUNICORN_WORKERS` in `config.py` (default `1`). `gunicorn.conf.py` reads it at startup. Raise if you have CPU/RAM headroom.
- **Row/stream caps** — `MAX_DATA_ROWS` (default 2.5M) and `MAX_STREAMS` (default 2000) env vars guard against oversized requests (HTTP 413).

### Parallel fan-out

By default, each request is answered by a **single** MongoDB cursor. The `availability` collection holds one document per channel-per-day, so a long time range means many documents fetched in sequential round-trips — most of the time is spent waiting on the database, one batch after another.

Fan-out splits the request's time range into day-aligned windows and runs them as **concurrent** cursors, then merges the pieces back together. The waiting overlaps instead of stacking up, so a multi-month query finishes noticeably faster. Because each window is a separate day range, the slices never overlap and the merged result is **byte-identical** to the single-cursor answer — only the speed differs.

It is **off by default**, applies to **both `/query` and `/extent`** (they share the same fetch layer), and only engages when a request's time range is at least `FANOUT_MIN_DAYS` — shorter requests stay single-cursor because the thread overhead wouldn't pay off. Controlled by these environment variables:

| Variable | Default | Effect |
|----------|---------|--------|
| `FANOUT_ENABLED` | `false` | Master switch. When `false`, behaves exactly like the single-cursor path. |
| `FANOUT_MIN_DAYS` | `7` | Minimum request range, in days, before fan-out engages. |
| `FANOUT_WINDOW_DAYS` | `30` | Size of each window. A 90-day query becomes ~3 windows. |
| `FANOUT_MAX_WORKERS` | `4` | Max windows run at once — also the number of MongoDB connections a fan-out request uses. |

Best for long, narrow queries (months/years of a few channels). Before enabling on a busy node, check that `workers × FANOUT_MAX_WORKERS` stays within your MongoDB connection budget.

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

## First-time database setup

*Skip this if you already run ws-availability — the view and index already exist.*

For a brand-new WFCatalog database, build the materialized view once:

```bash
# Build the availability view (adjust daysBack to how far back you want)
mongosh -u USER -p PASSWORD --authenticationDatabase wfrepo --eval "daysBack=365" views/main.js
```

The compound index `{ net: 1, sta: 1, loc: 1, cha: 1, ts: 1, te: 1 }` is created automatically by the API at startup (built in the background). If queries feel slow right after a brand-new install, give it a moment to finish.

After the initial build, the cacher keeps the view current automatically (see [What runs daily](#what-runs-daily)) — **no host cron is needed** (earlier versions required one; it has been replaced by the built-in scheduler).

### Back-processing (historical / scoped rebuild)

The daily scheduler only refreshes a **rolling recent window** (the last 4 days). It therefore *cannot* repair a historical gap: if WFCatalog is (re)populated for an old date — e.g. after a backfill, or a data correction surfaced by an [EIDA consistency report](https://github.com/EIDA) — restarting the cacher does **not** rebuild that date, so `/query` and `/extent` keep reporting "no data" even though dataselect / the SDS archive serve it. You must reprocess that range explicitly.

> **Prerequisite:** back-processing only re-derives the view *from* WFCatalog (`daily_streams`/`c_segments`). It does **not** scan the SDS archive. If WFCatalog itself is missing the range, refresh WFCatalog for those dates **first**, otherwise the rebuild completes cleanly but writes nothing.

**Preferred — the `avail-rebuild` CLI** (runs inside the cacher, so it uses the container's own MongoDB credentials; supports full NSLC):

```bash
# A network/station over a range (all of 2008 -> end is the day boundary, 2009-01-01)
docker exec fdsnws-availability-cacher \
  avail-rebuild --net IV --sta ABC --start 2008-01-01 --end 2009-01-01

# Channel-precise (e.g. just HHZ; --loc=-- means the empty location.
# Use the attached '=' form: a bare '--' is read by the shell/argparse as end-of-options.)
docker exec fdsnws-availability-cacher \
  avail-rebuild --net IV --sta ABC --loc=-- --cha HHZ --start 2008-01-01 --end 2009-01-01

# Whole range, all streams
docker exec fdsnws-availability-cacher avail-rebuild --start 2023-01-01 --end 2023-02-01
```

`--net/--sta/--loc/--cha` are comma-separated exact-match lists; omit any to leave it unconstrained. The rebuild is idempotent (`$merge whenMatched:"replace"`) — safe to re-run. After it finishes, flush Redis or wait out `CACHE_RESP_PERIOD` before re-checking, in case an empty response for that query is still cached. (If the console script isn't on `PATH` for some reason, `docker exec fdsnws-availability-cacher python -m apps.cli …` is equivalent.)

**Fallback — `views/main.js` via `mongosh`** (host-side; net+sta+date only, no loc/cha; needs a repo checkout and DB creds on the host):

```bash
mongosh -u USER -p PASSWORD --authenticationDatabase wfrepo \
  --eval "networks='NL'; stations='HGN'; start='2022-12-01'; end='2023-01-31'" views/main.js
```

## Troubleshooting

If the service isn't working — often right after an upgrade — it's usually a configuration problem:

1. **Check the logs** for runtime errors or connection failures:

   ```bash
   docker logs fdsnws-availability-api
   docker logs fdsnws-availability-cacher
   ```

2. **Verify `config.py` has every field** the current version expects. New versions add keys; list what yours is missing versus the sample:

   ```bash
   diff <(grep -oE '^[[:space:]]*[A-Z_]+ =' config.py      | tr -d ' =' | sort -u) \
        <(grep -oE '^[[:space:]]*[A-Z_]+ =' config.py.sample | tr -d ' =' | sort -u)
   ```

   Lines prefixed `>` are keys present in the sample but missing from your `config.py` — add them.

3. **Check database access** — confirm the MongoDB and Redis connection parameters in `config.py` are correct and that both services are reachable from the containers.

## References

Forked from [gitlab.com/resif/ws-availability](https://gitlab.com/resif/ws-availability) — thanks to our colleagues at RESIF for sharing their FDSNWS-Availability implementation. 💐
