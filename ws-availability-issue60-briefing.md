# ws-availability — Issue #60 Briefing
## Memory Exhaustion from Unbounded Queries

This document gives a developer agent full context to understand and work on Issue #60
in the ws-availability service. Share it by pasting it into the conversation.

---

## 1. What is ws-availability?

A Flask-based Python implementation of the
[FDSN Availability Web Service spec](http://www.fdsn.org/webservices/fdsnws-availability-1.0.pdf).

It exposes two HTTP endpoints:
- `/fdsnws/availability/1/extent` — one row per channel, earliest/latest timestamps + timespan count
- `/fdsnws/availability/1/query` — individual time segments per channel

**Stack:** Flask + gunicorn / MongoDB (data store) / Redis (restriction cache + response cache) / Docker Compose

**Repositories:**
- Upstream: https://github.com/EIDA/ws-availability
- Active fork (feature/in-app-scheduler branch): https://github.com/NikolaosSokos/ws-availability/tree/feature/in-app-scheduler

---

## 2. Key source files relevant to this issue

| File | Role |
|------|------|
| `apps/utils.py` | Request validation, the `check_base_parameters()` guardrail |
| `apps/wfcatalog_client.py` | MongoDB query construction and execution, wildcard expansion |
| `apps/data_access_layer.py` | Row count check (`MAX_DATA_ROWS`), response formatting |
| `apps/globals.py` | Constants including `MAX_DATA_ROWS = 2_500_000` |
| `apps/root.py` | Request orchestration (GET/POST), calls validation then `get_output` |
| `docker-compose.yml` | 3 containers: `cache` (Redis), `cacher` (scheduler), `api` (gunicorn) |

---

## 3. What happened (the incident)

A user sent this request three times in quick succession:

```
GET /fdsnws/availability/1/extent?network=BW
```

No station, no channel, no time range. This matched approximately **4 million rows** in MongoDB.
Each request loaded all 4 million rows into Python RAM. With three concurrent requests,
the server's 8 GB RAM + SWAP was fully exhausted. The machine became unresponsive,
including SSH access.

---

## 4. The three root causes

### Root Cause A — The row limit check fires after memory is already consumed

In `apps/data_access_layer.py`, `get_output()`:

```python
data = collect_data(param_dic_list)   # ← entire DB result loaded into RAM here
nrows = len(data)
if nrows > MAX_DATA_ROWS:             # ← only checked AFTER memory is consumed
    return overflow_error(...)        # too late — damage already done
```

In `apps/wfcatalog_client.py`, `mongo_request()`:

```python
cursor = db.availability.find(qry, projection=PROJ)  # no .limit() on cursor
result += _apply_restricted_bit(cursor, ...)          # plain for-loop, pulls ALL docs
```

`_apply_restricted_bit` is a plain Python `for` loop that iterates the entire MongoDB cursor
eagerly into a list. There is no `.limit()` on the cursor and no early exit.
The 2.5 million row check in `get_output` is therefore purely cosmetic —
it generates a 413 error, but only after the RAM is already gone.

### Root Cause B — The existing guardrail has a logical gap

In `apps/utils.py`, `check_base_parameters()`:

```python
if params["network"] == params["station"] == params["channel"] == "*":
    return error_param(params, Error.NO_SELECTION)
```

This only catches the case where **all three** are wildcards simultaneously.
The request `?network=BW` sets `network="BW"`, which makes the condition `False`.
So a query that selects every station, every channel, and every time period for an entire
network — potentially millions of rows — passes without complaint and hits MongoDB.

### Root Cause C — The FDSN spec allows unbounded queries by design

The FDSN spec lists network, station, location, channel, starttime, endtime as
"required parameters" but simultaneously defines their defaults as "any" (wildcard).
"Required" means implementations must *support* them, not that clients must *provide* them.

A client can legally omit every parameter, and the spec-compliant response is to query
the entire database. Other FDSN implementations (e.g. Earthscope's dataselect,
which follows the same spec) reject requests with no time constraints rather than
attempting to serve the whole DB. This is a deliberate and justified policy departure.

---

## 5. The complete request execution path for `?network=BW`

**Step 1 — `apps/utils.py`, `check_base_parameters()`**
- The `NO_SELECTION` guard checks `net == sta == cha == "*"`. Since `net="BW"`, this is `False`.
- Request passes through.

**Step 2 — `apps/wfcatalog_client.py`, `_expand_wildcards()`**
- Expands `network="BW"` against the Redis inventory (restriction cache).
- `station` and `channel` remain `"*"` — no filtering applied at this stage.
- MongoDB query is built with only `net: {$in: ["BW"]}`, no `sta` or `cha` filter.

**Step 3 — `apps/wfcatalog_client.py`, `mongo_request()`**
- `db.availability.find(qry, projection=PROJ)` — no `.limit()`.
- `_apply_restricted_bit(cursor, ...)` iterates the full cursor, builds a Python list of ~4M rows.
- RAM fills up here.

**Step 4 — `apps/data_access_layer.py`, `get_output()`**
- `collect_data()` returns. RAM is already consumed.
- `len(data) > MAX_DATA_ROWS` is True → returns 413.
- Too late.

---

## 6. Bonus: a fourth risk (empty Redis inventory)

If Redis is empty (cacher not yet run, or Redis restarted), `_expand_wildcards()`
returns empty lists for all parameters. This means `params["network"]` becomes an
empty string and the MongoDB query ends up with **no filters at all** — matching the
entire collection regardless of user input. This is a separate but related crash vector.

---

## 7. Proposed solution — four independent layers

These are ordered by implementation priority (do earlier = protects you while working on later).

---

### Layer 1 — Docker memory limit (do today, zero code change)

Add to `docker-compose.yml`:

```yaml
api:
  mem_limit: 2g
  memswap_limit: 2g
```

This ensures that even if everything else fails, the host OS is never threatened.
The container gets OOM-killed, gunicorn restarts it, and the other containers keep running.
`memswap_limit` = `mem_limit` prevents swap usage, which just delays the kill while
making the machine progressively more sluggish.

**Risk:** Zero. **Impact:** Immediate protection for the host.

---

### Layer 2 — Cap the MongoDB cursor (one-line fix, makes the 413 meaningful)

In `apps/wfcatalog_client.py`, `mongo_request()`:

```python
# Before:
cursor = db.availability.find(qry, projection=PROJ)

# After:
cursor = db.availability.find(qry, projection=PROJ).limit(MAX_DATA_ROWS + 1)
```

MongoDB enforces the cap in the DB engine. Python never allocates memory for excess rows.
The existing `len(data) > MAX_DATA_ROWS` check in `get_output` then works as intended —
if `MAX_DATA_ROWS + 1` rows come back, return 413 before any processing.

**Risk:** Near zero. Has no effect on normal queries.

---

### Layer 3 — Reject broad requests without a time range (policy fix)

In `apps/utils.py`, `check_base_parameters()`, after the existing `NO_SELECTION` check:

```python
# Require a time range if the query is broad (station and channel are wildcards)
no_time_range = params["start"] is None and params["end"] is None
broad_nslc = params["station"] == "*" and params["channel"] == "*"
if no_time_range and broad_nslc:
    return error_param(
        params,
        "Request too broad: please provide starttime/endtime, "
        "or specify at least a station or channel."
    )
```

This would have blocked `?network=BW` with a 400 before touching the DB.
Requests like `?network=BW&station=RMOA` or `?network=BW&start=2024-01-01&end=2024-02-01`
would still be allowed.

**Trade-off:** Policy departure from literal FDSN spec. Users relying on network-only
queries will get a 400. Needs documentation in README and release notes.
Precedent: Earthscope dataselect does the same thing.

---

### Layer 4 — Lower and externalise `MAX_DATA_ROWS`

`MAX_DATA_ROWS = 2_500_000` in `globals.py` is hardcoded and too high.
At ~200–400 bytes per row after Python object overhead:
- 100,000 rows ≈ 40–80 MB (safe)
- 500,000 rows ≈ 200 MB (reasonable)
- 2,500,000 rows ≈ 1 GB per request (dangerous with concurrent requests)

**Fix part 1:** Move to `apps/settings.py` as an env-var-backed field:

```python
max_data_rows: int = Field(100_000, alias="MAX_DATA_ROWS")
```

**Fix part 2:** Remove from `globals.py`, import from `settings` everywhere it is used
(`data_access_layer.py`, `root.py`, error string in `globals.py`).

This allows operators to tune the limit per deployment without code changes.

**Trade-off:** Breaking change for users who relied on large responses. Needs communication.

---

## 8. Recommended implementation order

1. **Layer 1** — Docker mem_limit. Do this immediately. No code needed.
2. **Layer 2** — Cursor `.limit()`. One line, no user-visible change, makes 413 real.
3. **Layer 3** — Broad query rejection. Requires policy decision and documentation.
4. **Layer 4** — Lower and externalise `MAX_DATA_ROWS`. Most disruptive, do last.

---

## 9. Files to change per layer

| Layer | File(s) to change |
|-------|-------------------|
| 1 | `docker-compose.yml` |
| 2 | `apps/wfcatalog_client.py` |
| 3 | `apps/utils.py`, `apps/globals.py` (new error string) |
| 4 | `apps/globals.py`, `apps/settings.py`, `apps/data_access_layer.py`, `apps/root.py` |
