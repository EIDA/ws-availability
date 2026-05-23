import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from datetime import datetime
from datetime import timedelta

# Ensure we can import modules from parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps import wfcatalog_client
from flask import Flask

class TestWFCatalogQuery(unittest.TestCase):
    
    def setUp(self):
        # Create a dummy app and push context
        self.app = Flask(__name__)
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Patch configuration
        self.app.config.update({
            "MONGODB_HOST": "localhost",
            "MONGODB_PORT": 27017,
            "MONGODB_USR": "user",
            "MONGODB_PWD": "pwd",
            "MONGODB_NAME": "testdb"
        })
        
        # Reset global DB_CLIENT
        wfcatalog_client.DB_CLIENT = None

        # Patch MongoClient
        self.mongo_patcher = patch('apps.wfcatalog_client.MongoClient')
        self.mock_mongo_cls = self.mongo_patcher.start()
        self.mock_db = self.mock_mongo_cls.return_value.get_database.return_value
        self.mock_collection = self.mock_db.availability
        
        # Patch filtering - NOTICE: we are NOT mocking apply_restricted because we want to test its logic
        # But apply_restricted uses RestrictionInventory which connects to Redis...
        # So we MUST mock RestrictionInventory
        self.ri_patcher = patch('apps.wfcatalog_client.RestrictionInventory')
        self.mock_ri_cls = self.ri_patcher.start()
        self.mock_ri = self.mock_ri_cls.return_value
        # Mock _known_seedIDs to allow all our test SIDs
        self.mock_ri._known_seedIDs = [] # If not in known, it skips? No, see code
        
        # Checking logic in _apply_restricted_bit
        # if sid not in RESTRICTED_INVENTORY._known_seedIDs: continue
        # SO we need to populate this
        wfcatalog_client.RESTRICTED_INVENTORY = self.mock_ri
        
        # Helper to setup known SIDs
        self.mock_ri._known_seedIDs = ["NL.HGN.--.BHZ", "NL.HGN.02.BHZ"]
        self.mock_ri._restricted_seedIDs = []

    def _set_find_results(self, results_or_fn):
        """Stub `collection.find(...).limit(...)` to return the given iterable.

        Accepts either a list (same iterable for every call) or a callable
        ``fn(query) -> iterable`` for per-query results.
        """
        if callable(results_or_fn):
            def _find_side_effect(qry, projection=None):
                cursor = MagicMock()
                cursor.limit.return_value = iter(results_or_fn(qry))
                return cursor
            self.mock_collection.find.side_effect = _find_side_effect
        else:
            cursor = MagicMock()
            cursor.limit.return_value = iter(results_or_fn)
            self.mock_collection.find.return_value = cursor

    def tearDown(self):
        self.mongo_patcher.stop()
        self.ri_patcher.stop()
        self.app_context.pop()
        wfcatalog_client.DB_CLIENT = None
        wfcatalog_client.RESTRICTED_INVENTORY = None

    def test_query_logic_overlap(self):
        """test that query uses $gt and $lt for overlap instead of containment"""
        params = [{
            "network": "NL", "station": "HGN", "location": "--", "channel": "BHZ", "quality": "D",
            "start": datetime(2023, 1, 10),
            "end": datetime(2023, 1, 20)
        }]
        
        with patch('apps.wfcatalog_client._expand_wildcards', side_effect=lambda x: x):
            self._set_find_results([])
            wfcatalog_client.mongo_request(params)

            # Get the query passed to find
            call_args = self.mock_collection.find.call_args
            qry = call_args[0][0]
            
            # Current logic (containment) uses $gte and $lte
            # New logic (overlap) should use $lt (start < end) and $gt (end > start)
            
            # Implementation combines both into one block if start is not None
            # And it uses `end` and `start` from params directly (impl uses cropped dates but here mocked expand)
            
            # The implementation calls `crop_datetimes`, which:
            # 1. Rounds start to beginning of day
            # 2. Rounds end to beginning of day AND adds 1 day
            
            # So if end input is 2023-01-20, cropped end is 2023-01-21 00:00:00
            expected_end = params[0]["end"].replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            
            self.assertEqual(qry["ts"], {"$lt": expected_end})
            self.assertEqual(qry["te"], {"$gt": params[0]["start"]})

    def test_fanout_disabled_runs_single_query(self):
        """With FANOUT_ENABLED=False, mongo_request issues exactly one find() per params entry."""
        params = [{
            "network": "NL", "station": "HGN", "location": "--", "channel": "BHZ", "quality": "D",
            "start": datetime(2024, 1, 1),
            "end": datetime(2024, 4, 1),  # 91 days — would trigger fan-out if on
        }]

        with patch.object(wfcatalog_client.settings, "fanout_enabled", False), \
             patch('apps.wfcatalog_client._expand_wildcards', side_effect=lambda x: x):
            self._set_find_results([])
            wfcatalog_client.mongo_request(params)

            self.assertEqual(self.mock_collection.find.call_count, 1)

    def test_fanout_enabled_splits_into_non_overlapping_shards(self):
        """With FANOUT_ENABLED=True and a wide range, shards cover [start,end) without overlap."""
        params = [{
            "network": "NL", "station": "HGN", "location": "--", "channel": "BHZ", "quality": "D",
            "start": datetime(2024, 1, 1),
            "end": datetime(2024, 4, 1),  # 91 days
        }]

        with patch.object(wfcatalog_client.settings, "fanout_enabled", True), \
             patch.object(wfcatalog_client.settings, "fanout_min_days", 7), \
             patch.object(wfcatalog_client.settings, "fanout_window_days", 30), \
             patch.object(wfcatalog_client.settings, "fanout_max_workers", 4), \
             patch('apps.wfcatalog_client._expand_wildcards', side_effect=lambda x: x):
            self._set_find_results([])
            wfcatalog_client.mongo_request(params)

            # crop_datetimes pushes end to start-of-next-day, so range is 92 days -> 4 shards of <=30d.
            self.assertEqual(self.mock_collection.find.call_count, 4)

            shard_bounds = []
            for call in self.mock_collection.find.call_args_list:
                qry = call[0][0]
                shard_bounds.append((qry["te"]["$gt"], qry["ts"]["$lt"]))

            # Shards are contiguous and non-overlapping when sorted by start.
            shard_bounds.sort()
            for (a_start, a_end), (b_start, b_end) in zip(shard_bounds, shard_bounds[1:]):
                self.assertEqual(a_end, b_start, "shards must tile [start, end) without gaps or overlap")
            self.assertEqual(shard_bounds[0][0], datetime(2024, 1, 1))
            self.assertEqual(shard_bounds[-1][1], datetime(2024, 4, 2))  # crop_datetimes(+1 day)

    def test_fanout_result_equals_single_shot(self):
        """Merged fan-out result must equal the single-shot result for the same query."""
        seg = lambda ts, te: {
            "net": "NL", "sta": "HGN", "loc": "--", "cha": "BHZ", "qlt": "D", "srate": 100.0,
            "ts": ts, "te": te,
            "created": datetime(2024, 5, 1), "count": 10, "restr": "OPEN",
        }
        # Three docs that fall in different 30-day windows.
        all_docs = [
            seg(datetime(2024, 1, 5), datetime(2024, 1, 6)),
            seg(datetime(2024, 2, 10), datetime(2024, 2, 11)),
            seg(datetime(2024, 3, 20), datetime(2024, 3, 21)),
        ]

        def find_by_range(qry, projection=None):
            ts_lt = qry["ts"]["$lt"]
            te_gt = qry["te"]["$gt"]
            return [d for d in all_docs if d["ts"] < ts_lt and d["te"] > te_gt]

        params = [{
            "network": "NL", "station": "HGN", "location": "--", "channel": "BHZ", "quality": "D",
            "start": datetime(2024, 1, 1),
            "end": datetime(2024, 4, 1),
        }]

        # Single-shot reference
        with patch.object(wfcatalog_client.settings, "fanout_enabled", False), \
             patch('apps.wfcatalog_client._expand_wildcards', side_effect=lambda x: x):
            self._set_find_results(find_by_range)
            _, single_result = wfcatalog_client.mongo_request(params)

        # Reset mock for the fan-out path.
        self.mock_collection.find.reset_mock()
        self._set_find_results(find_by_range)

        with patch.object(wfcatalog_client.settings, "fanout_enabled", True), \
             patch.object(wfcatalog_client.settings, "fanout_min_days", 7), \
             patch.object(wfcatalog_client.settings, "fanout_window_days", 30), \
             patch.object(wfcatalog_client.settings, "fanout_max_workers", 4), \
             patch('apps.wfcatalog_client._expand_wildcards', side_effect=lambda x: x):
            _, fanout_result = wfcatalog_client.mongo_request(params)

        self.assertEqual(single_result, fanout_result)

    def test_filter_invalid_data(self):
        """test that segments with start > end are filtered out"""
        
        # Invalid segment: Start > End
        invalid_segment = {
            "net": "NL", "sta": "HGN", "loc": "--", "cha": "BHZ", "qlt": "D", "srate": 100.0,
            "ts": datetime(2023, 1, 23, 5, 0), # 05:00
            "te": datetime(2023, 1, 23, 0, 0), # 00:00 (Before start!)
            "created": datetime.now(), "count": 100, "restr": "OPEN"
        }
        
        # Valid segment
        valid_segment = {
            "net": "NL", "sta": "HGN", "loc": "--", "cha": "BHZ", "qlt": "D", "srate": 100.0,
            "ts": datetime(2023, 1, 20, 0, 0),
            "te": datetime(2023, 1, 21, 0, 0),
            "created": datetime.now(), "count": 100, "restr": "OPEN"
        }
        
        params = [{
            "network": "NL", "station": "HGN", "location": "--", "channel": "BHZ", "quality": "D",
            "start": datetime(2023, 1, 1),
            "end": datetime(2023, 2, 1)
        }]
        
        with patch('apps.wfcatalog_client._expand_wildcards', side_effect=lambda x: x):
            # Return both segments
            self._set_find_results([invalid_segment, valid_segment])

            # Act
            queries, results = wfcatalog_client.mongo_request(params)
            
            # Assert
            # Only valid_segment should remain
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][6], valid_segment["ts"]) # Index 6 is start time

if __name__ == '__main__':
    unittest.main()
