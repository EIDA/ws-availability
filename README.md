# Webservice availability

WS-Availability implements the FDSN specification of the availability webservice.

## Requirements

Following implementation requires MongoDB v4.2 or higher.

## Creating and populating the materialized view

In order to create and populate the view, simply run following script:

```bash
mongosh -u USER -p PASSWORD --authenticationDatabase wfrepo --eval "const daysBack=1" views/main.js
```

Remember to set `daysBack` to a suitable value. If you are making an initial build, it might be required to set it to a high value, e.g. `365` to scan last year. In regular production envoronment, it is recommended to scan in daily basis.

MongoDB script from `views/main.js` file can be extracted and used in MongoDB Atlas if available.

Materialized view filling can be automated using following cron entry. Please keep in mind this
procedure should be executed after WFCatalog processing is completed.

```bash
0 6 * * * cd ~/git/ws-availability/views && mongosh -u USERNAME -p PASSWORD --authenticationDatabase wfrepo --eval "const daysBack=2" main.js > /dev/null 2>&1
```

By default, materialized view is saved as `db.availability` in `wfcat` database.

## Running in Docker

1. Go to the root directory.
1. Copy `config.py.sample` to `config.py` and adjust it as needed.
1. Build the containers:

    ```bash
    docker-compose -p 'fdsnws-availability' up -d --no-deps --build
    ```

### Cache rebuild

The inventory cache will be constructed directly after containers are up. There is no expiration period enforced for the inventory information. To refresh the cache, simply start the `fdsnws-availability-cacher` container which will harvest and overwite the cached information:

```bash
docker restart fdsnws-availability-cacher

# To see the logs
docker logs --follow fdsnws-availability-cacher
```

Cache rebuilding can be automated using following cron entry (Docker container
will harvest and rebuild the metadata information on entry and then stop):

```bash
0 3 * * * docker restart fdsnws-availability-cacher
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

* `production`
* `test`

## References

This repository has been forked from [gitlab.com/resif/ws-availability](https://gitlab.com/resif/ws-availability), special thanks to our colleagues at RESIF for sharing their implementation of the FDSNWS-Availability web service. 💐
