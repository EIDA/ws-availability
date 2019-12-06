CREATE OR REPLACE FUNCTION update_wsavailability_traces(merge varchar DEFAULT 'merge')
RETURNS VOID AS $$
DECLARE
    start1 timestamp := clock_timestamp();
    cols_traces text := 'traces.network, traces.station, traces.location, traces.channel, traces.quality, traces.samplerate, traces.starttime, traces.endtime, lastupdated, policy';
    match text := 'WHERE traces.fileindex = files.fileindex
AND traces.network = channel_with_record.network
AND traces.station = channel_with_record.station
AND traces.location = channel_with_record.location
AND traces.channel = channel_with_record.channel
AND (traces.starttime BETWEEN channel_with_record.starttime AND channel_with_record.endtime
AND traces.endtime BETWEEN channel_with_record.starttime AND channel_with_record.endtime)';

    rows_traces text := (SELECT string_agg(format('SELECT %s FROM %I.traces, %I.files, wsavailability.channel_with_record %s ', cols_traces, nspname, nspname, match), 'UNION ')
FROM pg_catalog.pg_namespace WHERE nspname LIKE '\_%');

    table_traces text := format('CREATE TABLE traces AS %s;', rows_traces);
BEGIN
    RAISE NOTICE 'wsavailability update starting...';
    DROP TABLE IF EXISTS wsavailability.channel_with_record;
    CREATE TABLE wsavailability.channel_with_record AS SELECT * FROM channel_with_record;
    UPDATE wsavailability.channel_with_record SET location = '' WHERE location = '--';
    UPDATE wsavailability.channel_with_record SET policy = 'OPEN' WHERE policy = 'open';
    UPDATE wsavailability.channel_with_record SET policy = 'RESTRICTED' WHERE policy = 'closed';

    RAISE NOTICE 'creating raw table...';
    DROP TABLE IF EXISTS traces;
    EXECUTE table_traces;
    ALTER TABLE traces ADD COLUMN mergeid bigint;
    RAISE NOTICE 'raw temp traces table created in %', age(clock_timestamp(), start1);

    IF merge = 'merge' THEN
        PERFORM merge_traces();
    END IF;

    RAISE NOTICE 'replace empty location by double dash...';
    UPDATE traces SET location = '--' WHERE coalesce(TRIM(location), '') = '';

    RAISE NOTICE 'creating indexes...';
    CREATE INDEX ON traces (network);
    CREATE INDEX ON traces (station);
    CREATE INDEX ON traces (location);
    CREATE INDEX ON traces (channel);
    CREATE INDEX ON traces (quality);

    DROP TABLE IF EXISTS wsavailability.traces;
    ALTER TABLE traces SET SCHEMA wsavailability;
    RAISE NOTICE 'wsavailability traces updated in %', age(clock_timestamp(), start1);
    GRANT SELECT ON TABLE wsavailability.traces TO wsavailability_ro;
END;
$$ LANGUAGE plpgsql;


----------------------------------------------------------------------------------------
---------------------------------- merge_traces FUNCTION -------------------------------
----------------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION merge_traces()
RETURNS VOID AS $$
DECLARE
    j INT := 0;
    maxgap numeric := 0;
    start1 timestamp := clock_timestamp();
    rec RECORD;
    prec RECORD;
BEGIN
    RAISE NOTICE 'merge preprocessing...';
    CREATE TABLE wstemp AS TABLE traces WITH NO DATA;
    FOR rec IN SELECT * FROM traces
        ORDER BY network, station, location, channel, quality, samplerate, starttime, endtime
    LOOP
        IF j > 0 THEN
            maxgap = 1 / NULLIF(prec.samplerate, 0)::numeric;
            IF prec.network = rec.network AND prec.station = rec.station
                AND prec.location = rec.location AND prec.channel = rec.channel
                AND prec.quality = rec.quality AND prec.samplerate = rec.samplerate
                AND extract('epoch' from rec.starttime - prec.endtime) <= maxgap
            THEN rec.endtime = GREATEST(prec.endtime, rec.endtime);
            ELSE
                j = j + 1;
            END IF;
        ELSE
            j = 1;
        END IF;

        INSERT INTO wstemp VALUES (rec.network, rec.station, rec.location, rec.channel,
        rec.quality, rec.samplerate, rec.starttime, rec.endtime, rec.lastupdated, rec.policy, j);

        prec = rec;
    END LOOP;

    RAISE NOTICE 'creating merged table...';
    DROP TABLE traces;
    CREATE TABLE traces AS
        SELECT network, station, location, channel, quality, samplerate,
            min(starttime) as starttime, max(endtime) as endtime, max(lastupdated) as lastupdated, policy, mergeid
        FROM wstemp
        GROUP BY mergeid, station, channel, network, location, samplerate, quality, policy;

    DROP TABLE wstemp;
    RAISE NOTICE 'merged table created in %', age(clock_timestamp(), start1);
END;
$$ LANGUAGE plpgsql;

