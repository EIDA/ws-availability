# FDSNWS-Availability

A Flask implementation of the [FDSN Availability web service 1.0](http://www.fdsn.org/webservices/fdsnws-availability-1.0.pdf). It reports the time spans for which time-series data exist, served from a WFCatalog MongoDB.

It runs as three Docker containers: the **API** (Flask + gunicorn, port 9001), a **Redis** cache, and a **cacher** that keeps the restriction inventory and the `availability` view up to date on a built-in daily schedule.

> **Installing or upgrading to v1.1.0-beta.1?** Follow [`BETA.md`](BETA.md) for the exact commands.

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

Each **tagged release** publishes images to GHCR, so you can skip the build. Replace `<version>` with a release tag (e.g. `1.1.0`):

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

> Pre-built images exist only for tagged releases. The current beta ships as a branch, so use Option A (build locally) for it — see [`BETA.md`](BETA.md).

Either way, three containers come up. Check it:

```bash
curl "127.0.0.1:9001/version"        # -> 1.1.0-beta.1
curl "127.0.0.1:9001/extent?net=NA&start=2023-02-01"
```

For a node that already has a populated WFCatalog, that's the whole install. A brand-new database also needs the one-time [database setup](#first-time-database-setup). Requires MongoDB ≥ 4.2.

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

## What runs daily

The cacher runs a built-in scheduler — no host cron needed:

- **03:00 UTC** — refresh the restriction inventory from FDSNWS-Station into Redis.
- **06:00 UTC** — update the `availability` view from the last 4 days of WFCatalog data.
- **On startup** — both run once, so a restart leaves data fresh.

## Tuning (optional)

- **Workers** — default `--workers 1` in `docker-compose.yml`; raise if you have CPU/RAM headroom.
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

### Back-processing

The daily scheduler only refreshes a rolling recent window. To reprocess a specific historical range or a subset of streams — e.g. after a data correction or a backfill — run `views/main.js` manually with parameters (`networks`/`stations` accept regex):

```bash
# A specific month
mongosh -u USER -p PASSWORD --authenticationDatabase wfrepo \
  --eval "start='2023-01-01'; end='2023-01-31'" views/main.js

# One network/station over a range
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
