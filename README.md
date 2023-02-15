# FDSNWS-Availability Deployment

## Overview

- WFCatalog DB (gray) - database used by the WFCatalog collector and API.
- FDSNWS-Availability API (blue) - Flask-based FDSNWS-Availability implementation.
- FDSNWS-Availability Cache (green) - Redis-based cache to store restriction information.
- FDSNWS-Availability Cacher (orange) - Python-based container to harvest and store restriction information.
- FDSNWS-Availability Update (purple) - JS script to fill the `availability` materialized view using WFCatalog `daily_streams` and `c_segments` collections.

![[deployment.png]]

Following implementation requires MongoDB v4.2 or higher.

## Deployment

1. Clone the [https://github.com/EIDA/ws-availability] repository and go to its root
1. Copy `config.py.sample` to `config.py` and adjust it as needed (please notice there are two sections - `RUNMODE == "production"` and `RUNMODE == "test"`; for Docker deployment use the `production` section):

    ```bash
    # WFCatalog MongoDB
    MONGODB_HOST = "localhost" #MongoDB host
    MONGODB_PORT = 27017 #MongoDB port
    MONGODB_USR = "" #MongoDB user
    MONGODB_PWD = "" #MongoDB password
    MONGODB_NAME = "wfrepo" #MongoDB database name
    FDSNWS_STATION_URL = "https://orfeus-eu.org/fdsnws/station/1/query" #FDSNWS-Station endpoint to harvest restriction information from
    CACHE_HOST = "localhost" #Cache host
    CACHE_PORT = 6379 #Cache port
    CACHE_INVENTORY_KEY = "inventory" #Cache key for restriction information
    CACHE_INVENTORY_PERIOD = 0 #Cache invalidation period for `inventory` key; 0 = never invalidate
    CACHE_RESP_PERIOD = 1200 #Cache invalidation period for API response
    ```

1. Build the containers:

    ```bash
    docker-compose -p 'fdsnws-availability' up -d --no-deps --build
    ```

    When the Docker stack is deployed, you will see 3 containers running:

    ```bash
    $ docker ps
    CONTAINER ID   IMAGE                         COMMAND                  CREATED         STATUS        PORTS                      NAMES
    4e3dace01fb0   fdsnws-availability_api       "/bin/bash -c 'gunic…"   10 seconds ago  Up 5 seconds  0.0.0.0:9001->9001/tcp     fdsnws-availability-api
    3c91e0d1c5e6   fdsnws-availability_cacher    "/bin/bash -c 'pytho…"   10 seconds ago  Up 5 seconds  0.0.0.0:11211->11211/tcp   fdsnws-availability-cacher
    d983e64d64a8   redis:7.0-alpine              "docker-entrypoint.s…"   10 seconds ago  Up 5 seconds  0.0.0.0:6379->6379/tcp     fdsnws-availability-cache
    ```

    You can follow the `fdsnws-availability-cacher` container to see the status of restriction information harvesting:

    ```bash
    $ docker logs --follow fdsnws-availability-cacher
    [2023-01-11 09:47:38 +0000] [0] [INFO] Getting inventory from FDSNWS-Station...
    [2023-01-11 09:47:39 +0000] [0] [INFO] Harvesting 33 from https://orfeus-eu.org/fdsnws/station/1/query?level=network: 2M,3T,6A...
    #...
    [2023-02-15 08:31:56 +0000] [0] [INFO] Completed caching inventory from FDSNWS-Station
    ```

    Once `fdsnws-availability-cacher` is completed, it will go down. Harvested information is stored in the Redis DB served by `fdsnws-availability-cache` container. To rebuild the cache, simply restart the container using:

    ```bash
    docker start fdsnws-availability-cacher
    ```

    To automate cache rebuilding process, add following line to `cron`:

    ```bash
    # Rebuild FDSNWS-Availability restriction information cache daily at 3:00 AM
    0 3 * * * docker restart fdsnws-availability-cacher
    ```

    It will harvest and overwrite the restricted information stored in Redis instance.

1. Materialized view
    1. Initial build

        When the stack is initially deployed, the materialized view is not yet in place. To build it, issue the following command:

        ```bash
        mongosh -u USER -p PASSWORD --authenticationDatabase wfrepo --eval "const daysBack=365" views/main.js
        ```

        It will go throught the documents in `daily_streams` and `c_segments` from last year, extract availability information and store it in the `availability` materialized view.

    1. Daily appension

        To automate availability information appension, add following line to `cron`:

        ```bash
        0 6 * * * cd ~/ws-availability/views && mongosh -u USERNAME -p PASSWORD --authenticationDatabase wfrepo --eval "const daysBack=2" main.js > /dev/null 2>&1
        ```

        It will go throught the documents in `daily_streams` and `c_segments` from last 2 days, extract availability information and append it to the `availability` materialized view. We use 2 days here simply to process data with small overlap.

    1. Indexes

        It is highly suggested to create at least following index in the `availability` materialized view. First, login to your MongoDB instance using `mongosh` and then execute following commands:

        ```bash
        use wfrepo;
        db.availability.createIndex({ net: 1, sta: 1, loc: 1, cha: 1, ts: 1, te: 1 })
        ```

## Running in development environment

1. Go to the root directory.
1. Copy `config.py.sample` to `config.py` and adjust it as needed.
1. Create the virtual environment:

    ```bash
    python3 -m venv env
    ```

1. Activate the virtual environment:

    ```bash
    source env/bin/activate
    ```

1. Install the dependencies:

    ```bash
    pip install -r requirements.txt
    ```

1. Create Redis instance (mandatory for WFCatalog-based deployment):

    ```bash
    docker run -p 6379:6379 --name cache -d redis:7.0-alpine redis-server --save 20 1 --loglevel warning
    ```

1. Build the cache:

    ```bash
    python3 cache.py
    ```

1. Now you can either:
    1. Run it:

        ```bash
        RUNMODE=test FLASK_APP=start.py flask run

        # Or with gunicorn:
        RUNMODE=test gunicorn --workers 2 --timeout 60 --bind 0.0.0.0:9001 start:app
        ```

    1. Debug it in VS Code (F5) after selecting "Launch (Flask)" config.

## RUNMODE builtin values

- `production`
- `test`

## Ideas for improvements

1. Move restriction information from Redis cache directly to the `db.availability` materialized view. This would imply modifying the `views/main.js` script with code harvesting this information directly from the FDSNWS-Station instance.
1. Modify underlying RESIF code from logic based on list of arrays to list of objects/dicts which is native MongoDB response to prevent the object/dict to array casting.

## References

This repository has been forked from [gitlab.com/resif/ws-availability](https://gitlab.com/resif/ws-availability), special thanks to our colleagues at RESIF for sharing their implementation of the FDSNWS-Availability web service. 💐
