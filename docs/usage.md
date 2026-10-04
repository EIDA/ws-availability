---
tags:
  - data-user
  - node-operator
---

# Usage

## Endpoints

API on port `9001`. `/query` (time spans per channel) and `/extent` (one row per channel) accept GET and POST. Also `/version`, `/application.wadl`, and `/` (landing page).

```bash
curl "127.0.0.1:9001/extent?net=NA&start=2023-02-01"
#Network Station Location Channel Quality SampleRate Earliest                    Latest                      Updated              TimeSpans Restriction
NA       SABA             BHZ     D       40.0       2023-02-01T00:00:00.000000Z 2023-02-14T00:00:00.000000Z 2023-02-14T07:41:41Z 1         OPEN
```

## What runs daily

The cacher runs a built-in scheduler — no host cron needed:

- **03:00 UTC** — refresh the restriction inventory from FDSNWS-Station into Redis.
- **06:00 UTC** — update the `availability` view from the last 4 days of WFCatalog data.
- **On startup** — both run once, so a restart leaves recent data fresh.

This covers only the recent window. To repair an older date (e.g. after a backfill), see [Back-processing](install.md#back-processing-historical-scoped-rebuild).
