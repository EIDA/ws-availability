import unittest
from datetime import datetime
from unittest.mock import MagicMock, call

from apps.updater import AvailabilityUpdater


class TestAvailabilityUpdater(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.updater = AvailabilityUpdater(self.mock_db)

    def test_update_availability_daily_pipeline(self):
        """
        Test that update_availability_daily calls aggregate with the correct pipeline.
        """
        start_date = datetime(2023, 3, 23)
        end_date = datetime(2023, 3, 24)
        networks = "NL"
        stations = "HGN"

        self.updater.update_availability_daily(networks, stations, start_date, end_date)

        # Retrieve the pipeline that was passed to aggregate
        self.mock_db.daily_streams.aggregate.assert_called_once()
        pipeline = self.mock_db.daily_streams.aggregate.call_args[0][0]

        # Verify pipeline structure exactly matches what we expect from main.js
        expected_match = {
            "$match": {
                "net": {"$regex": networks},
                "sta": {"$regex": stations},
                "ts": {"$gte": start_date},
                "te": {"$lte": end_date},
                "avail": {"$gte": 100},
            }
        }
        self.assertEqual(pipeline[0], expected_match)

        expected_group = {
            "$group": {
                "_id": "$_id",
                "net": {"$first": "$net"},
                "sta": {"$first": "$sta"},
                "loc": {"$first": "$loc"},
                "cha": {"$first": "$cha"},
                "qlt": {"$first": "$qlt"},
                "srate": {"$first": {"$arrayElemAt": ["$srate", 0]}},
                "ts": {"$first": "$ts"},
                "te": {"$first": "$te"},
                "created": {"$first": "$created"},
                "restr": {"$first": "OPEN"},
                "count": {"$first": 1},
            }
        }
        self.assertEqual(pipeline[1], expected_group)

        expected_merge = {
            "$merge": {"into": "availability", "on": "_id", "whenMatched": "replace"}
        }
        self.assertEqual(pipeline[2], expected_merge)

    def test_update_availability_continuous_pipeline(self):
        """
        Test that update_availability_continuous calls aggregate with the correct pipeline.
        """
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 2, 1)
        networks = "^.*$"
        stations = "^.*$"

        self.updater.update_availability_continuous(networks, stations, start_date, end_date)

        # Retrieve the pipeline that was passed to aggregate
        self.mock_db.daily_streams.aggregate.assert_called_once()
        pipeline = self.mock_db.daily_streams.aggregate.call_args[0][0]

        expected_match = {
            "$match": {
                "net": {"$regex": networks},
                "sta": {"$regex": stations},
                "ts": {"$gte": start_date},
                "te": {"$lte": end_date},
                "avail": {"$lt": 100},
            }
        }
        self.assertEqual(pipeline[0], expected_match)

        expected_lookup = {
            "$lookup": {
                "from": "c_segments",
                "localField": "_id",
                "foreignField": "streamId",
                "as": "c_segments",
            }
        }
        self.assertEqual(pipeline[1], expected_lookup)

        expected_unwind = {"$unwind": "$c_segments"}
        self.assertEqual(pipeline[2], expected_unwind)

        expected_group = {
            "$group": {
                "_id": "$c_segments._id",
                "net": {"$first": "$net"},
                "sta": {"$first": "$sta"},
                "loc": {"$first": "$loc"},
                "cha": {"$first": "$cha"},
                "qlt": {"$first": "$qlt"},
                "srate": {"$first": "$c_segments.srate"},
                "ts": {"$first": "$c_segments.ts"},
                "te": {"$first": "$c_segments.te"},
                "created": {"$first": "$created"},
                "restr": {"$first": "OPEN"},
                "count": {"$first": 1},
            }
        }
        self.assertEqual(pipeline[3], expected_group)

        expected_merge = {
            "$merge": {"into": "availability", "on": "_id", "whenMatched": "replace"}
        }
        self.assertEqual(pipeline[4], expected_merge)


if __name__ == "__main__":
    unittest.main()
