import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from datetime import datetime

# Ensure we can import modules from parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps import wfcatalog_client

from flask import Flask

class TestDataAccess(unittest.TestCase):
    
    def setUp(self):
        # Create a dummy app and push context
        self.app = Flask(__name__)
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Patch configuration on the app itself (cleaner than patching current_app directly)
        self.app.config.update({
            "MONGODB_HOST": "localhost",
            "MONGODB_PORT": 27017,
            "MONGODB_USR": "user",
            "MONGODB_PWD": "pwd",
            "MONGODB_NAME": "testdb"
        })
        
        # Reset the global DB_CLIENT to ensure fresh start
        wfcatalog_client.DB_CLIENT = None
        # Patch MongoClient
        self.mongo_patcher = patch('apps.wfcatalog_client.MongoClient')
        self.mock_mongo_cls = self.mongo_patcher.start()
        
        # Setup the mock DB chain
        self.mock_client_instance = self.mock_mongo_cls.return_value
        self.mock_db = self.mock_client_instance.get_database.return_value
        self.mock_collection = self.mock_db.availability
        
        # Patch filtering
        self.filter_patcher = patch('apps.wfcatalog_client._apply_restricted_bit')
        self.mock_apply_restricted = self.filter_patcher.start()

    def tearDown(self):
        # Reset the global to None so it doesn't leak to other tests
        wfcatalog_client.DB_CLIENT = None
        self.mongo_patcher.stop()
        self.filter_patcher.stop()
        self.app_context.pop()
        
        # Reset global DB_CLIENT again to be clean
        wfcatalog_client.DB_CLIENT = None

    def test_mongo_request_query_construction(self):
        """Test that mongo_request builds correct MongoDB queries from params"""
        
        # Arrange
        params = [{
            "network": "NL",
            "station": "HGN",
            "location": "--",
            "channel": "BHZ",
            "quality": "D",
            "start": datetime(2023, 1, 1),
            "end": datetime(2023, 1, 2)
        }]
        
        # Mock wildcard expansion to return params as-is for simplicity
        with patch('apps.wfcatalog_client._expand_wildcards', side_effect=lambda x: x):
            # Mock return values
            self.mock_collection.find.return_value = ["fake_cursor"]
            self.mock_apply_restricted.return_value = ["fake_result"]
            
            # Act
            queries, results = wfcatalog_client.mongo_request(params)
            
            # Assert
            self.assertEqual(len(queries), 1)
            qry = queries[0]
            
            # Verify query structure
            self.assertEqual(qry["net"], {"$in": ["NL"]})
            self.assertEqual(qry["sta"], {"$in": ["HGN"]})
            self.assertIn("ts", qry)
            self.assertIn("te", qry)
            
            # Verify Mongo interaction
            self.mock_collection.find.assert_called()

    def test_mongo_request_multiple_params(self):
        """Test that multiple parameter sets trigger multiple queries"""
         # Arrange
        params = [
            {
                "network": "NL", "station": "*", "location": "*", "channel": "*", "quality": "D",
                "start": None, "end": None
            },
            {
                "network": "BE", "station": "*", "location": "*", "channel": "*", "quality": "D",
                "start": None, "end": None
            }
        ]
        
        with patch('apps.wfcatalog_client._expand_wildcards', side_effect=lambda x: x):
             # Act
            queries, results = wfcatalog_client.mongo_request(params)
            
            # Assert
            # Should have created 2 queries
            self.assertEqual(len(queries), 2)
            # Should have called find 2 times
            self.assertEqual(self.mock_collection.find.call_count, 2)
            
            # NEW IMPLEMENTATION CHECK:
            # We expect MongoClient to be initialized ONLY ONCE, reusing the connection.
            self.assertEqual(self.mock_mongo_cls.call_count, 1)

if __name__ == '__main__':
    unittest.main()
