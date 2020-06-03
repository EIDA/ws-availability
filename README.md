ws-availability implements the FDSN specification of the availability webservice.

# Prerequisite
## Backend
`ws-availability` relies on the seedtree5 database used at RESIF-DC.

The file `update_wsavailability_schema.sql` can be used to build the necessary materialized view.

This is RESIF-DC inners and is not detailed here.

# Deployment

## Configuring

TODO: we need to configure through environment variables.

Create the configuration file `apps/availability/database_config.ini` :

``` ini
[postgresql]
host=server
database=seedtree5
user=wsavailability_ro
password=*******
port=5432
```

## Development environment


    docker build -t ws-availability .
    docker run -d -p 8000:8000 -e RUNMODE=test --name ws-availability ws-availability



