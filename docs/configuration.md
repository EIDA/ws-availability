---
tags:
  - node-operator
---

# ws-availability: Configuration

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
