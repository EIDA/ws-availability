from unittest import TestCase, mock

from datetime import date
from obspy import read_inventory
from apps import restriction


class TestInventoryLoad(TestCase):
    @mock.patch('restriction.read_inventory')
    def test_init(self, mock_read):
        # Mock FDSN request
        mock_read.return_value = read_inventory('tests/data/inventory.xml')

        inv = restriction.RestrictionInventory('')

        self.assertIsNotNone(inv)
        self.assertIsInstance(inv, restriction.RestrictionInventory)
        self.assertTrue(len(inv._inv) > 0)


class TestIsRestricted(TestCase):
    @mock.patch('restriction.read_inventory')
    def setUp(self, mock_read):
        # Mock FDSN request
        mock_read.return_value = []

        self.inv = restriction.RestrictionInventory('')

        self.inv._inv['AA.BBB..ZZZ'] = []
        start_list = [date(2000, 1, 1), date(2002, 1, 1), date(2004, 1, 1)]
        end_list = [date(2001, 12, 31), date(2003, 12, 31), None]
        restriction_list = [restriction.Restriction.OPEN,
                            restriction.Restriction.RESTRICTED,
                            restriction.Restriction.OPEN]
        for sd, ed, r in zip(start_list, end_list, restriction_list):
            epoch = restriction.Epoch('AA', 'BBB', 'ZZZ', sd, ed)
            epoch.restriction = r
            self.inv._inv['AA.BBB..ZZZ'].append(epoch)

    def test_is_restricted_nonexisting(self):
        """Test if is_restricted returns None if channel doesn't exist."""
        self.assertIsNone(self.inv.is_restricted('XX.CCC..ZZZ',
                                                 date(2000, 1, 1), date(2001, 1, 1)))

    def test_is_restricted_before(self):
        """Test if is_restricted returns None if channel didn't exist in interval."""
        self.assertIsNone(self.inv.is_restricted('AA.BBB..ZZZ',
                                                 date(1987, 1, 1), date(1999, 1, 1)))

    def test_is_restricted_open1(self):
        """Assert channel is open between 2000-01-01 and 2001-01-01."""
        self.assertEqual(self.inv.is_restricted('AA.BBB..ZZZ',
                                                date(2000, 1, 1), date(2001, 1, 1)),
                         restriction.Restriction.OPEN)

    def test_is_restricted_closed(self):
        """Assert channel is restricted between 2003-01-01 and 2003-12-31."""
        self.assertEqual(self.inv.is_restricted('AA.BBB..ZZZ',
                                                date(2003, 1, 1), date(2003, 12, 31)),
                         restriction.Restriction.RESTRICTED)

    def test_is_restricted_open2(self):
        """Assert channel is open between 2005-01-01 and 2006-01-01."""
        self.assertEqual(self.inv.is_restricted('AA.BBB..ZZZ',
                                                date(2005, 1, 1), date(2006, 1, 1)),
                         restriction.Restriction.OPEN)

    def test_is_restricted_partial1(self):
        """Assert channel is partially open between 2000-01-01 and 2003-01-01."""
        self.assertEqual(self.inv.is_restricted('AA.BBB..ZZZ',
                                                date(2000, 1, 1), date(2003, 1, 1)),
                         restriction.Restriction.PARTIAL)

    def test_is_restricted_partial2(self):
        """Assert channel is partially open between 2003-01-01 and 2006-01-01."""
        self.assertEqual(self.inv.is_restricted('AA.BBB..ZZZ',
                                                date(2003, 1, 1), date(2006, 1, 1)),
                         restriction.Restriction.PARTIAL)

    def test_is_restricted_partial3(self):
        """Assert channel is partially open between 2000-01-01 and 2006-01-01."""
        self.assertEqual(self.inv.is_restricted('AA.BBB..ZZZ',
                                                date(2000, 1, 1), date(2006, 1, 1)),
                         restriction.Restriction.PARTIAL)
