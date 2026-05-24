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

2. `config.py` — keep your existing one if you already have it; otherwise copy the sample and edit:

   ```bash
   [ -f config.py ] || cp config.py.sample config.py
   $EDITOR config.py    # set MONGODB_*, FDSNWS_STATION_URL, SENTRY_DSN
   ```

3. Set your node's Sentry tag (replace `noa` with your node short name):

   ```bash
   echo "SENTRY_ENVIRONMENT=noa_production" > .env
   ```

4. Build and start.

   ```bash
   docker-compose build
   docker-compose up -d
   ```

5. If your node had a host cron triggering `views/main.js`, remove it — it's now redundant.

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

docker exec fdsnws-availability-api env | grep SENTRY_ENVIRONMENT
# expected: SENTRY_ENVIRONMENT=noa_production
```

## Rollback

```bash
git checkout v1.0.5
rm -f .env
docker-compose build
docker-compose up -d
```
