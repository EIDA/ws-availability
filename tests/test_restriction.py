from unittest import TestCase, mock
from datetime import date
from apps.restriction import Restriction, RestrictionInventory, Epoch


class TestInventoryLoad(TestCase):
    @mock.patch("apps.restriction.redis")
    def test_init(self, mock_redis):
        with open("tests/data/cache.pickle", "rb") as handle:
            mock_redis.Redis().get.return_value = handle.read()

        inv = RestrictionInventory(host="", port=0, key="")

        self.assertIsNotNone(inv)
        self.assertIsInstance(inv, RestrictionInventory)
        self.assertTrue(len(inv._inv) > 0)


class TestIsRestricted(TestCase):
    @mock.patch("apps.restriction.redis")
    def setUp(self, mock_redis):
        with open("tests/data/cache.pickle", "rb") as handle:
            mock_redis.Redis().get.return_value = handle.read()

        self.inv = RestrictionInventory(host="", port=0, key="")

        # Inject fake epoch to easily test `PARTIAL` restriction
        self.inv._inv["XX.YYY.00.BHE"] = []
        start_list = [date(2000, 1, 1), date(2002, 1, 1), date(2004, 1, 1)]
        end_list = [date(2001, 12, 31), date(2003, 12, 31), None]
        restriction_list = [
            Restriction.OPEN,
            Restriction.RESTRICTED,
            Restriction.OPEN,
        ]
        for sd, ed, r in zip(start_list, end_list, restriction_list):
            epoch = Epoch("AA", "BBB", "", "ZZZ", sd, ed)
            epoch.restriction = r
            self.inv._inv["XX.YYY.00.BHE"].append(epoch)

    def test_is_restricted_nonexisting(self):
        """Test if is_restricted returns None if channel doesn't exist."""
        self.assertIsNone(
            self.inv.is_restricted("XX.CCC..ZZZ", date(2000, 1, 1), date(2001, 1, 1))
        )

    def test_is_restricted_before(self):
        """Test if is_restricted returns None if channel didn't exist in interval."""
        self.assertIsNone(
            self.inv.is_restricted("NL.DBN..BHE", date(1995, 1, 1), date(1996, 1, 1))
        )

    def test_is_restricted_open1(self):
        """Assert channel is open between 2000-01-01 and 2001-01-01."""
        self.assertTrue(
            self.inv.is_restricted(
                "NL.DBN..BHE", date(2000, 1, 1), date(2001, 1, 1)
            ).value
            == Restriction.OPEN.value,
        )

    def test_is_restricted_closed(self):
        """Assert channel is restricted between 2003-01-01 and 2003-12-31."""
        self.assertTrue(
            self.inv.is_restricted(
                "CR.BRJN..BHE", date(2010, 1, 1), date(2010, 12, 31)
            ).value
            == Restriction.RESTRICTED.value,
        )

    def test_is_restricted_open2(self):
        """Assert channel is open between 2005-01-01 and 2006-01-01."""
        self.assertTrue(
            self.inv.is_restricted(
                "NL.DBN..BHE", date(2005, 1, 1), date(2006, 1, 1)
            ).value
            == Restriction.OPEN.value,
        )

    def test_is_restricted_partial1(self):
        """Assert channel is partially open between 2000-01-01 and 2003-01-01."""
        self.assertTrue(
            self.inv.is_restricted(
                "XX.YYY.00.BHE", date(2000, 1, 1), date(2003, 1, 1)
            ).value
            == Restriction.PARTIAL.value,
        )

    def test_is_restricted_partial2(self):
        """Assert channel is partially open between 2003-01-01 and 2006-01-01."""
        self.assertTrue(
            self.inv.is_restricted(
                "XX.YYY.00.BHE", date(2003, 1, 1), date(2006, 1, 1)
            ).value
            == Restriction.PARTIAL.value,
        )

    def test_is_restricted_partial3(self):
        """Assert channel is partially open between 2000-01-01 and 2006-01-01."""
        self.assertTrue(
            self.inv.is_restricted(
                "XX.YYY.00.BHE", date(2000, 1, 1), date(2006, 1, 1)
            ).value
            == Restriction.PARTIAL.value,
        )
