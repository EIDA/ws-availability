import os


class Config:

    """
    Configure Flask application from environment vars.
    Preconfigured values are set from: RUNMODE=test or RUNMODE=production
    Each parameter can be overriden directly by an environment variable.
    """

    PGHOST = PGUSER = PGPORT = PGDATABASE = ""
    RUNMODE = os.environ.get("RUNMODE")
    if RUNMODE == "production":
        PGHOST = "resif-pgprod.u-ga.fr"
        PGUSER = "wsavailability_ro"
        PGPORT = "5432"
        PGDATABASE = "seedtree5"
    elif RUNMODE == "test":
        PGHOST = "resif-pgpreprod.u-ga.fr"
        PGUSER = "wsavailability_ro"
        PGPORT = "5432"
        PGDATABASE = "seedtree5dev"

    try:
        PGHOST = os.environ.get("PGHOST") or PGHOST
        PGUSER = os.environ.get("PGUSER") or PGUSER
        PGPORT = os.environ.get("PGPORT") or PGPORT
        PGDATABASE = os.environ.get("PGDATABASE") or PGDATABASE
        os.environ["PG_DBURI"] = f"postgresql://{PGUSER}@{PGHOST}:{PGPORT}/{PGDATABASE}"
    except NameError as ne:
        print(ne)
        print(
            "Missing environment variables. Either RUNMODE=(test|production) or PGHOST, PGUSER, PGPORT and PGDATABASE should be set."
        )
        raise
