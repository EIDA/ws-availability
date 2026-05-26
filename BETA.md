# ws-availability v1.1.0-beta.1 — Install

Beta release. API-compatible with v1.0.5.

## Prerequisites

- Docker with `docker-compose` (v1) or `docker compose` (v2).
- WFCatalog MongoDB ≥ 4.2 reachable from the host.
- Port 9001 free on the host.

## Install

`cd` into your `ws-availability` checkout (or `git clone https://github.com/EIDA/ws-availability.git` if you don't have one yet), then:

1. Check out the beta.

   ```bash
   git fetch --tags origin
   git checkout v1.1.0-beta.1
   ```

2. `config.py` — keep your existing one if you already have it; otherwise copy the sample:

   ```bash
   [ -f config.py ] || cp config.py.sample config.py
   $EDITOR config.py
   ```

   `MONGODB_*`, `CACHE_*`, and `FDSNWS_STATION_URL` are unchanged since v1.0.3 — keep your existing values.

   **What you must add depends on the version you're upgrading from.** Add the missing lines inside the `try:` block of `config.py` (next to the other `os.environ.get(...)` lines):

   - **Upgrading from v1.0.5 or v1.0.4** — add one line:

     ```python
     SENTRY_ENVIRONMENT = "yournode_production"
     ```

   - **Upgrading from v1.0.3 (or earlier)** — your `config.py` predates Sentry entirely. Add all three:

     ```python
     SENTRY_DSN = os.environ.get("SENTRY_DSN") or ""          # paste your Sentry DSN, or leave "" to disable Sentry
     SENTRY_TRACES_SAMPLE_RATE = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE") or "1.0")
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

## Verify

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

## Rollback

```bash
git checkout v1.0.5
docker-compose build
docker-compose up -d
```
