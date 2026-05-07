import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure apps is in the path
sys.path.append(os.getcwd())

from apps.wfcatalog_client import _expand_wildcards, mongo_request
from apps.settings import settings
from apps.globals import Error

class TestIssue60Protection(unittest.TestCase):
    
    @patch("apps.wfcatalog_client.RESTRICTED_INVENTORY")
    def test_max_streams_limit(self, mock_inv):
        """Test Rule A: Hard limit on number of streams (MAX_STREAMS)"""
        # Setup mock inventory with 2500 streams
        # _expand_wildcards uses RESTRICTED_INVENTORY._inv to filter
        # but wait, let's look at _expand_wildcards implementation again
        
        # for net in params["network"].split(","):
        #     _net += [e for e in RESTRICTED_INVENTORY._inv if fnmatch(e.split(".")[0], net)]
        
        mock_inv._inv = [f"NET.STA.00.CH{i}" for i in range(2500)]
        
        params = {
            "network": "NET",
            "station": "*",
            "location": "*",
            "channel": "*",
            "start": None,
            "end": None
        }
        
        # This should raise ValueError due to stream count (2500 > 2000)
        with self.assertRaises(ValueError) as cm:
            _expand_wildcards(params)
        
        self.assertEqual(str(cm.exception), Error.TOO_MANY_STREAMS)

    @patch("apps.wfcatalog_client.RESTRICTED_INVENTORY")
    def test_broad_query_limit(self, mock_inv):
        """Test Rule B: Broad query rejection (many streams + no time range)"""
        # Setup mock inventory with 600 streams
        mock_inv._inv = [f"NET.STA.00.CH{i}" for i in range(600)]
        
        params = {
            "network": "NET",
            "station": "*",
            "location": "*",
            "channel": "*",
            "start": None,
            "end": None
        }
        
        # This should raise ValueError because 600 > 500 AND no time range
        with self.assertRaises(ValueError) as cm:
            _expand_wildcards(params)
        
        self.assertEqual(str(cm.exception), Error.BROAD_QUERY)

        # Now add a time range - it should PASS the breadth check
        params["start"] = "2024-01-01"
        params["end"] = "2024-01-02"
        
        # This should NOT raise ValueError from breadth check
        try:
            _expand_wildcards(params)
        except ValueError as e:
            if str(e) == Error.BROAD_QUERY:
                self.fail("Broad query check fired even with time range")

    @patch("apps.wfcatalog_client.get_db_client")
    def test_mongodb_cursor_limit(self, mock_get_db):
        """Test Layer 4: MongoDB cursor .limit() is applied"""
        mock_db = MagicMock()
        mock_get_db.return_value.get_database.return_value = mock_db
        
        # Mock _expand_wildcards to avoid Redis dependency
        with patch("apps.wfcatalog_client._expand_wildcards") as mock_expand:
            mock_expand.return_value = {
                "network": "NET", "station": "STA", "location": "*", "channel": "*",
                "quality": "*", "start": None, "end": None
            }
            
            # Mock _apply_restricted_bit to return empty list
            with patch("apps.wfcatalog_client._apply_restricted_bit", return_value=[]):
                
                mongo_request([{"network": "NET"}])
                
                # Check if .limit() was called with settings.max_data_rows + 1
                mock_db.availability.find.return_value.limit.assert_called_with(settings.max_data_rows + 1)

if __name__ == "__main__":
    unittest.main()
