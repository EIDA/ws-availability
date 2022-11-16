# Webservice availability

WS-Availability implements the FDSN specification of the availability webservice.

## Creating and populating the views

In order to create and populate the views, simply run following script:

```bash
mongosh --eval "const daysBack=1" views/main.js
```

Remember to set `daysBack` to a suitable value. If you are making an initial build, it might be required to set it to a high value, e.g. `365` to scan last year. In regular production envoronment, it is recommended to scan in daily basis.

MongoDB script from `views/main.js` file can be extracted and used in MongoDB Atlas if available.

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

## Running in Docker

1. Go to the root directory.
1. Copy `config.py.sample` to `config.py` and adjust it as needed.
1. Build the containers:

    ```bash
    docker-compose -p 'fdsnws-availability' up -d --no-deps --build
    ```

### Cache rebuild

The inventory cache will be constructed directly after containers are up. There is no expiration period enforced for the inventory information. To refresh the cache, simply start the `fdsn-availability-cacher` container which will harvest and overwite the cached information:

```bash
docker restart fdsn-availability-cacher

# To see the logs
docker logs --follow fdsn-availability-cacher
```

## RUNMODE builtin values

* `production`
* `test`

## References

This repository has been forked from [gitlab.com/resif/ws-availability](https://gitlab.com/resif/ws-availability), special thanks to our colleagues at RESIF for sharing their implementation of the FDSNWS-Availability web service. 💐
