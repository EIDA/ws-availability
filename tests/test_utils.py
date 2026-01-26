
import unittest
from unittest.mock import MagicMock, patch
from flask import Flask
from datetime import datetime
from apps import utils
from apps.globals import HTTP, Error

app = Flask(__name__)


class TestUtils(unittest.TestCase):

    def test_is_valid_integer(self):
        self.assertTrue(utils.is_valid_integer(10))
        self.assertTrue(utils.is_valid_integer("10"))
        self.assertFalse(utils.is_valid_integer("10.5"))
        self.assertFalse(utils.is_valid_integer("abc"))
        self.assertTrue(utils.is_valid_integer(5, mini=0, maxi=10))
        self.assertFalse(utils.is_valid_integer(-1, mini=0, maxi=10))

    def test_is_valid_float(self):
        self.assertTrue(utils.is_valid_float(10.5))
        self.assertTrue(utils.is_valid_float("10.5"))
        self.assertFalse(utils.is_valid_float("abc"))
    
    def test_is_valid_datetime(self):
        self.assertIsInstance(utils.is_valid_datetime("2023-01-01"), datetime)
        self.assertIsInstance(utils.is_valid_datetime("2023-01-01T12:00:00"), datetime)
        self.assertIsNone(utils.is_valid_datetime("invalid"))

    def test_is_valid_bool_string(self):
        self.assertTrue(utils.is_valid_bool_string("true"))
        self.assertTrue(utils.is_valid_bool_string("TRUE"))
        self.assertTrue(utils.is_valid_bool_string("1"))
        self.assertTrue(utils.is_valid_bool_string("false"))
        self.assertTrue(utils.is_valid_bool_string("0"))
        self.assertFalse(utils.is_valid_bool_string("maybe"))
        self.assertFalse(utils.is_valid_bool_string(None))

    def test_currentutcday(self):
        dt = utils.currentutcday()
        self.assertEqual(dt.hour, 0)
        self.assertEqual(dt.minute, 0)
        self.assertEqual(dt.second, 0)
        self.assertEqual(dt.microsecond, 0)

    def test_check_request_valid(self):
        with app.test_request_context('/?net=NL&sta=HGN'):
            # Params dict setup (mimics what root.py passes)
            params = {
                "net": None, "sta": None, 
                "constraints": {
                    "alias": [], 
                    "not_none": [],
                    "booleans": [],
                    "floats": []
                }
            }
            
            # Test success
            p, status = utils.check_request(params)
            self.assertEqual(status["code"], 200)

    def test_check_request_unknown_param(self):
        with app.test_request_context('/?unknown_param=val'):
            params = {
                "net": None,
                "constraints": {"alias": []}
            }
            
            _, status = utils.check_request(params)
            self.assertEqual(status["code"], 400)
            self.assertIn(Error.UNKNOWN_PARAM, status["details"])

    def test_check_request_invalid_char(self):
        with app.test_request_context('/?net=Bad;Char'):
            params = {"net": None}
            
            _, status = utils.check_request(params)
            self.assertEqual(status["code"], 400)
            self.assertIn(Error.CHAR, status["details"])

if __name__ == "__main__":
    unittest.main()
