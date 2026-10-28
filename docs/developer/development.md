---
tags:
  - developer
---

# Development

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
