# Webservice availability
ws-availability implements the FDSN specification of the availability webservice.


## Running in development environment
1. Go to the root directory:
1. Create the virtual environment:
    ```
    $ python3 -m venv env
    ```
1. Activate the virtual environment:
    ```
    $ source env/bin/activate
    ```
1. Install the dependencies:
    ```
    (env) $ pip install -r requirements.txt
    ```
1. Now you can either:
    1. Run it:
        ```
        (env) $ RUNMODE=test FLASK_APP=start.py flask run
        ```
    1. Debug it in VS Code (F5)

## Backend
`ws-availability` relies on the seedtree5 database used at RESIF-DC.

The file `update_wsavailability_schema.sql` can be used to build the necessary materialized view.

This is RESIF-DC inners and is not detailed here.


## Play around with docker


docker build -t ws-availability .
docker run --rm -e RUNMODE=test -p 8000:8000 --name ws-availability ws-availability


Then :

```
wget -O - http://localhost:8000/1/application.wadl
```

Run it in debug mode with flask:

```
RUNMODE=test FLASK_APP=start.py flask run
```

## RUNMODE builtin values

  * `production`
  * `test`

# References
This repository has been forked from https://gitlab.com/resif/ws-availability, special thanks to our colleagues at RESIF for sharing their implementation of the FDSNWS-Availability web service. 💐