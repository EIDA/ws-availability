use("wfrepo");

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

updateAvailabilityContinuous = function (startDate) {
  db.daily_streams.aggregate([
    {
      $match: {
        ts: { $gte: startDate },
        avail: { $lt: 100 },
        slen: { $gte: 60 },
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
    { $merge: { into: "availability", on: "_id", whenMatched: "replace" } },
  ]);
};

const startTimestamp = new Date();
startTimestamp.setDate(startTimestamp.getDate() - daysBack);

function padTo2Digits(num) {
  return num.toString().padStart(2, "0");
}

function formatDate(date) {
  return [
    date.getFullYear(),
    padTo2Digits(date.getMonth() + 1),
    padTo2Digits(date.getDate()),
  ].join("-");
}

const startDate = formatDate(startTimestamp);

console.log(process.env["PWD"]);
console.log("Processing WFCatalog entries from", startDate);

updateAvailabilityDaily(new ISODate(startDate));
updateAvailabilityContinuous(new ISODate(startDate));

console.log("Processing WFCatalog entries from", startDate, "completed!");
