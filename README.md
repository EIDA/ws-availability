# Webservice availability
ws-availability implements the FDSN specification of the availability webservice.

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

Run it in debug mode with flask :

```
docker run --rm --name ws-availability -e RUNMODE=production -e FLASK_APP=start.py ws-availability flask run
```

## RUNMODE builtin values

  * `production` 
  * `test`
