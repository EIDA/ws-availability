"""
Test for Issue #48: Query with starttime but no endtime returns no results.

This regression was introduced in the fix for Issue #23. When endtime is None,
the MongoDB query was incorrectly constructing {"ts": {"$lt": None}}, which
matches no documents.
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add parent directory to path to import apps
sys.path.insert(0, str(Path(__file__).parent.parent))

from apps import wfcatalog_client


class TestQueryNoEndtime(unittest.TestCase):
    """Test that queries work correctly when endtime is not specified."""

    @patch('apps.wfcatalog_client.get_db_client')
    @patch('apps.wfcatalog_client.RESTRICTED_INVENTORY')
    def test_query_with_starttime_only(self, mock_inventory, mock_get_db_client):
        """
        Test that a query with only starttime (no endtime) constructs a valid MongoDB query.
        
        The query should only include {"te": {"$gt": start}} and NOT include
        {"ts": {"$lt": None}}.
        """
        # Setup mock database
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_cursor = MagicMock()
        
        mock_get_db_client.return_value = mock_client
        mock_client.get_database.return_value = mock_db
        mock_db.availability = mock_collection
        mock_collection.find.return_value = mock_cursor
        mock_cursor.__iter__.return_value = iter([])
        
        # Setup mock inventory
        mock_inventory._inv = ["HL.ATH.00.HHZ"]
        mock_inventory._known_seedIDs = ["HL.ATH.00.HHZ"]
        mock_inventory._restricted_seedIDs = []
        
        # Create params with starttime but no endtime
        params = {
            "network": "HL",
            "station": "ATH",
            "location": "*",
            "channel": "*",
            "quality": "*",
            "start": datetime(2025, 12, 1),
            "end": None,  # No endtime specified
            "includerestricted": False
        }
        
        # Execute query
        queries, results = wfcatalog_client.mongo_request([params])
        
        # Verify the MongoDB query was constructed correctly
        self.assertEqual(len(queries), 1)
        query = queries[0]
        
        # Should have te constraint
        self.assertIn("te", query)
        self.assertEqual(query["te"], {"$gt": datetime(2025, 12, 1, 0, 0, 0)})
        
        # Should NOT have ts constraint (because end is None)
        self.assertNotIn("ts", query)
        
        # Verify find was called with the correct query
        mock_collection.find.assert_called_once()
        actual_query = mock_collection.find.call_args[0][0]
        
        # The actual query should NOT contain {"ts": {"$lt": None}}
        if "ts" in actual_query:
            self.assertIsNotNone(actual_query["ts"].get("$lt"))


if __name__ == "__main__":
    unittest.main()
