---
tags:
  - node-operator
---

# Troubleshooting

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
