
// Connect to wfrepo
use("wfrepo");

// 1. Create a dummy daily_stream entry
// It must trigger 'updateAvailabilityContinuous', so avail < 100
var streamId = new ObjectId();
var dayStart = ISODate("2020-06-05T00:00:00.000Z");
var dayEnd = ISODate("2020-06-06T00:00:00.000Z");

var streamDoc = {
    _id: streamId,
    net: "NL",
    sta: "BHAR",
    loc: "HGN",
    cha: "D",
    qlt: "D",
    ts: dayStart,
    te: dayEnd,
    avail: 50.0, // < 100 to trigger continuous lookup
    srate: [200.0], // Array as per updateAvailabilityDaily aggregation
    created: new Date()
};

db.daily_streams.insertOne(streamDoc);
print("Inserted daily_stream: " + streamId);

// 2. Create overlapping c_segments
// Row 1 End:   ...17:26:59.005
// Row 2 Start: ...17:26:59.000 (Overlap)
var t_mid = ISODate("2020-06-05T17:26:59.000Z");
var t_end1 = ISODate("2020-06-05T17:26:59.005Z");
var t_end2 = ISODate("2020-06-05T17:32:09.005Z");

var seg1 = {
    streamId: streamId,
    srate: 200.0,
    ts: dayStart,
    te: t_end1,
    num_samples: 1000 // Dummy
};

var seg2 = {
    streamId: streamId,
    srate: 200.0,
    ts: t_mid, // OVERLAP START
    te: t_end2,
    num_samples: 1000 // Dummy
};

db.c_segments.insertMany([seg1, seg2]);
print("Inserted 2 overlapping c_segments.");

print("Now run main.js to populate 'availability' view.");
