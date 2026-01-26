
import unittest
import json
from datetime import datetime, timedelta
from apps import data_access_layer as dal
from apps.globals import START, END, UPDATED, COUNT, STATUS

class TestDataAccessLayer(unittest.TestCase):

    def setUp(self):
        self.base_params = {
            "format": "text",
            "merge": [],
            "showlastupdate": False,
            "extent": False,
            "quality": "*",
            "orderby": "nslc_time_quality_samplerate",
            "mergegaps": None
        }
        # Fake data row structure based on PROJ in wfcatalog_client
        # [net, sta, loc, cha, qlt, srate, ts, te, updated, restr, count]
        # But wait, collect_data returns what?
        # wfcatalog_client returns list of lists.
        # [net, sta, loc, cha, qlt, srate, ts, te, created, restr, count]
        # created -> updated
        self.now = datetime.utcnow()
        self.data_row = [
            "NL", "HGN", "02", "BHZ", "D", 40.0, 
            datetime(2022, 1, 1, 12, 0, 0), 
            datetime(2022, 1, 1, 13, 0, 0),
            self.now, "OPEN", 100
        ]

    def test_get_header_text(self):
        params = self.base_params.copy()
        header = dal.get_header(params)
        self.assertEqual(header[0], "#Network")
        self.assertIn("Quality", header)
        self.assertIn("SampleRate", header)
    
    def test_get_header_geocsv(self):
        params = self.base_params.copy()
        params["format"] = "geocsv"
        header_str = dal.get_geocsv_header(params)
        self.assertIn("#dataset: GeoCSV 2.0", header_str)
        self.assertIn("Network|Station", header_str)

    def test_records_to_text(self):
        params = self.base_params.copy()
        data = [self.data_row[:]] # Copy
        # dal.select_columns expects data to be formatted strings strings mostly? 
        # No, select_columns does the formatting. records_to_text expects pre-formatted data strings?
        # Let's check logic: records_to_text calls get_column_widths.
        # It assumes data is "Any", but usually it's stringified by select_columns first in get_output.
        # BUT records_to_text is called by get_response which is called AFTER select_columns.
        # So I should pass strings if I want to test records_to_text in isolation?
        # dal.records_to_text uses ljust which works on strings.
        
        # Let's stringify data first like select_columns does
        str_data = [[str(x) for x in self.data_row]]
        text = dal.records_to_text(params, str_data)
        self.assertIn("NL", text)
        self.assertIn("#Network", text)

    def test_records_to_text_empty_location(self):
        """Test that empty location code is converted to '--' in text format"""
        params = self.base_params.copy()
        # Row with empty location
        row = ["NL", "HGN", "", "BHZ", "D", 40.0, 
               datetime(2022, 1, 1, 12, 0, 0), 
               datetime(2022, 1, 1, 13, 0, 0),
               self.now, "OPEN", 100]
        str_data = [[str(x) for x in row]]
        
        text = dal.records_to_text(params, str_data)
        
        # Check that proper header is present
        self.assertIn("#Network", text)
        # Check that the empty location is represented as --
        # We look for the line. Since we don't know exact padding, checking that -- exists 
        # is good, but let's be more specific if possible.
        # The row usually prints like: NL HGN -- BHZ ...
        self.assertRegex(text, r"NL\s+HGN\s+--\s+BHZ")

    def test_records_to_dictlist(self):
        params = self.base_params.copy()
        params["format"] = "json"
        data = [self.data_row[:]]
        # records_to_dictlist handles raw logic or formatted?
        # dictlist maps zip(header, row).
        # It relies on the position.
        result = dal.records_to_dictlist(params, data)
        self.assertIn("datasources", result)
        ds = result["datasources"][0]
        self.assertEqual(ds["network"], "NL")
        self.assertEqual(ds["station"], "HGN")
        
    def test_fusion_logic(self):
        # Create two adjacent rows that should merge
        params = self.base_params.copy()
        params["mergegaps"] = 0.001
        
        t0 = datetime(2022, 1, 1, 12, 0, 0)
        t1 = t0 + timedelta(hours=1)
        t2 = t1 # Seamless
        t3 = t2 + timedelta(hours=1)
        
        # [net, sta, loc, cha, qlt, srate, ts, te, updated, restr, count]
        # Indexes used by fusion (get_indexes default): [0, 1, 2, 3, 4, 5] (incl SampleRate)
        indexes = [0, 1, 2, 3, 4, 5]
        
        row1 = ["NL", "HGN", "", "BHZ", "D", 40.0, t0, t1, self.now, "OPEN", 100]
        row2 = ["NL", "HGN", "", "BHZ", "D", 40.0, t2, t3, self.now, "OPEN", 100]
        
        data = [row1, row2]
        
        merged = dal.fusion(params, data, indexes)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0][START], t0)
        self.assertEqual(merged[0][END], t3)

if __name__ == "__main__":
    unittest.main()
