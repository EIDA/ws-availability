# Webservice availability

WS-Availability implements the FDSN specification of the availability webservice.

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

1. Create memcache instance (mandatory for WFCatalog-based deployment):

    ```bash
    docker run -d --restart=always --net=host memcached
    ```

1. Now you can either:
    1. Run it:

        ```bash
        RUNMODE=test FLASK_APP=start.py flask run
        ```

    1. Debug it in VS Code (F5)

## Running in Docker

1. Go to the root directory.
1. Copy `config.py.sample` to `config.py` and adjust it as needed.
1. Build the containers:

    ```bash
    docker-compose -p 'fdsnws-availability' up -d --no-deps --build
    ```

## Backend

`ws-availability` relies on the seedtree5 database used at RESIF-DC.

The file `update_wsavailability_schema.sql` can be used to build the necessary materialized view.

This is RESIF-DC inners and is not detailed here.

## Play around with docker

```bash
$ docker build -t ws-availability:latest .
# Run with bridged network
$ docker run -d --restart=always -e RUNMODE=production -p 9001:9001 --name ws-availability ws-availability:latest
# Or
$ docker run --rm -e RUNMODE=test -p 9001:9001 --name ws-availability ws-availability:latest
# Run with shared host network
$ docker run -d --restart=always -e RUNMODE=production --net=host --name ws-availability ws-availability:latest
# Or
$ docker run --rm --net=host -e RUNMODE=test --name ws-availability ws-availability:latest
```

## Memcache

⚠️ EIDA deployment requires a memcache instance, it can be easily deployed using Docker:

```bash
docker run -d --restart=always --net=host memcached
# or
docker run -d --restart=always -p 11211:11211 memcached
```

Then :

```bash
wget -O - http://localhost:9001/1/application.wadl
```

Run it in debug mode with flask:

```bash
RUNMODE=test FLASK_APP=start.py flask run
```

## RUNMODE builtin values

* `production`
* `test`

## References

This repository has been forked from [gitlab.com/resif/ws-availability](https://gitlab.com/resif/ws-availability), special thanks to our colleagues at RESIF for sharing their implementation of the FDSNWS-Availability web service. 💐
