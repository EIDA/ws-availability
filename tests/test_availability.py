import unittest
import sys
from copy import copy
from datetime import datetime

sys.path.append("../")

from apps.globals import Error, HTTP
from apps.root import check_parameters
from apps.utils import error_param
from apps.utils import is_valid_integer
from apps.utils import is_valid_float
from apps.utils import is_valid_datetime
from apps.utils import is_valid_network
from apps.utils import is_valid_station
from apps.utils import is_valid_location
from apps.utils import is_valid_channel
from apps.utils import is_valid_bool_string


class MyTest(unittest.TestCase):
    def test_integers(self):
        self.assertTrue(is_valid_integer(1, 0, 1))
        self.assertTrue(is_valid_float(1.9, -5, 5))
        self.assertFalse(is_valid_integer(-1, 0, 1))
        self.assertTrue(is_valid_integer(0.5, 0, 1))
        self.assertFalse(is_valid_float(6, -5, 5))

    def test_dates(self):
        self.assertTrue(is_valid_datetime("2018-01-17"))
        self.assertTrue(is_valid_datetime("2018-01-17T19:07:01"))
        self.assertFalse(is_valid_datetime("2018-01-17Z19:07:01"))
        self.assertFalse(is_valid_datetime("2018-01-*"))
        self.assertFalse(is_valid_datetime("2018-01-17T19:07:60"))
        self.assertEqual(
            is_valid_datetime("2018-01-17T19:07:01.000021"),
            datetime(2018, 1, 17, 19, 7, 1, 21),
        )

    def test_networks(self):
        self.assertTrue(is_valid_network("G"))  # 1 or 2
        self.assertTrue(is_valid_network("FR"))
        self.assertTrue(is_valid_network("F?"))
        self.assertFalse(is_valid_network("FRA"))
        self.assertFalse(is_valid_network("FR?"))
        self.assertFalse(is_valid_network("FR*"))
        self.assertFalse(is_valid_network("F-"))

    def test_stations(self):
        self.assertTrue(is_valid_station("C"))  # 1 to 5
        self.assertTrue(is_valid_station("CIELZ"))
        self.assertTrue(is_valid_station("*"))
        self.assertTrue(is_valid_station("CI??"))
        self.assertTrue(is_valid_station("CI*"))
        self.assertFalse(is_valid_station("CIELLE"))
        self.assertFalse(is_valid_station("CIELL?"))
        self.assertFalse(is_valid_station("CIçL"))

    def test_locations(self):
        self.assertTrue(is_valid_location("01"))  # 2
        self.assertTrue(is_valid_location("*"))
        self.assertFalse(is_valid_location("00*"))
        self.assertFalse(is_valid_location("001?"))
        self.assertFalse(is_valid_location("0$"))
        self.assertFalse(is_valid_location("???"))

    def test_channels(self):
        self.assertTrue(is_valid_channel("HHZ"))  # 3
        self.assertTrue(is_valid_channel("*"))
        self.assertTrue(is_valid_channel("H?Z"))
        self.assertTrue(is_valid_channel("???"))
        self.assertFalse(is_valid_channel("HHH*"))
        self.assertFalse(is_valid_channel("H$H"))

    #        self.assertFalse(is_valid_channel("HH"))
    #        self.assertFalse(is_valid_channel("??"))

    def test_bool_string(self):
        self.assertTrue(is_valid_bool_string("yes"))
        self.assertTrue(is_valid_bool_string("true"))
        self.assertTrue(is_valid_bool_string("t"))
        self.assertTrue(is_valid_bool_string("y"))
        self.assertTrue(is_valid_bool_string("1"))

        self.assertTrue(is_valid_bool_string("yEs"))
        self.assertTrue(is_valid_bool_string("TrUe"))
        self.assertTrue(is_valid_bool_string("T"))
        self.assertTrue(is_valid_bool_string("Y"))
        self.assertTrue(is_valid_bool_string("1"))

        self.assertTrue(is_valid_bool_string("no"))
        self.assertTrue(is_valid_bool_string("false"))
        self.assertTrue(is_valid_bool_string("f"))
        self.assertTrue(is_valid_bool_string("n"))

        self.assertTrue(is_valid_bool_string("nO"))
        self.assertTrue(is_valid_bool_string("faLSe"))
        self.assertTrue(is_valid_bool_string("F"))
        self.assertTrue(is_valid_bool_string("N"))

        self.assertFalse(is_valid_bool_string("fase"))
        self.assertFalse(is_valid_bool_string("O"))
        self.assertFalse(is_valid_bool_string("oui"))

    def test_parameters(self):

        # ?network=FR&channel=HHZ&starttime=2018-02-12T03:08:02&endtime=2018-02-12T03:10:00&station=CIEL
        p1 = {}
        p1["network"] = "FR"
        p1["station"] = "CIEL"
        p1["location"] = "*"
        p1["channel"] = "HHZ"
        p1["start"] = "2018-02-12T03:08:02"
        p1["end"] = "2018-02-12T04:08:02"
        p1["format"] = "text"
        p1["orderby"] = None
        p1["quality"] = "*"
        p1["show"] = ""
        p1["limit"] = None
        p1["merge"] = ""
        p1["mergegaps"] = None
        p1["includerestricted"] = "F"
        p1["nodata"] = "204"
        p1["base_url"] = "/extent"
        p1["constraints"] = {
            "booleans": ["includerestricted"],
            "floats": [],
            "not_none": [],
        }

        valid_param = {"msg": HTTP._200_, "details": Error.VALID_PARAM, "code": 200}

        p2 = copy(p1)
        self.assertEqual(check_parameters(p2), (p2, valid_param))

        p2 = copy(p1)
        p1["start"] = "2018-02-12T03:08:02"
        p1["end"] = "30"
        self.assertEqual(check_parameters(p2), (p2, valid_param))

        p2 = copy(p1)
        p1["start"] = "currentutcday"
        p1["end"] = "60"
        self.assertEqual(check_parameters(p2), (p2, valid_param))

        p2 = copy(p1)
        p2["start"] = None
        self.assertEqual(check_parameters(p2), (p2, valid_param))

        p2 = copy(p1)
        p2["start"] = ""
        self.assertEqual(
            check_parameters(p2), error_param(p2, Error.TIME + p2["start"])
        )

        p2 = copy(p1)
        p2["start"] = "2018-02-12Z04:08:02"
        self.assertEqual(
            check_parameters(p2), error_param(p2, Error.TIME + p2["start"])
        )


if __name__ == "__main__":
    unittest.main()
