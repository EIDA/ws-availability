import unittest
from datetime import datetime
from unittest.mock import patch

from apps.cli import _anchor_regex, _code_list, build_parser, main


class TestCliHelpers(unittest.TestCase):
    def test_anchor_regex(self):
        self.assertEqual(_anchor_regex(None), "^.*$")
        self.assertEqual(_anchor_regex(""), "^.*$")
        self.assertEqual(_anchor_regex("IV"), "^(IV)$")
        self.assertEqual(_anchor_regex("IV,GE"), "^(IV|GE)$")
        self.assertEqual(_anchor_regex(" IV , GE "), "^(IV|GE)$")

    def test_code_list(self):
        self.assertIsNone(_code_list(None))
        self.assertEqual(_code_list("00,10"), ["00", "10"])
        self.assertEqual(_code_list("--"), [""])          # empty location sentinel
        self.assertEqual(_code_list("00,--"), ["00", ""])

    def test_parser_requires_dates(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["--net", "IV"])  # no --start/--end

    def test_parser_rejects_bad_date(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["--start", "2008/01/01", "--end", "2009-01-01"])


class TestCliMain(unittest.TestCase):
    @patch("apps.cli.get_db_client")
    @patch("apps.cli.AvailabilityUpdater")
    def test_main_maps_args_to_run_updates(self, MockUpdater, _mock_db):
        inst = MockUpdater.return_value
        rc = main([
            "--net", "IV", "--sta", "ABC", "--loc=--", "--cha", "HHZ",
            "--start", "2008-01-01", "--end", "2009-01-01",
        ])
        self.assertEqual(rc, 0)
        inst.run_updates.assert_called_once()
        kwargs = inst.run_updates.call_args.kwargs
        self.assertEqual(kwargs["networks"], "^(IV)$")
        self.assertEqual(kwargs["stations"], "^(ABC)$")
        self.assertEqual(kwargs["locations"], [""])
        self.assertEqual(kwargs["channels"], ["HHZ"])
        self.assertEqual(kwargs["start_date"], datetime(2008, 1, 1))
        self.assertEqual(kwargs["end_date"], datetime(2009, 1, 1))

    @patch("apps.cli.get_db_client")
    @patch("apps.cli.AvailabilityUpdater")
    def test_main_defaults_to_all_streams(self, MockUpdater, _mock_db):
        inst = MockUpdater.return_value
        rc = main(["--start", "2023-01-01", "--end", "2023-02-01"])
        self.assertEqual(rc, 0)
        kwargs = inst.run_updates.call_args.kwargs
        self.assertEqual(kwargs["networks"], "^.*$")
        self.assertEqual(kwargs["stations"], "^.*$")
        self.assertIsNone(kwargs["locations"])
        self.assertIsNone(kwargs["channels"])

    @patch("apps.cli.get_db_client")
    @patch("apps.cli.AvailabilityUpdater")
    def test_main_rejects_reversed_range(self, MockUpdater, _mock_db):
        rc = main(["--start", "2009-01-01", "--end", "2008-01-01"])
        self.assertEqual(rc, 2)
        MockUpdater.return_value.run_updates.assert_not_called()


if __name__ == "__main__":
    unittest.main()
