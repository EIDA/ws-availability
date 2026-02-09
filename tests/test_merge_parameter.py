"""
Tests for merge parameter functionality.

This module tests all merge options:
- merge=overlap: Merges overlapping time segments
- merge=quality: Merges segments with different quality codes
- merge=samplerate: Merges segments with different sample rates
- Combinations of merge options
"""

import unittest
from datetime import datetime, timedelta
from apps import data_access_layer as dal
from apps.globals import START, END, UPDATED, COUNT, STATUS, QUALITY, SAMPLERATE


class TestMergeParameter(unittest.TestCase):
    """Test suite for merge parameter functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.base_params = {
            "format": "text",
            "merge": [],
            "showlastupdate": False,
            "extent": False,
            "quality": "*",
            "orderby": "nslc_time_quality_samplerate",
            "mergegaps": None,
            "start": None,
            "end": None
        }
        self.now = datetime.utcnow()

    def test_merge_overlap_basic(self):
        """Test that merge=overlap merges overlapping time segments."""
        params = self.base_params.copy()
        params["merge"] = ["overlap"]
        
        # Create overlapping segments
        # Segment 1: 12:00 - 14:00
        # Segment 2: 13:00 - 15:00 (overlaps with segment 1)
        t0 = datetime(2022, 1, 1, 12, 0, 0)
        t1 = datetime(2022, 1, 1, 14, 0, 0)
        t2 = datetime(2022, 1, 1, 13, 0, 0)  # Overlaps
        t3 = datetime(2022, 1, 1, 15, 0, 0)
        
        # [net, sta, loc, cha, qlt, srate, ts, te, updated, restr, count]
        row1 = ["NL", "HGN", "02", "BHZ", "D", 40.0, t0, t1, self.now, "OPEN", 1]
        row2 = ["NL", "HGN", "02", "BHZ", "D", 40.0, t2, t3, self.now, "OPEN", 1]
        
        data = [row1, row2]
        
        # When merge=overlap, indexes should NOT include quality and samplerate
        # because we're merging across those dimensions
        indexes = dal.get_indexes(params)
        
        merged = dal.fusion(params, data, indexes)
        
        # Should merge into one segment spanning t0 to t3
        self.assertEqual(len(merged), 1, "Overlapping segments should merge into one")
        self.assertEqual(merged[0][START], t0, "Start time should be earliest")
        self.assertEqual(merged[0][END], t3, "End time should be latest")

    def test_merge_overlap_non_overlapping(self):
        """Test that non-overlapping segments are NOT merged with merge=overlap."""
        params = self.base_params.copy()
        params["merge"] = ["overlap"]
        
        # Create non-overlapping segments with a gap
        # Segment 1: 12:00 - 13:00
        # Segment 2: 14:00 - 15:00 (1 hour gap)
        t0 = datetime(2022, 1, 1, 12, 0, 0)
        t1 = datetime(2022, 1, 1, 13, 0, 0)
        t2 = datetime(2022, 1, 1, 14, 0, 0)
        t3 = datetime(2022, 1, 1, 15, 0, 0)
        
        row1 = ["NL", "HGN", "02", "BHZ", "D", 40.0, t0, t1, self.now, "OPEN", 1]
        row2 = ["NL", "HGN", "02", "BHZ", "D", 40.0, t2, t3, self.now, "OPEN", 1]
        
        data = [row1, row2]
        indexes = dal.get_indexes(params)
        
        merged = dal.fusion(params, data, indexes)
        
        # Should remain as two separate segments
        self.assertEqual(len(merged), 2, "Non-overlapping segments should not merge")

    def test_merge_quality(self):
        """Test that merge=quality merges segments with different quality codes."""
        params = self.base_params.copy()
        params["merge"] = ["quality"]
        
        # Create adjacent segments with different quality codes
        t0 = datetime(2022, 1, 1, 12, 0, 0)
        t1 = datetime(2022, 1, 1, 13, 0, 0)
        t2 = t1  # Adjacent
        t3 = datetime(2022, 1, 1, 14, 0, 0)
        
        # Same NSLC but different quality: D vs M
        row1 = ["NL", "HGN", "02", "BHZ", "D", 40.0, t0, t1, self.now, "OPEN", 1]
        row2 = ["NL", "HGN", "02", "BHZ", "M", 40.0, t2, t3, self.now, "OPEN", 1]
        
        data = [row1, row2]
        
        # When merge=quality, indexes should NOT include quality column
        indexes = dal.get_indexes(params)
        self.assertNotIn(QUALITY, indexes, "Quality should not be in indexes when merge=quality")
        
        merged = dal.fusion(params, data, indexes)
        
        # Should merge into one segment
        self.assertEqual(len(merged), 1, "Segments with different quality should merge")
        self.assertEqual(merged[0][START], t0)
        self.assertEqual(merged[0][END], t3)

    def test_merge_samplerate(self):
        """Test that merge=samplerate merges segments with different sample rates."""
        params = self.base_params.copy()
        params["merge"] = ["samplerate"]
        
        # Create adjacent segments with different sample rates
        t0 = datetime(2022, 1, 1, 12, 0, 0)
        t1 = datetime(2022, 1, 1, 13, 0, 0)
        t2 = t1  # Adjacent
        t3 = datetime(2022, 1, 1, 14, 0, 0)
        
        # Same NSLC and quality but different sample rate: 40.0 vs 20.0
        row1 = ["NL", "HGN", "02", "BHZ", "D", 40.0, t0, t1, self.now, "OPEN", 1]
        row2 = ["NL", "HGN", "02", "BHZ", "D", 20.0, t2, t3, self.now, "OPEN", 1]
        
        data = [row1, row2]
        
        # When merge=samplerate, indexes should NOT include samplerate column
        indexes = dal.get_indexes(params)
        self.assertNotIn(SAMPLERATE, indexes, "SampleRate should not be in indexes when merge=samplerate")
        
        merged = dal.fusion(params, data, indexes)
        
        # Should merge into one segment
        self.assertEqual(len(merged), 1, "Segments with different sample rates should merge")
        self.assertEqual(merged[0][START], t0)
        self.assertEqual(merged[0][END], t3)

    def test_merge_quality_and_samplerate(self):
        """Test that merge=quality,samplerate merges segments with different quality AND sample rates."""
        params = self.base_params.copy()
        params["merge"] = ["quality", "samplerate"]
        
        # Create adjacent segments with different quality AND sample rate
        t0 = datetime(2022, 1, 1, 12, 0, 0)
        t1 = datetime(2022, 1, 1, 13, 0, 0)
        t2 = t1  # Adjacent
        t3 = datetime(2022, 1, 1, 14, 0, 0)
        
        row1 = ["NL", "HGN", "02", "BHZ", "D", 40.0, t0, t1, self.now, "OPEN", 1]
        row2 = ["NL", "HGN", "02", "BHZ", "M", 20.0, t2, t3, self.now, "OPEN", 1]
        
        data = [row1, row2]
        
        # When merge=quality,samplerate, indexes should include only NSLC
        indexes = dal.get_indexes(params)
        self.assertEqual(indexes, [0, 1, 2, 3], "Should only have NSLC indexes")
        
        merged = dal.fusion(params, data, indexes)
        
        # Should merge into one segment
        self.assertEqual(len(merged), 1, "Segments with different quality and sample rate should merge")
        self.assertEqual(merged[0][START], t0)
        self.assertEqual(merged[0][END], t3)

    def test_merge_with_mergegaps(self):
        """Test that merge works correctly with mergegaps parameter."""
        params = self.base_params.copy()
        params["merge"] = ["overlap"]
        params["mergegaps"] = 3600.0  # 1 hour tolerance
        
        # Create segments with a small gap (30 minutes)
        t0 = datetime(2022, 1, 1, 12, 0, 0)
        t1 = datetime(2022, 1, 1, 13, 0, 0)
        t2 = datetime(2022, 1, 1, 13, 30, 0)  # 30 min gap
        t3 = datetime(2022, 1, 1, 14, 30, 0)
        
        row1 = ["NL", "HGN", "02", "BHZ", "D", 40.0, t0, t1, self.now, "OPEN", 1]
        row2 = ["NL", "HGN", "02", "BHZ", "D", 40.0, t2, t3, self.now, "OPEN", 1]
        
        data = [row1, row2]
        indexes = dal.get_indexes(params)
        
        merged = dal.fusion(params, data, indexes)
        
        # Should merge because gap is within tolerance
        self.assertEqual(len(merged), 1, "Segments within mergegaps tolerance should merge")
        self.assertEqual(merged[0][START], t0)
        self.assertEqual(merged[0][END], t3)

    def test_no_merge_different_channel(self):
        """Test that segments with different channels are NOT merged."""
        params = self.base_params.copy()
        params["merge"] = ["quality", "samplerate"]
        
        # Create adjacent segments with different channels
        t0 = datetime(2022, 1, 1, 12, 0, 0)
        t1 = datetime(2022, 1, 1, 13, 0, 0)
        t2 = t1
        t3 = datetime(2022, 1, 1, 14, 0, 0)
        
        # Different channel: BHZ vs BHN
        row1 = ["NL", "HGN", "02", "BHZ", "D", 40.0, t0, t1, self.now, "OPEN", 1]
        row2 = ["NL", "HGN", "02", "BHN", "D", 40.0, t2, t3, self.now, "OPEN", 1]
        
        data = [row1, row2]
        indexes = dal.get_indexes(params)
        
        merged = dal.fusion(params, data, indexes)
        
        # Should NOT merge because channels are different
        self.assertEqual(len(merged), 2, "Segments with different channels should not merge")

    def test_get_indexes_no_merge(self):
        """Test get_indexes returns all indexes when merge is empty."""
        params = self.base_params.copy()
        params["merge"] = []
        
        indexes = dal.get_indexes(params)
        
        # Should include all: net, sta, loc, cha, quality, samplerate
        self.assertEqual(indexes, [0, 1, 2, 3, 4, 5])

    def test_get_indexes_merge_quality(self):
        """Test get_indexes excludes quality when merge=quality."""
        params = self.base_params.copy()
        params["merge"] = ["quality"]
        
        indexes = dal.get_indexes(params)
        
        # Should exclude quality (index 4)
        self.assertEqual(indexes, [0, 1, 2, 3, 5])

    def test_get_indexes_merge_samplerate(self):
        """Test get_indexes excludes samplerate when merge=samplerate."""
        params = self.base_params.copy()
        params["merge"] = ["samplerate"]
        
        indexes = dal.get_indexes(params)
        
        # Should exclude samplerate (index 5)
        self.assertEqual(indexes, [0, 1, 2, 3, 4])

    def test_get_indexes_merge_both(self):
        """Test get_indexes excludes both quality and samplerate when merge=quality,samplerate."""
        params = self.base_params.copy()
        params["merge"] = ["quality", "samplerate"]
        
        indexes = dal.get_indexes(params)
        
        # Should exclude both quality and samplerate
        self.assertEqual(indexes, [0, 1, 2, 3])

    def test_get_header_with_merge_quality(self):
        """Test that header excludes Quality column when merge=quality."""
        params = self.base_params.copy()
        params["merge"] = ["quality"]
        
        header = dal.get_header(params)
        
        self.assertNotIn("Quality", header, "Quality should not be in header when merge=quality")
        self.assertIn("SampleRate", header, "SampleRate should be in header")

    def test_get_header_with_merge_samplerate(self):
        """Test that header excludes SampleRate column when merge=samplerate."""
        params = self.base_params.copy()
        params["merge"] = ["samplerate"]
        
        header = dal.get_header(params)
        
        self.assertIn("Quality", header, "Quality should be in header")
        self.assertNotIn("SampleRate", header, "SampleRate should not be in header when merge=samplerate")

    def test_get_header_with_merge_both(self):
        """Test that header excludes both Quality and SampleRate when merge=quality,samplerate."""
        params = self.base_params.copy()
        params["merge"] = ["quality", "samplerate"]
        
        header = dal.get_header(params)
        
        self.assertNotIn("Quality", header, "Quality should not be in header")
        self.assertNotIn("SampleRate", header, "SampleRate should not be in header")
        # Note: text format adds # prefix to Network
        self.assertTrue(any("Network" in h for h in header), "Network should be in header")
        self.assertIn("Station", header, "Station should be in header")


if __name__ == "__main__":
    unittest.main()
