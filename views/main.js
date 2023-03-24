use("wfrepo");

updateAvailabilityDaily = function (networks, stations, startDate, endDate) {
  db.daily_streams.aggregate([
    {
      $match: {
        net: { $regex: networks },
        sta: { $regex: stations },
        ts: { $gte: startDate },
        te: { $lte: endDate },
        avail: { $gte: 100 },
      },
    },
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
    {
      $merge: { into: "availability_test", on: "_id", whenMatched: "replace" },
    },
  ]);
};

updateAvailabilityContinuous = function (
  networks,
  stations,
  startDate,
  endDate
) {
  db.daily_streams.aggregate([
    {
      $match: {
        net: { $regex: networks },
        sta: { $regex: stations },
        ts: { $gte: startDate },
        te: { $lte: endDate },
        avail: { $lt: 100 },
      },
    },
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
    {
      $merge: { into: "availability_test", on: "_id", whenMatched: "replace" },
    },
  ]);
};

function formatDate(date) {
  return [
    date.getFullYear(),
    padTo2Digits(date.getMonth() + 1),
    padTo2Digits(date.getDate()),
  ].join("-");
}

function padTo2Digits(num) {
  return num.toString().padStart(2, "0");
}

function getPastDate(daysBack) {
  const timestamp = new Date();
  timestamp.setDate(timestamp.getDate() - daysBack);
  return formatDate(timestamp);
}

// Pass command line params
var net = typeof networks == "undefined" ? "^.*$" : `^${networks}$`;
var sta = typeof stations == "undefined" ? "^.*$" : `^${stations}$`;
var ts = typeof start == "undefined" ? getPastDate(1) : start;
var te = typeof end == "undefined" ? getPastDate(0) : end;

// If provided, `daysBack` overwrites `ts`
if (typeof daysBack !== "undefined") {
  ts = getPastDate(daysBack);
}

console.log(
  `Processing WFCatalog entries using networks: '${net}', stations: '${sta}', start: '${ts}', end: '${te}' started!`
);

updateAvailabilityDaily(net, sta, new ISODate(ts), new ISODate(te));
updateAvailabilityContinuous(net, sta, new ISODate(ts), new ISODate(te));

console.log(
  `Processing WFCatalog entries using networks: '${net}', stations: '${sta}', start: '${ts}', end: '${te}' completed!`
);
