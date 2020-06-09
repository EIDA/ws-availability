# Documentation du Webservice FDSN availability de RESIF

## Description

The availability web service returns detailed time span information of what time series data is available at the RESIF data center archive. Only unrestricted data are available.

There are two service query methods:

/extent

Produces a list of available time extents (earliest to latest) for selected channels (network, station, location, channel and quality) and time ranges.

/query

Produces a list of contiguous time spans for selected channels (network, station, location, channel and quality) and time ranges.


## Output format options:

  - text
  - json
  - geocsv

## Query usage

Query parameters are joined by ampersands "&", without blank space (see the sample queries). Default values are uppercase.
At least one station or one network must be specified.

# /extent usage

    /extent? [channel-options] [date-range-options] [merge-options] [sort-options] [format-options]

    where :

    channel-options      ::  [net=<network>] & [sta=<station>] & [loc=<location>] & [cha=<channel>] & [quality=<quality>]
    date-range-options   ::  [starttime=<date|duration>] & [endtime=<date|duration>]
    merge-options        ::  [merge=<quality|samplerate|overlap>]
    sort-options         ::  [orderby=<NSLC_TIME_QUALITY_SAMPLERATE|timespancount|timespancount_desc|latestupdate|latestupdate_desc>]
    display-options      ::  [includerestricted=<true|FALSE>] & [limit=<number>]
    format-options       ::  [format=<TEXT|geocsv|json|request|sync|zip>]


# /query usage

    /query? [channel-options] [date-range-options] [merge-options] [sort-options] [display-options] [format-options]

    where :

    channel-options      ::  [net=<network>] & [sta=<station>] & [loc=<location>] & [cha=<channel>] & [quality=<quality>]
    date-range-options   ::  [starttime=<date|duration>] & [endtime=<date|duration>]
    merge-options        ::  [merge=<quality|samplerate|overlap>] & [mergegaps=<number>]
    sort-options         ::  [orderby=<NSLC_TIME_QUALITY_SAMPLERATE|latestupdate|latestupdate_desc>]
    display-options      ::  [show=<latestupdate>] & [includerestricted=<true|FALSE>] & [limit=<number>]
    format-options       ::  [format=<TEXT|geocsv|json|request|sync|zip>]


    default values are uppercase


## Sample Queries

### with /extent
<a href="http://ws.resif.fr/fdsnws/availability/1/extent?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15">http://ws.resif.fr/fdsnws/availability/1/extent?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15</a>

<a href="http://ws.resif.fr/fdsnws/availability/1/extent?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15&show=latestupdate&orderby=timespancount">http://ws.resif.fr/fdsnws/availability/1/extent?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15&show=latestupdate&orderby=timespancount</a>


### with /query

<a href="http://ws.resif.fr/fdsnws/availability/1/query?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15">http://ws.resif.fr/fdsnws/availability/1/query?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15</a>

<a href="http://ws.resif.fr/fdsnws/availability/1/query?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15&merge=samplerate&mergegaps=36000">http://ws.resif.fr/fdsnws/availability/1/query?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15&merge=samplerate&mergegaps=36000</a>

## Detailed descriptions of each query parameter

### Station code details
The four parameters (network, station, location, channel) determine channels of interest.

| Parameters | Examples | Discussion                                          |
| :--------- | :------- | :-------------------------------------------------- |
| net[work]  | FR       | Seismic network name.                               |
| sta[tion]  | CIEL     | Station name.                                       |
| loc[ation] | 00       | Location code. Use loc=-- for empty location codes. |
| cha[nnel]  | HHZ      | Channel Code.                                       |
| quality    | M        | SEED quality code : D, M, Q, R.                     |


  - network = one to two alphanumeric characters
  - station = one to five alphanumeric characters
  - location = two alphanumeric characters
  - channel = three alphanumeric characters

#### Wildcards and Lists

  - Wildcards: the question mark __?__ represents any single character, while the asterisk __*__ represents zero or more characters.

  - List: multiple items may also be retrieved using a comma separated list. Wildcards may be included in the list.

For example, with channel codes: channel=EH?,BHZ

### Date-range options
The definition of the time interval may take different forms:

#### Expressed as calendar dates:

| Parameters  | Examples            | Discussion                               |
| :---------- | :------------------ | :--------------------------------------- |
| start[time] | 2015-08-12T01:00:00 | Start time expressed as a calendar date. |
| end[time]   | 2015-08-13T01:00:00 | End time expressed as a calendar date.   |

**Example:**

...starttime=2015-08-12T01:00:00&endtime=2015-08-13T01:00:00...

#### Expressed as a calendar date and duration (seconds):

| Parameters  | Examples            | Discussion                                  |
| :---------- | :------------------ | :------------------------------------------ |
| start[time] | 2015-08-12T01:00:00 | Start time expressed as a calendar date.    |
| end[time]   | 7200                | End time expressed as duration (seconds).   |

**Example:**

...starttime=2015-08-12T01:00:00&endtime=7200...

This example specifies a calendar date as the start time and duration of 7200 seconds specified in the end[time] parameter.

#### Expressed as a calendar date, duration (seconds) or the key word: "currentutcday":

The key word "currentutcday" means exactly midnight of today’s date (UTC time). It may be used for the start[time] and end[time] parameters.

| Parameters  | Examples      | Discussion                                  |
| :---------- | :------------ | :------------------------------------------ |
| start[time] | 7200          | Start time expressed as duration (seconds). |
| end[time]   | currentutcday | Today’s midnight (UTC).                     |

**Examples:**

1) ...starttime=currentutcday&endtime=7200...<br/>
2) ...starttime=7200&endtime=currentutcday...

The first example specifies the duration of 2 hours after today’s midnight (UTC).
The second example specifies the duration of 2 hours prior today’s midnight (UTC).

### Merge options

| Parameters      | Examples   | Discussion                                                            |
| :-------------- | :--------- | :-------------------------------------------------------------------- |
| merge           |            | Comma separated list (example merge=quality,samplerate).              |
|                 | quality    | Timespans from data with differing quality are grouped together.      |
|                 | samplerate | Timespans from data with differing sample rates are grouped together. |
|                 | overlap    | Not applicable.                                                       |


### Output options

| Parameters  | Examples | Discussion                                                                                  |
| :---------- | :------- | :------------------------------------------------------------------------------------------ |
| format      | json    | Specify output format. Accepted values are text (the default), json, sync, request and zip.  |
| includerestricted | false | Display or not restricted data.                                                          |
| limit       | integer  | Limits output to this many rows.                                                            |


### Sort options

| Parameters | Examples                     | Discussion                                                                      |
| :--------- | :--------------------------- | :------------------------------------------------------------------------------ |
| orderby    |                              | Sort rows by:                                                                   |
|            | nslc_time_quality_samplerate | network, station, location, channel, time-range, quality, sample-rate (default) |
|            | timespancount (extent only)  | number of timespans (small to large), network, station, location, channel, time-range, quality, sample-rate |
|            | timespancount_desc (extent only) | number of timespans (large to small), network, station, location, channel, time-range, quality, sample-rate |
|            | latestupdate                 | update-date (past to present), network, station, location, channel, time-range, quality, sample-rate |
|            | latestupdate_desc            | update-date (present to past), network, station, location, channel, time-range, quality, sample-rate |

<br/>

## /query method additional parameters

### Merge options

| Parameters      | Example  | Discussion                                                            |
| :-------------- | :------- | :-------------------------------------------------------------------- |
| mergegaps       | 86400.0 (1 day) | The timespans which are separated by gaps smaller than or equal to the given value are merged together. |

### Shows options

| Parameters    | Example       | Discussion                                        |
| :------------ | :------------ | :------------------------------------------------ |
| show          |               | Comma separated list (example show=latestupdate). |
|               | latestupdate  | Display the last date of data update.             |

<br/>

## Date and time formats

    YYYY-MM-DDThh:mm:ss[.ssssss] ex. 1997-01-31T12:04:32.123
    YYYY-MM-DD ex. 1997-01-31 (a time of 00:00:00 is assumed)

    where:

    YYYY    :: four-digit year
    MM      :: two-digit month (01=January, etc.)
    DD      :: two-digit day (01 through 31)
    T       :: date-time separator
    hh      :: two-digit hour (00 through 23)
    mm      :: two-digit number of minutes (00 through 59)
    ss      :: two-digit number of seconds (00 through 59)
    ssssss  :: one to six-digit number of microseconds (0 through 999999)

