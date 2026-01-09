
import unittest
from datetime import datetime
from pydantic import ValidationError
from apps.models import QueryParameters
from apps.globals import STRING_TRUE, STRING_FALSE

class TestQueryParameters(unittest.TestCase):

    def test_default_values(self):
        """Test instantiation with defaults."""
        params = {}
        qp = QueryParameters(**params)
        # Defaults are "*" in models.py
        self.assertEqual(qp.network, "*")
        self.assertEqual(qp.station, "*")
        self.assertIsNone(qp.starttime) # start -> starttime

    def test_network_validation(self):
        """Test network code validation patterns."""
        valid_networks = ["NL", "G?", "*", "NL,DE"]
        for net in valid_networks:
             qp = QueryParameters(network=net)
             self.assertEqual(qp.network, net)

        invalid_networks = ["TooLong", "Invalid!Char"]
        for net in invalid_networks:
            with self.assertRaises(ValidationError):
                QueryParameters(network=net)
    
    def test_station_validation(self):
        """Test station code validation patterns."""
        valid_stations = ["HGN", "H?N", "*", "HGN,VKB"]
        for sta in valid_stations:
             qp = QueryParameters(station=sta)
             self.assertEqual(qp.station, sta)

        invalid_stations = ["TooLongStationName", "Invalid!"]
        for sta in invalid_stations:
            with self.assertRaises(ValidationError):
                QueryParameters(station=sta)

    def test_start_end_time_parsing(self):
        """Test date parsing logic."""
        # ISO8601
        qp = QueryParameters(start="2022-01-01T00:00:00") # Alias 'start'
        self.assertIsNotNone(qp.starttime)
        # Since validator might return string or datetime depending on implementation logic.
        # models.py says: 
        # try: datetime.strptime(...); return v
        # So it returns the STRING '2022-01-01T00:00:00' verified.
        self.assertEqual(qp.starttime, "2022-01-01T00:00:00")

        # Keyword
        qp = QueryParameters(start="currentutcday")
        self.assertEqual(qp.starttime, "currentutcday")

        # Invalid
        with self.assertRaises(ValidationError):
            QueryParameters(start="not-a-date")

    def test_boolean_conversion(self):
        """Test converting string booleans."""
        # 'extent' is NOT an alias in models.py, must use 'includerestricted'
        # root.py handles mapping manually, but here we test the model.
        # Boolean conversion for includesrestricted
        for val in STRING_TRUE:
            qp = QueryParameters(includerestricted=val)
            self.assertTrue(qp.includerestricted)
        
        for val in STRING_FALSE:
            qp = QueryParameters(includerestricted=val)
            self.assertFalse(qp.includerestricted)

if __name__ == "__main__":
    unittest.main()
