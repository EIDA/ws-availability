"""
avail-rebuild — on-demand rebuild of the `availability` materialized view for a
specific date range and (optionally) a specific NSLC subset.

Why this exists
---------------
The cacher's daily scheduler only refreshes a rolling recent window
(`run_updates(days_back=4)` in apps/scheduler.py). It cannot repair *historical*
gaps: if WFCatalog is (re)populated for an old date — e.g. after a backfill or a
data correction surfaced by an EIDA consistency report — the availability view
for that date is never rebuilt, so `/availability` keeps reporting "no data"
even though dataselect / the SDS archive serve it.

The underlying engine (`AvailabilityUpdater.run_updates`) already accepts an
arbitrary start/end and is idempotent (`$merge whenMatched:"replace"`). Until
now the only ways to drive it for an old range were the host-side
`mongosh ... views/main.js` invocation (needs a repo checkout + DB creds on the
host, and is net+sta+date only) or editing the scheduler. This CLI exposes the
engine as a stable, versioned, in-container interface so an orchestrator (dmtri)
can trigger a scoped rebuild without reaching into MongoDB:

    docker exec fdsnws-availability-cacher \
        avail-rebuild --net IV --sta ABC --start 2008-01-01 --end 2009-01-01

Running inside the cacher means MongoDB credentials come from the container's
own config.py/settings — the caller never handles DB secrets. Unlike main.js it
also accepts full NSLC (--loc/--cha) for channel-precise rebuilds.

Prerequisite
------------
WFCatalog (`daily_streams`/`c_segments`) must already contain the range. This
tool only re-derives the view *from* WFCatalog; it does not scan the SDS
archive. Run the WFCatalog refresh for the range first — otherwise the rebuild
completes cleanly but writes nothing.
"""
import argparse
import logging
import sys
from datetime import datetime
from typing import Optional

from apps.settings import settings
from apps.updater import AvailabilityUpdater
from apps.wfcatalog_client import get_db_client

logging.basicConfig(
    handlers=[logging.StreamHandler()],
    level=logging.INFO,
    format="[%(asctime)s] [AVAIL-REBUILD] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S +0000",
)
logger = logging.getLogger(__name__)


def _anchor_regex(csv: Optional[str]) -> str:
    """Turn "IV,GE" into the anchored regex ``^(IV|GE)$`` (exact match per code).

    None/empty -> ``^.*$`` (match all), mirroring ``run_updates``' default and
    main.js's ``^${networks}$`` convention.
    """
    if not csv:
        return "^.*$"
    codes = [c.strip() for c in csv.split(",") if c.strip()]
    if not codes:
        return "^.*$"
    return "^(" + "|".join(codes) + ")$"


def _code_list(csv: Optional[str]) -> Optional[list[str]]:
    """Turn "00,--" into ``["00", ""]``; ``--`` denotes the empty location.

    None -> None (dimension left unconstrained in the aggregation).
    """
    if csv is None:
        return None
    return ["" if c.strip() == "--" else c.strip() for c in csv.split(",")]


def _parse_day(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid date '{value}', expected YYYY-MM-DD"
        )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="avail-rebuild",
        description=(
            "Rebuild the availability materialized view for a date range (and "
            "optional NSLC subset) from WFCatalog. Idempotent — safe to re-run."
        ),
    )
    p.add_argument("--net", help="Comma-separated network codes (exact). Default: all.")
    p.add_argument("--sta", help="Comma-separated station codes (exact). Default: all.")
    p.add_argument(
        "--loc",
        help="Comma-separated location codes (exact). For the empty location pass "
             "--loc=-- (attached form) or --loc '' . Default: all.",
    )
    p.add_argument("--cha", help="Comma-separated channel codes (exact). Default: all.")
    p.add_argument(
        "--start", required=True, type=_parse_day,
        help="Range start, YYYY-MM-DD (inclusive).",
    )
    p.add_argument(
        "--end", required=True, type=_parse_day,
        help="Range end, YYYY-MM-DD. Day boundary: matches segments with te <= end "
             "(e.g. for all of 2008 use --end 2009-01-01).",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.end < args.start:
        logger.error(
            "END (%s) is before START (%s) — nothing to do.",
            args.end.date(), args.start.date(),
        )
        return 2

    # Sentry is optional; never let its wiring (or a missing config.py) block a
    # rebuild.
    try:
        from apps.sentry import init_sentry
        init_sentry()
    except Exception as e:  # pragma: no cover - defensive, env-dependent
        logger.warning("Sentry init skipped: %s", e)

    networks = _anchor_regex(args.net)
    stations = _anchor_regex(args.sta)
    locations = _code_list(args.loc)
    channels = _code_list(args.cha)

    db = get_db_client().get_database(settings.mongodb_name)
    updater = AvailabilityUpdater(db)

    logger.info(
        "Rebuild start: net=%s sta=%s loc=%s cha=%s range=%s..%s db=%s",
        networks, stations, locations, channels,
        args.start.date(), args.end.date(), settings.mongodb_name,
    )
    updater.run_updates(
        networks=networks,
        stations=stations,
        start_date=args.start,
        end_date=args.end,
        locations=locations,
        channels=channels,
    )
    logger.info(
        "Rebuild complete. If a previous query was cached, flush Redis or wait "
        "out CACHE_RESP_PERIOD before re-checking /availability."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
