---
tags:
  - node-operator
---

# ws-availability: Install

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

   **`SENTRY_ENVIRONMENT` is required and must be unique per node** (e.g. `noa_production`, `resif_production`) so your events are distinguishable in Sentry. Not sure what's missing? Diff against the sample — see [Troubleshooting](troubleshooting.md).

3. **Rebuild and restart:**

   ```bash
   docker-compose up -d --build          # or: docker-compose pull && docker-compose up -d
   ```

4. **Remove the old host cron**, if you had one triggering `views/main.js` — it's now redundant, replaced by the [built-in scheduler](usage.md#what-runs-daily):

   ```bash
   crontab -l | grep -v "ws-availability.*views.*main.js" | crontab -
   ```

Then re-run the `curl` checks above; `/version` should report `1.1.0`.

## First-time database setup

*Skip this if you already run ws-availability — the view and index already exist.*

For a brand-new WFCatalog database, build the materialized view once:

```bash
# Build the availability view (adjust daysBack to how far back you want)
mongosh -u USER -p PASSWORD --authenticationDatabase wfrepo --eval "daysBack=365" views/main.js
```

The compound index `{ net: 1, sta: 1, loc: 1, cha: 1, ts: 1, te: 1 }` is created automatically by the API at startup (built in the background). If queries feel slow right after a brand-new install, give it a moment to finish.

After the initial build, the cacher keeps the view current automatically (see [What runs daily](usage.md#what-runs-daily)) — **no host cron is needed** (earlier versions required one; it has been replaced by the built-in scheduler).

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

## ws-availability v1.1.0-beta.1 — Install

Beta release. API-compatible with v1.0.5. The beta ships as the **`beta/v1.1.0-beta.1` branch** on `EIDA/ws-availability` — you build it locally (no pre-built images during the beta).

### Prerequisites

- Docker with `docker-compose` (v1) or `docker compose` (v2).
- WFCatalog MongoDB ≥ 4.2 reachable from the host.
- Port 9001 free on the host.

### Install

`cd` into your `ws-availability` checkout (or `git clone https://github.com/EIDA/ws-availability.git` if you don't have one yet), then:

1. Check out the beta branch.

   ```bash
   git fetch origin
   git checkout beta/v1.1.0-beta.1
   ```

   > **What's new for operators:** `config.py` is now the only place to set MongoDB, FDSNWS-Station and Sentry settings — `docker-compose.yml` no longer passes them to the container, so your edits in `config.py` actually take effect.

2. `config.py` — keep your existing one if you already have it; otherwise copy the sample:

   ```bash
   cp -n config.py.sample config.py
   $EDITOR config.py
   ```

   (`cp -n` won't overwrite an existing `config.py`.)

   `MONGODB_*`, `CACHE_*`, and `FDSNWS_STATION_URL` are unchanged since v1.0.3 — keep your existing values.

   **What you must add depends on the version you're upgrading from.** Add the missing lines inside the `try:` block of `config.py` (next to the other `os.environ.get(...)` lines):

   - **Upgrading from v1.0.5 or v1.0.4** — add one line:

     ```python
     SENTRY_ENVIRONMENT = "yournode_production"
     ```

   - **Upgrading from v1.0.3 (or earlier)** — your `config.py` predates Sentry entirely. Add all three:

     ```python
     SENTRY_DSN = os.environ.get("SENTRY_DSN", "")          # paste your Sentry DSN, or leave "" to disable Sentry
     SENTRY_TRACES_SAMPLE_RATE = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "1.0"))
     SENTRY_ENVIRONMENT = "yournode_production"
     ```

   - **Fresh install (copied from `config.py.sample`)** — all three are already present; just replace the `{{node}}_production` placeholder.

   **`SENTRY_ENVIRONMENT` is mandatory and must be unique per node** (e.g. `noa_production`, `resif_production`, `ingv_production`). It is what separates your events from other nodes' in Sentry. Do not leave it as `{{node}}_production` and do not reuse another node's value.

   > To see exactly what your `config.py` is missing, diff it against the shipped sample:
   > ```bash
   > diff <(grep -oE '^[[:space:]]*[A-Z_]+ =' config.py | tr -d ' =' | sort -u) \
   >      <(grep -oE '^[[:space:]]*[A-Z_]+ =' config.py.sample | tr -d ' =' | sort -u)
   > ```
   > Lines prefixed `>` are keys present in the sample but missing from your `config.py`.

3. Build and start.

   ```bash
   docker-compose build
   docker-compose up -d
   ```

4. If your node had a host cron triggering `views/main.js`, remove it — it's now redundant.

   ```bash
   crontab -l | grep -v "ws-availability.*views.*main.js" | crontab -
   ```

### Verify

Replace `<net>` and `<sta>` with one of your live stations.

```bash
curl -s http://127.0.0.1:9001/version
# expected: 1.1.0-beta.1

curl -s -o /dev/null -w "%{http_code}\n" \
  "http://127.0.0.1:9001/extent?net=<net>&sta=<sta>&start=2024-01-01&end=2024-01-02"
# expected: 200

curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:9001/extent?network=<net>"
# expected: 413

docker exec fdsnws-availability-api python -c "from config import Config; print(Config.SENTRY_ENVIRONMENT)"
# expected: your node tag, e.g. noa_production  (NOT {{node}}_production — that means you forgot step 2)
```

### Rollback

```bash
git checkout v1.0.5
docker-compose build
docker-compose up -d
```
