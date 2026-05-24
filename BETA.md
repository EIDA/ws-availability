# ws-availability v1.1.0-beta.1 — Install

Beta release. API-compatible with v1.0.5. Default behavior unchanged unless you opt in via env vars.

## Prerequisites

- Docker with the `docker-compose` v1.x (or `docker compose` v2) plugin.
- Running WFCatalog MongoDB ≥ 4.2 reachable from the host.
- Port 9001 free on the host.
- ~2 GB RAM.

## Install

Set two shell variables once. Replace `<your_node>` with a short tag (`noa`, `resif`, `orfeus`, …).

```bash
export WSAVAIL_DIR=/path/to/your/ws-availability/checkout    # adjust
export NODE_TAG=<your_node>                                  # adjust
```

1. Back up.

   ```bash
   cd "$WSAVAIL_DIR"
   cp config.py "$HOME/config.py.pre-1.1.0-beta.bak" 2>/dev/null || true
   crontab -l > "$HOME/crontab.pre-1.1.0-beta.bak" 2>/dev/null || true
   git rev-parse HEAD > "$HOME/ws-availability.pre-1.1.0-beta.commit" 2>/dev/null || true
   ```

2. Check out the beta.

   ```bash
   git fetch --tags origin
   git checkout v1.1.0-beta.1
   ```

3. Set the per-node Sentry tag.

   ```bash
   echo "SENTRY_ENVIRONMENT=${NODE_TAG}_production" > .env
   ```

4. If this is a first install, copy and edit `config.py`. (Skip on upgrade — your existing `config.py` is kept.)

   ```bash
   cp config.py.sample config.py
   $EDITOR config.py
   ```

5. Build images.

   ```bash
   docker-compose build api cacher
   ```

6. Replace the API container.

   ```bash
   docker-compose up -d --no-deps --build api
   ```

7. Replace the cacher container.

   ```bash
   docker-compose up -d --no-deps --build cacher
   ```

   Wait for the cacher startup tasks to finish:

   ```bash
   docker logs -f fdsnws-availability-cacher 2>&1 | grep --line-buffered -E "Scheduler started|ERROR|Traceback"
   ```

   Stop tailing (`Ctrl-C`) once you see `Scheduler started`.

8. If your node had a host cron triggering `views/main.js`, remove it. It is now redundant.

   ```bash
   crontab -l | grep -v "ws-availability.*views.*main.js" | crontab -
   ```

## Verify

Replace `<known_net>` and `<known_sta>` with one of your live stations.

```bash
curl -s http://127.0.0.1:9001/version
# expected: 1.1.0-beta.1

curl -s -o /dev/null -w "%{http_code}\n" \
  "http://127.0.0.1:9001/extent?net=<known_net>&sta=<known_sta>&start=2024-01-01&end=2024-01-02"
# expected: 200

curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:9001/extent?network=<known_net>"
# expected: 413

docker exec fdsnws-availability-api env | grep SENTRY_ENVIRONMENT
# expected: SENTRY_ENVIRONMENT=<your_node>_production
```

## Rollback

```bash
cd "$WSAVAIL_DIR"
git checkout v1.0.5
rm -f .env
docker-compose build api cacher
docker-compose up -d --no-deps api cacher
crontab "$HOME/crontab.pre-1.1.0-beta.bak"
```
