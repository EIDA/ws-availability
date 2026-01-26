
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure we can import modules from parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# MOCK DEPENDENCIES
# We use patch in setUp/test methods instead of global sys.modules hacking
# to avoid breaking other tests that need real modules.


from apps import wfcatalog_client

class TestWFCatalogFiltering(unittest.TestCase):
    
    def setUp(self):
        # Setup mock inventory
        self.mock_inventory = MagicMock()
        self.mock_inventory._known_seedIDs = {"NET.STA.LOC.CHA"}
        self.mock_inventory._restricted_seedIDs = {"NET.STA.LOC.CHA"}
        
        # Patch the global RESTRICTED_INVENTORY in wfcatalog_client
        self.patcher = patch('apps.wfcatalog_client.RESTRICTED_INVENTORY', self.mock_inventory)
        self.mock_inv_global = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_open_data_default(self):
        """Test that OPEN data is returned by default (includerestricted=False)"""
        # Mock _get_restricted_status to return "OPEN"
        with patch('apps.wfcatalog_client._get_restricted_status', return_value="OPEN"):
            
            data = [{
                "net": "NET", "sta": "STA", "loc": "LOC", "cha": "CHA",
                "qlt": "D", "srate": 100, "ts": "2024-01-01", "te": "2024-01-02",
                "created": "now", "count": 100
            }]
            
            # Run function with default (includerestricted=False)
            results = wfcatalog_client._apply_restricted_bit(data, include_restricted=False)
            
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][9], "OPEN") # Check restriction status in result

    def test_restricted_data_default(self):
        """Test that RESTRICTED data is skipped by default"""
        with patch('apps.wfcatalog_client._get_restricted_status', return_value="RESTRICTED"):
            
            data = [{
                "net": "NET", "sta": "STA", "loc": "LOC", "cha": "CHA",
                "qlt": "D", "srate": 100, "ts": "2024-01-01", "te": "2024-01-02",
                "created": "now", "count": 100
            }]
            
            # Should be empty
            results = wfcatalog_client._apply_restricted_bit(data, include_restricted=False)
            
            self.assertEqual(len(results), 0)

    def test_partial_data_default(self):
        """Test that PARTIAL data is skipped by default"""
        with patch('apps.wfcatalog_client._get_restricted_status', return_value="PARTIAL"):
            
            data = [{
                "net": "NET", "sta": "STA", "loc": "LOC", "cha": "CHA",
                "qlt": "D", "srate": 100, "ts": "2024-01-01", "te": "2024-01-02",
                "created": "now", "count": 100
            }]
            
            # Should be empty
            results = wfcatalog_client._apply_restricted_bit(data, include_restricted=False)
            
            self.assertEqual(len(results), 0)

    def test_restricted_data_included(self):
        """Test that RESTRICTED data is included when requested"""
        with patch('apps.wfcatalog_client._get_restricted_status', return_value="RESTRICTED"):
            
            data = [{
                "net": "NET", "sta": "STA", "loc": "LOC", "cha": "CHA",
                "qlt": "D", "srate": 100, "ts": "2024-01-01", "te": "2024-01-02",
                "created": "now", "count": 100
            }]
            
            # Should NOT be empty
            results = wfcatalog_client._apply_restricted_bit(data, include_restricted=True)
            
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][9], "RESTRICTED")

    def test_empty_inventory_fail_open(self):
        """Test that if inventory is empty/missing, data is returned (fail-open)"""
        # Set inventory to not populated
        self.mock_inventory.is_populated = False
        
        data = [{
            "net": "NET", "sta": "STA", "loc": "LOC", "cha": "CHA",
            "qlt": "D", "srate": 100, "ts": "2024-01-01", "te": "2024-01-02",
            "created": "now", "count": 100
        }]
        
        # Even if data is technically unknown (since inventory is empty), it should pass
        results = wfcatalog_client._apply_restricted_bit(data, include_restricted=False)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "NET")

if __name__ == '__main__':
    unittest.main()
