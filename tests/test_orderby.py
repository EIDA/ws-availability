import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
import sys
import os

# Ensure we can import modules from parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps import data_access_layer
from apps import globals

class TestOrderBy(unittest.TestCase):
    
    def test_sort_nslc_time_quality_samplerate(self):
        """Test default sorting: Net, Sta, Loc, Cha, Time, Quality, SampleRate"""
        
        # Create data in mixed order
        # Indices: 0=Net, 1=Sta, 2=Loc, 3=Cha, 4=Qlt, 5=SR, 6=Start, 7=End, 8=Updated
        
        t1 = datetime(2023, 1, 1, 10, 0, 0)
        t2 = datetime(2023, 1, 1, 12, 0, 0)
        
        row1 = ["NL", "HGN", "02", "BHZ", "D", 100.0, t1, t2, datetime.now(), "OPEN", 100]
        row2 = ["NL", "HGN", "02", "BHZ", "D", 100.0, t2, t2+timedelta(hours=1), datetime.now(), "OPEN", 100]
        # Same NSLC, DIFFERENT Quality
        row3 = ["NL", "HGN", "02", "BHZ", "Q", 100.0, t1, t2, datetime.now(), "OPEN", 100]
        # Different Station
        row4 = ["NL", "ABC", "02", "BHZ", "D", 100.0, t1, t2, datetime.now(), "OPEN", 100]
        
        # Mixed up list
        data = [row3, row2, row4, row1]
        
        params = {
            "orderby": "nslc_time_quality_samplerate",
            "extent": False
        }
        
        # data_access_layer.sort_records ONLY runs if orderby != nslc_time_quality_samplerate
        # But wait, where is the default sort?
        # In mongo_request? Yes.
        # But fusion might break order?
        # Let's assume data comes from fusion.
        
        # If orderby IS nslc_time_quality_samplerate, sort_records is skipped.
        # So we expect data to be ALREADY sorted?
        # If fusion doesn't preserve strict order, or if mongo sort was insufficient?
        
        # Call sort_records directly
        # The function has a check: `if params["orderby"] != "nslc_time_quality_samplerate":`
        # So effectivey it DOES NOTHING for the default case.
        data_access_layer.sort_records(params, data)
        
        # Expectation: Data should be sorted by Net, Sta, Loc, Cha, Time, Quality, SampleRate
        # Current behavior: It skips sorting, so data remains [row3, row2, row4, row1]
        
        # If the bug exists, this assertion will FAIL (because data[0] is row3 but should be row4 or row1 depending on sort)
        # Expected sort order:
        # 1. row4 (ABC)
        # 2. row1 (HGN, t1, D)
        # 3. row2 (HGN, t2, D)
        # 4. row3 (HGN, t1, Q) -> Wait, Q > D? Or D < Q? Lexicographical. D < Q.
        
        # Wait, comparison:
        # row1: HGN, t1, D
        # row3: HGN, t1, Q
        # tuple comparison: (..., 'D', ...) < (..., 'Q', ...)
        # So row1 comes before row3.
        
        # Correct sorted order:
        # 1. row4 (ABC - Station 'A' comes before 'H')
        # 2. row1 (HGN, t1, D)
        # 3. row3 (HGN, t1, Q) (Same time as row1, but Q > D)
        # 4. row2 (HGN, t2, D) (Later time)
        
        expected = [row4, row1, row3, row2]
        
        # Use assertEqual to verify complete list order
        self.assertEqual(data, expected, "Data was not sorted correctly by nslc_time_quality_samplerate")

    def test_sort_latestupdate(self):
        """Test sorting by latest update"""
        t = datetime.now()
        row1 = ["A", "B", "", "C", "D", 1.0, t, t, t - timedelta(hours=2), "O", 1] # Oldest
        row2 = ["A", "B", "", "C", "D", 1.0, t, t, t - timedelta(hours=1), "O", 1] # Newer
        row3 = ["A", "B", "", "C", "D", 1.0, t, t, t, "O", 1]                   # Newest
        
        data = [row1, row3, row2]
        params = {"orderby": "latestupdate", "extent": False}
        
        data_access_layer.sort_records(params, data)
        
        self.assertEqual(data[0], row1)
        self.assertEqual(data[1], row2)
        self.assertEqual(data[2], row3)
        
    def test_sort_latestupdate_desc(self):
        """Test sorting by latest update desc"""
        t = datetime.now()
        row1 = ["A", "B", "", "C", "D", 1.0, t, t, t - timedelta(hours=2), "O", 1]
        row2 = ["A", "B", "", "C", "D", 1.0, t, t, t - timedelta(hours=1), "O", 1]
        row3 = ["A", "B", "", "C", "D", 1.0, t, t, t, "O", 1]
        
        data = [row1, row3, row2]
        params = {"orderby": "latestupdate_desc", "extent": False}
        
        data_access_layer.sort_records(params, data)
        
        self.assertEqual(data[0], row3)
        self.assertEqual(data[1], row2)
        self.assertEqual(data[2], row1)

if __name__ == '__main__':
    unittest.main()
