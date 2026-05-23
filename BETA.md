# ws-availability — Beta Testing Guide (v1.1.0-beta.1)

You are running a **beta release** of `ws-availability`. This document is for sysadmins of EIDA nodes who are deploying the beta against their own WFCatalog MongoDB. If you are looking for the stable release, use [`v1.0.5`](https://github.com/EIDA/ws-availability/releases/tag/v1.0.5).

The beta is **API-compatible** with `v1.0.5` — request shapes, response bodies, status codes, and error messages are unchanged. All new behavior is opt-in via environment variables. If you do not set any of the new env vars, the beta behaves like the stable release.

> **Release status:** the beta lives on `EIDA/ws-availability` once the PR is merged and the `v1.1.0-beta.1` tag is pushed. The CI workflow then publishes container images to `ghcr.io/eida/ws-availability/api:1.1.0-beta.1` and `ghcr.io/eida/ws-availability/cacher:1.1.0-beta.1`. If you are testing the beta **before** the PR is merged, replace the clone URL with the contributor's fork (the PR description will link it) and the image namespace with `ghcr.io/<contributor>/ws-availability/...`. Everything else in this guide is unchanged.

---

## 1. What's new since v1.0.5

| Area | Change | Risk |
|------|--------|------|
| Python runtime | Container base image bumped to `python:3.13-slim`. Major deps bumped: Flask 2.3 → 3.1, gunicorn 20 → 26, pymongo 3.12 → 4.17, redis 4.4 → 7.4, obspy 1.3 → 1.5. | Medium — major version bumps. Smoke-tested by the maintainer, but please report any regressions. |
| Sentry environment | New `SENTRY_ENVIRONMENT` env var tags Sentry events per node (e.g. `noa_production`). Defaults to `local_development` if unset. | Low — affects only event tagging in Sentry. |
| Parallel MongoDB fan-out | Optional time-window parallelism for long-range queries. Off by default. See §6. | Low when off; medium when on — read §6 before enabling. |

What did **not** change: query/extent endpoints, response formats, restriction filtering, the `MAX_DATA_ROWS` row cap, the broad-query rejection from Issue #60.

---

## 2. Pre-flight checklist

Run through this list **before** starting the deployment. Items marked **must** will block the deploy; **should** items will not crash the install but may produce no data.

- [ ] **must** — Docker ≥ 20.10 installed with Compose v2 plugin. Verify with `docker compose version`.
- [ ] **must** — Outbound HTTPS to `ghcr.io` reachable from the host (for `docker compose pull`). If you cannot reach ghcr, see §4.2 (build from source).
- [ ] **must** — A running WFCatalog MongoDB ≥ 4.2 reachable from the host. Test with:
   ```bash
   mongosh "mongodb://USR:PWD@MONGO_HOST:27017/wfrepo?authSource=wfrepo" --eval 'db.runCommand({ping:1})'
   ```
- [ ] **should** — The `availability` collection or materialized view exists in your MongoDB. If it does not, see §5.4.
- [ ] **should** — The compound index on `availability` exists. Verify with `db.availability.getIndexes()`. If missing, create it (see §5.5) — without it, every query becomes a collection scan.
- [ ] **must** — Port `9001/tcp` available on the host (or whichever port you bind to). Verify with `ss -tlnp | grep :9001`.
- [ ] **should** — An FDSNWS-Station endpoint URL reachable from the host. Used by the cacher to harvest the restriction inventory. Test with `curl -sf "<URL>?level=network&format=text" | head`.
- [ ] **should** — At least **2 GB** free RAM (the api container is capped at `mem_limit: 2g`) and **500 MB** for the cacher.
- [ ] **optional** — A Sentry DSN if you want error/performance monitoring. The beta runs fine with Sentry disabled.

If any **must** item fails, stop and resolve it before continuing.

---

## 3. Pick your deployment path

| Path | When to use | Section |
|------|-------------|---------|
| **A. Fresh install** | No `ws-availability` running on this host. | §4 |
| **B. Upgrade from v1.0.5** | Currently running v1.0.5 (or earlier) on this host. | §5 |
| **C. Side-by-side test** | Want to test the beta on a different port without touching your existing v1.0.5 deployment. | §6 |

---

## 4. Path A — Fresh install

### 4.1 Clone and checkout the beta

```bash
git clone https://github.com/EIDA/ws-availability.git
cd ws-availability
git fetch --tags
git checkout v1.1.0-beta.1
```

### 4.2 Create `config.py` from the sample

```bash
cp config.py.sample config.py
```

Edit `config.py` and set the **production** branch values to match your environment. The minimum you must set:

```python
if RUNMODE == "production":
    MONGODB_HOST = "10.0.0.50"           # your Mongo host (or 127.0.0.1)
    MONGODB_PORT = 27017
    MONGODB_USR = "wfrepouser"            # leave empty if no auth
    MONGODB_PWD = "your-password"
    MONGODB_NAME = "wfrepo"
    FDSNWS_STATION_URL = "https://your-node.example/fdsnws/station/1/query"
    CACHE_HOST = "127.0.0.1"              # Redis lives inside docker host-network
    CACHE_PORT = 6379
    CACHE_INVENTORY_KEY = "inventory"
    CACHE_INVENTORY_PERIOD = 0            # 0 = never expire; refreshed by cacher schedule
    CACHE_RESP_PERIOD = 1200              # cache responses for 20 minutes
```

Sentry (optional) — set `SENTRY_DSN` either inside `config.py` or via env var before running `docker compose up`.

> **Heads-up:** `config.py` is in `.gitignore`. Each operator maintains their own. Do **not** commit it.

### 4.3 Create a compose override to use the pre-built image

Create `docker-compose.override.yml` next to `docker-compose.yml`. This pins the api and cacher to the published beta images:

```yaml
services:
  api:
    image: ghcr.io/eida/ws-availability/api:1.1.0-beta.1
  cacher:
    image: ghcr.io/eida/ws-availability/cacher:1.1.0-beta.1
```

Compose v2 reads `docker-compose.override.yml` automatically and merges it with `docker-compose.yml`. Because the override sets `image:`, `docker compose up` will pull the published image instead of running the local `build:` step — provided you start with `docker compose up` (not `docker compose build`).

If your host cannot reach `ghcr.io`, skip this file and Compose will build the images locally from the Dockerfiles.

### 4.4 Set per-node environment variables

These must be exported in the same shell where you run `docker compose up`:

```bash
# Sentry environment tag — REQUIRED if SENTRY_DSN is set
export SENTRY_ENVIRONMENT=your_node_production    # or your_node_staging
# Mongo overrides — only set if different from config.py
# export MONGODB_HOST=10.0.0.50
# export MONGODB_USR=wfrepouser
# export MONGODB_PWD='your-password'
```

You can also write these to a `.env` file in the repo root; Compose v2 reads `.env` automatically. Recommended for production:

```ini
# .env (DO NOT COMMIT)
SENTRY_ENVIRONMENT=your_node_production
MONGODB_HOST=10.0.0.50
MONGODB_USR=wfrepouser
MONGODB_PWD=your-password
```

> **Heads-up:** `.env` is **not** in the repo's `.gitignore` by default. Add it to your local `.gitignore` or keep the file outside the working tree.

### 4.5 Pull images and start

```bash
docker compose pull                  # downloads ghcr images (~200 MB total)
docker compose up -d                 # starts cache, cacher, api in detached mode
docker compose ps                    # should show 3 containers, all "running"
```

Expected output of `docker compose ps`:

```
NAME                          STATUS         PORTS
fdsnws-availability-cache     Up 5 seconds
fdsnws-availability-cacher    Up 5 seconds
fdsnws-availability-api       Up 5 seconds
```

### 4.6 Wait for the cacher to harvest the restriction inventory

The cacher container fetches the restriction inventory from `FDSNWS_STATION_URL` on first run. This takes **anywhere from 30 seconds to several minutes** depending on how many networks your FDSNWS-Station endpoint exposes.

Watch the cacher log:

```bash
docker logs -f fdsnws-availability-cacher
```

You are looking for the line:

```
INFO Completed caching inventory from FDSNWS-Station
```

Once that appears, the api container will be able to handle requests that touch the restriction logic (most queries do).

> **If the cacher fails:** check that `FDSNWS_STATION_URL` is reachable from inside the container with `docker exec fdsnws-availability-cacher curl -sI "$FDSNWS_STATION_URL?level=network"`.

### 4.7 Initial materialized view (only if it does not exist yet)

If your MongoDB does not yet have an `availability` collection populated from the WFCatalog `daily_streams` / `c_segments` collections, run the initial build. This is a **one-time** operation and is **independent of ws-availability** — the same step as the v1.0.5 README.

```bash
# Adjust daysBack as needed. 365 = back-fill the last year.
mongosh -u "$MONGODB_USR" -p "$MONGODB_PWD" --authenticationDatabase wfrepo \
   --eval "daysBack=365" \
   /path/to/checkout/views/main.js
```

This may take **tens of minutes to several hours** depending on your data volume. Tail Mongo logs to monitor progress.

### 4.8 Create the compound index (one-time)

```bash
mongosh -u "$MONGODB_USR" -p "$MONGODB_PWD" --authenticationDatabase wfrepo --eval '
   use wfrepo;
   db.availability.createIndex({ net: 1, sta: 1, loc: 1, cha: 1, ts: 1, te: 1 });
   db.availability.getIndexes();
'
```

Without this index, every API query becomes a collection scan and the beta will be no faster than v1.0.5 — fan-out won't help either.

### 4.9 Smoke test

```bash
# Landing page
curl -sf http://127.0.0.1:9001/ | grep -q FDSNWS-Availability && echo "Landing OK"

# Version
curl -s http://127.0.0.1:9001/version
# expected: 1.1.0-beta.1

# Extent — replace HL with one of your networks
curl -s "http://127.0.0.1:9001/extent?net=HL&start=2024-01-01&end=2024-01-02" | head -5

# Query in JSON
curl -s "http://127.0.0.1:9001/query?net=HL&start=2024-01-01&end=2024-01-02&format=json" | head

# Broad-query rejection (Issue #60). MUST return 413.
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:9001/extent?network=HL"
# expected: 413
```

If all five succeed, your fresh install is operational. Continue to §7 (enabling fan-out) or §10 (what to test).

---

## 5. Path B — Upgrade an existing node from v1.0.5 (cookbook)

This is the path for an EIDA node operator already running `v1.0.5`. Follow the steps in order. Each step has a verification command — if its output doesn't match, **stop and investigate before continuing**.

Total time: **~5–10 minutes** including build. API downtime: **~15 seconds × 2** (API and cacher swapped one at a time).

### 5.1 Variables for your node

Set these once in the shell you'll run the rest from. Replace `<your_node>` with a short tag — `noa`, `resif`, `orfeus`, `ingv`, etc. This tag identifies your deployment in Sentry.

```bash
export WSAVAIL_DIR=/path/to/your/ws-availability/checkout    # <-- adjust
export NODE_TAG=<your_node>                                  # <-- adjust, e.g. noa
```

### 5.2 Back up before you change anything

```bash
cd "$WSAVAIL_DIR"
cp config.py "$HOME/config.py.pre-1.1.0-beta.bak"
crontab -l > "$HOME/crontab.pre-1.1.0-beta.bak" 2>/dev/null
git rev-parse HEAD > "$HOME/ws-availability.pre-1.1.0-beta.commit"
echo "OK — backups written to $HOME/config.py.pre-1.1.0-beta.bak, $HOME/crontab.pre-1.1.0-beta.bak, $HOME/ws-availability.pre-1.1.0-beta.commit"
```

**Verify:** all three backup files exist.

```bash
ls -la "$HOME"/config.py.pre-1.1.0-beta.bak "$HOME"/crontab.pre-1.1.0-beta.bak "$HOME"/ws-availability.pre-1.1.0-beta.commit
```

### 5.3 Fetch and check out v1.1.0-beta.1

```bash
cd "$WSAVAIL_DIR"
git fetch --tags origin
git checkout v1.1.0-beta.1
```

**Verify:**

```bash
git log --oneline -1
# expected: a commit on v1.1.0-beta.1 (e.g. "release: prepare v1.1.0-beta.1" or later)
grep '^VERSION' apps/globals.py
# expected: VERSION = "1.1.0-beta.1"
```

### 5.4 Set the per-node Sentry environment

Write the env var into a `.env` file next to `docker-compose.yml` so it survives reboots:

```bash
cd "$WSAVAIL_DIR"
echo "SENTRY_ENVIRONMENT=${NODE_TAG}_production" > .env
cat .env
# expected: SENTRY_ENVIRONMENT=<your_node>_production
```

`.env` is read automatically by Docker Compose v2 and is gitignored.

### 5.5 Build new images

```bash
cd "$WSAVAIL_DIR"
docker compose build api cacher
```

**Verify:** the build finishes with `Successfully tagged ws-availability*_api:latest` and `..._cacher:latest`. No errors or warnings about ObsPy or pymongo. ~3–5 min on a 4-core box.

### 5.6 Phase 1 — replace the API container only

```bash
cd "$WSAVAIL_DIR"
docker compose up -d --no-deps --build api
sleep 5
```

**Verify:**

```bash
docker ps --filter name=fdsnws-availability-api --format "{{.Status}} {{.Image}}"
# expected: Up <few seconds>  ws-availability*_api

curl -s http://127.0.0.1:9001/version
# expected: 1.1.0-beta.1

curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:9001/extent?net=<known_net>&sta=<known_sta>&start=2024-01-01&end=2024-01-02"
# expected: 200

docker exec fdsnws-availability-api env | grep SENTRY_ENVIRONMENT
# expected: SENTRY_ENVIRONMENT=<your_node>_production
```

If `/version` reports the OLD version or any check fails, **roll back the API now** (§11.2) before continuing.

### 5.7 Phase 2 — replace the cacher container

```bash
cd "$WSAVAIL_DIR"
docker compose up -d --no-deps --build cacher
```

The cacher runs two startup tasks immediately: an inventory refresh from FDSNWS-Station (~15–30 s) and a materialized-view update over the last 4 days (~30 s – several minutes depending on your data volume).

**Verify** by tailing the log until you see "Scheduler started":

```bash
docker logs -f fdsnws-availability-cacher 2>&1 | grep --line-buffered -E "Scheduler started|ERROR|Traceback"
# wait for: "Scheduler started"  then Ctrl-C
```

Expected log lines, in order:

```
Initializing APScheduler...
Running initial startup tasks...
Starting scheduled task: Rebuild Inventory Cache
Completed scheduled task: Rebuild Inventory Cache
Starting scheduled task: Update Availability Materialized View
Processing WFCatalog entries ... start: '<today-4d>', end: '<today>' started!
Processing WFCatalog entries ... completed!
Completed scheduled task: Update Availability Materialized View
Scheduler started successfully. Waiting for jobs to execute...
Added job "Rebuilds the cache mapping seed IDs to restriction data from FDSNWS Station"
Added job "Builds the daily_streams aggregation into the availability materialized view"
Scheduler started
```

If you see `ERROR` or `Traceback` instead, **roll back the cacher** (§11.2) and report at §12.

### 5.8 If your node had a host-cron entry for `views/main.js`

Some node deployments (NOA, possibly others) added a host-level cron at `01:00 UTC` like:

```
0 1 * * * cd /path/to/old-ws-availability/views && mongosh -u ... --eval "const daysBack=4" main.js
```

It's now redundant — the in-app scheduler does the same work at 06:00 UTC with `days_back=4`. Remove it:

```bash
crontab -l | grep -v "ws-availability.*views.*main.js" | crontab -
```

**Verify:**

```bash
crontab -l | grep -c "ws-availability"
# expected: 0
```

If you're unsure whether your node has such a cron, this command shows you safely:

```bash
crontab -l | grep -iE "ws-availability|fdsnws-availability"
```

### 5.9 Final smoke test — same 5 checks as a fresh install

```bash
curl -sf http://127.0.0.1:9001/ | grep -q FDSNWS-Availability && echo "Landing OK"
curl -s http://127.0.0.1:9001/version
curl -s "http://127.0.0.1:9001/extent?net=<known_net>&sta=<known_sta>&start=2024-01-01&end=2024-01-02" | head -5
curl -s "http://127.0.0.1:9001/query?net=<known_net>&sta=<known_sta>&start=2024-01-01&end=2024-01-02&format=json" | head -c 200
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:9001/extent?network=<known_net>"
# last command expected: 413 (broad-query rejection from Issue #60)
```

Replace `<known_net>` and `<known_sta>` with a station you know has data.

### 5.10 Confirm Sentry tag is flowing through

Hit your service a couple more times and then check Sentry: filter by `environment:<your_node>_production`. You should see transactions arriving with that tag and no events with `local_development`.

### 5.11 You're done

Watch logs and Sentry for the next 24 hours. The first real scheduled run happens at **06:00 UTC tomorrow** (`update-availability-view` job with `days_back=4`). If it fires on time and the Sentry monitor stays green, you've validated the new in-app scheduler in your environment.

---

## Rollback (Path B — to v1.0.5)

If anything goes wrong in §5.6–5.9, this command set restores the previous state. Run from `$WSAVAIL_DIR`:

```bash
cd "$WSAVAIL_DIR"
git checkout v1.0.5
rm -f .env
docker compose build api cacher
docker compose up -d --no-deps api cacher
# Restore the old host cron only if you ran §5.8:
crontab "$HOME/crontab.pre-1.1.0-beta.bak"
# Verify:
curl -s http://127.0.0.1:9001/version
# expected: 1.0.4
```

---

## 6. Path C — Side-by-side test (different port)

If you want to test the beta without touching your live v1.0.5 deployment, deploy it under a different `COMPOSE_PROJECT_NAME` and a different host port.

### 6.1 Clone into a separate directory

```bash
git clone https://github.com/EIDA/ws-availability.git ws-availability-beta
cd ws-availability-beta
git checkout v1.1.0-beta.1
cp config.py.sample config.py && $EDITOR config.py
```

### 6.2 Override the api port and project name

Create `docker-compose.override.yml`:

```yaml
services:
  cache:
    container_name: fdsnws-availability-beta-cache
  cacher:
    image: ghcr.io/eida/ws-availability/cacher:1.1.0-beta.1
    container_name: fdsnws-availability-beta-cacher
  api:
    image: ghcr.io/eida/ws-availability/api:1.1.0-beta.1
    container_name: fdsnws-availability-beta-api
    # Override the port the api binds to (Compose can't remap host ports under network_mode: host,
    # so we change the gunicorn bind address instead)
    command: gunicorn --bind 0.0.0.0:9101 --workers 1 --timeout 600 start:app
```

### 6.3 Start with a distinct project name

```bash
docker compose -p ws-availability-beta up -d
```

The beta now listens on `9101` while your v1.0.5 keeps serving on `9001`. Both use the same MongoDB and Redis (which is fine — both keys/cache entries are compatible).

> **Caveat:** because both stacks use `network_mode: host`, the Redis cache containers will conflict on port 6379 unless you also remap. The simplest path is to point the beta cacher/api at the existing Redis on 6379 and **not** start a second Redis container — set `cache.deploy.replicas: 0` or use `docker compose --no-deps up -d api cacher` to skip the cache service.

---

## 7. Enabling parallel fan-out (optional)

The fan-out path runs N parallel MongoDB cursors over disjoint time windows instead of one sequential cursor. It is most effective for long-range, narrow-NSLC queries (months/years × a few channels), where wall-clock time is dominated by cursor round-trips.

**Enable for one node:**

```bash
export FANOUT_ENABLED=true
# Optional tuning
export FANOUT_MAX_WORKERS=4        # default 4
export FANOUT_MIN_DAYS=7           # below this, single-cursor path is used
export FANOUT_WINDOW_DAYS=30       # target shard size

docker compose up -d api           # restart the api container only
```

**What to watch:**

1. **Mongo connection count** — peak rises to `gunicorn_workers × FANOUT_MAX_WORKERS` (with default `--workers 1`, that's 4 vs the prior 1). Verify:

   ```javascript
   db.serverStatus().connections
   ```

   Lower `FANOUT_MAX_WORKERS` if your Mongo has a tight budget.

2. **Memory ceiling** — each shard still respects the `MAX_DATA_ROWS + 1` cursor cap. Worst-case in-flight memory is `N × MAX_DATA_ROWS` (where N ≤ `FANOUT_MAX_WORKERS`), but Layer 3 broad-query rejection (Issue #60) already blocks queries that could approach this.

3. **Response parity** — `FANOUT_ENABLED=true` and `=false` must produce byte-identical response bodies for the same request (modulo the JSON `"created"` timestamp). A unit test enforces this against in-memory mocks. Please verify against your real Mongo for a few representative requests.

4. **Sentry traces** — each shard appears as a `db.mongo.shard` child span with `ts_start` / `ts_end` tags. The parallelism is visible in the trace timeline.

**Roll back fan-out without redeploying:**

```bash
unset FANOUT_ENABLED        # or set to false
docker compose up -d api
```

---

## 8. Configuration reference

| Env var | Required? | Default | Used by | What it does |
|---------|-----------|---------|---------|--------------|
| `RUNMODE` | yes | `production` (compose) | both | Picks production branch in `config.py`. |
| `MONGODB_HOST` | yes | `127.0.0.1` | both | WFCatalog MongoDB host. |
| `MONGODB_PORT` | no | `27017` | both | |
| `MONGODB_USR` / `MONGODB_PWD` | yes if Mongo auth is on | `""` | both | |
| `MONGODB_NAME` | no | `wfrepo` | both | DB name; also used as `authSource`. |
| `CACHE_HOST` | yes | `127.0.0.1` | both | Redis host. |
| `FDSNWS_STATION_URL` | yes | empty | cacher | Used to harvest restriction inventory. |
| **`SENTRY_DSN`** | no | empty | both | Set in `config.py` or env. Empty = Sentry disabled. |
| **`SENTRY_ENVIRONMENT`** | recommended | `local_development` | both | **New in 1.1.0-beta.** Tags events per node. Suggested values: `<your_node>_production`, `<your_node>_staging`. |
| `SENTRY_TRACES_SAMPLE_RATE` | no | `1.0` | both | 0.0 to 1.0. Set lower in production to reduce trace volume. |
| **`FANOUT_ENABLED`** | no | `false` | api | **New in 1.1.0-beta.** Enables parallel MongoDB fan-out. See §7. |
| **`FANOUT_MAX_WORKERS`** | no | `4` | api | Max parallel shards per request. |
| **`FANOUT_MIN_DAYS`** | no | `7` | api | Below this range size, single-cursor path is used. |
| **`FANOUT_WINDOW_DAYS`** | no | `30` | api | Target shard size. |
| `MAX_DATA_ROWS` | no | `2500000` | api | Row cap; over this returns 413. |
| `MAX_STREAMS` | no | `2000` | api | Stream-count cap. |

---

## 9. Post-deploy monitoring

For the first 24 hours after deployment, watch:

1. **Container health** — `docker compose ps` should show all three containers `Up` with no restart loops. `docker stats fdsnws-availability-api` should stay below the `mem_limit: 2g` cap.

2. **API logs** — `docker logs --tail=200 -f fdsnws-availability-api`. Look for:
   - `[SENTRY] Initialized. env=...` at startup — confirms `SENTRY_ENVIRONMENT` is picked up correctly.
   - `Number of collected rows: N` per request — sanity-check N is reasonable.
   - Any `Traceback` or `ERROR` — report per §12.

3. **Cacher logs** — `docker logs --tail=100 -f fdsnws-availability-cacher`. The scheduled jobs run at 03:00 (inventory refresh) and 06:00 (materialized view daily append). Confirm both run without errors within their first window.

4. **Sentry dashboard** — if configured, filter by your `environment` tag. New events from the beta should be tagged with your `SENTRY_ENVIRONMENT` value, not `local_development`.

5. **Request latency** — compare median and p95 against v1.0.5 for representative request shapes. The beta should be **no slower** than v1.0.5 with fan-out off; with fan-out on, multi-day queries should be 2–3× faster.

---

## 10. What to test specifically

These scenarios are most likely to surface beta-only regressions.

1. **Major dep bumps.** Anything that worked in v1.0.5 should keep working. Pay attention to:
   - Long-time-range queries (cursor iteration in pymongo 4.x has changed defaults).
   - Restriction inventory harvest in the cacher (obspy 1.5 has different XML parser behavior in some edge cases).
   - Flask routes with unusual headers / encodings (flask 3 dropped some legacy code paths).

2. **Sentry tagging.** If you set `SENTRY_DSN`, confirm events in Sentry are tagged with your `SENTRY_ENVIRONMENT` value, not `local_development`.

3. **Fan-out parity** (optional). With `FANOUT_ENABLED=false`, run a 90-day `/query` request and save the response. Then `FANOUT_ENABLED=true` and run the same request. Bodies must be byte-identical except for the JSON `"created"` timestamp.

4. **Fan-out under load** (optional). Run a small concurrent load (5–10 parallel curl loops) against the fan-out path; watch `docker stats` for the api container and Mongo `serverStatus().connections`. Memory should stay below `mem_limit: 2g`.

---

## 11. Rollback

### 11.1 Disable beta features without changing image

```bash
unset FANOUT_ENABLED            # disables fan-out
unset SENTRY_ENVIRONMENT        # falls back to local_development tag
docker compose up -d api
```

### 11.2 Roll back to v1.0.5 entirely

```bash
cd /path/to/ws-availability
git fetch --tags
git checkout v1.0.5

# Restore the override file to point at v1.0.5 images (if you used one)
# Or delete docker-compose.override.yml and let Compose rebuild from the v1.0.5 Dockerfile.

docker compose pull             # downloads v1.0.5 images
docker compose up -d
```

The v1.0.5 images are at `ghcr.io/eida/ws-availability/api:1.0.5` and `.../cacher:1.0.5`.

Restore your backed-up `config.py` if you modified it for the beta:

```bash
cp ~/config.py.pre-1.1.0-beta.bak config.py
```

Rollback typically takes 30–60 seconds of API downtime.

---

## 12. Reporting issues

Open an issue at <https://github.com/EIDA/ws-availability/issues> with the title prefix `[beta] ...`. Include:

- The beta tag you're running: `git describe --tags --abbrev=0`
- `docker compose ps` output
- `docker logs fdsnws-availability-api --tail=200` (scrub Mongo creds)
- The exact request URL that misbehaved + the response (status code + first ~10 lines of body)
- For Sentry traces: the trace ID (visible in the Sentry UI URL)
- `db.serverStatus().connections` if the issue is performance-related

For Sentry-visible errors with the beta, please also include the `environment` tag value so we can isolate the affected node.

---

## 13. Known issues

- **`/version` endpoint reports `1.1.0-beta.1`.** The version string will be stripped of the `-beta.1` suffix when the GA release is tagged. The git tag and Docker image tag are the authoritative version identifiers for the beta.
- **`test_restriction.py` has a pre-existing import error** (uses `from restriction` instead of `from apps.restriction`). Not introduced by the beta. The other 35 tests pass on the upgraded stack.
- **`numpy==2.4.0` is marked yanked** by upstream due to a backward-compat bug. It is pulled in transitively by obspy/scipy and is not used directly by the api. If you hit a numerical regression in the cacher, please report it; we may pin to `numpy<2.4` in a follow-up.
- **`maxPoolSize` doubles to `FANOUT_MAX_WORKERS` when fan-out is enabled.** If your MongoDB has a strict connection budget, plan accordingly or reduce `FANOUT_MAX_WORKERS`.

---

## 14. Feedback channel

For non-bug feedback (performance numbers, deployment friction, ideas), please email the maintainer or open a Discussion on the repo. Beta cycle is expected to last ~2 weeks; if no blocker is reported, `v1.1.0` will be tagged as stable.
