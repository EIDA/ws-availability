---
tags:
  - data-user
  - node-operator
---

# FDSNWS-Availability

A Flask implementation of the [FDSN Availability web service 1.0](http://www.fdsn.org/webservices/fdsnws-availability-1.0.pdf). It reports the time spans for which time-series data exist, served from a WFCatalog MongoDB.

It runs as three Docker containers: the **API** (Flask + gunicorn, port 9001), a **Redis** cache, and a **cacher** that keeps the restriction inventory and the `availability` view up to date on a built-in daily schedule.

> **Upgrading from v1.0.x?** See [Upgrading from v1.0.x](install.md#upgrading-from-v10x) for the exact `config.py` changes — it's a quick, self-contained checklist.

## References

Forked from [gitlab.com/resif/ws-availability](https://gitlab.com/resif/ws-availability) — thanks to our colleagues at RESIF for sharing their FDSNWS-Availability implementation. 💐
