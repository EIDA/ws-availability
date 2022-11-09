// Switch to `wfrepo` database
use("wfrepo");

// Define function filling `availability` view from `daily_streams` collection.
// We select documents with 100% availability and merge them into the view.
updateAvailabilityDaily = function (startDate) {
  db.daily_streams.aggregate([
    { $match: { ts: { $gte: startDate }, avail: { $gte: 100 } } },
    {
      $group: {
        _id: "$_id",
        net: { $first: "$net" },
        sta: { $first: "$sta" },
        loc: { $first: "$loc" },
        cha: { $first: "$cha" },
        qlt: { $first: "$qlt" },
        srate: { $first: { $arrayElemAt: ["$srate", 0] } },
        ts: { $first: "$ts" },
        te: { $first: "$te" },
        created: { $first: "$created" },
        restr: { $first: "OPEN" },
        count: { $first: 1 },
      },
    },
    { $merge: { into: "availability", on: "_id", whenMatched: "replace" } },
  ]);
};

// Define function filling `availability` view from `c_segments` collection.
// We select documents with <100% availability, join them on c_segments, unwind
// the result and merge into the view.
updateAvailabilityContinuous = function (startDate) {
  db.daily_streams.aggregate([
    { $match: { ts: { $gte: startDate }, avail: { $lt: 100 } } },
    {
      $lookup: {
        from: "c_segments",
        localField: "_id",
        foreignField: "streamId",
        as: "c_segments",
      },
    },
    { $unwind: "$c_segments" },
    {
      $group: {
        _id: "$c_segments._id",
        net: { $first: "$net" },
        sta: { $first: "$sta" },
        loc: { $first: "$loc" },
        cha: { $first: "$cha" },
        qlt: { $first: "$qlt" },
        srate: { $first: "$c_segments.srate" },
        ts: { $first: "$c_segments.ts" },
        te: { $first: "$c_segments.te" },
        created: { $first: "$created" },
        restr: { $first: "OPEN" },
        count: { $first: 1 },
      },
    },
    { $merge: { into: "availability", on: "_id", whenMatched: "replace" } },
  ]);
};

// Recalculate everything starting on YYYY-MM-DD:
updateAvailabilityDaily(new ISODate("2022-01-01"));
updateAvailabilityContinuous(new ISODate("2022-01-01"));