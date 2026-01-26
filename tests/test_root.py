
import unittest
import io
import re
from unittest.mock import MagicMock, patch
from flask import Flask
from apps import root
from apps import models
from apps.globals import HTTP, Error, MAX_DATA_ROWS

app = Flask(__name__)

class TestRoot(unittest.TestCase):

    def test_get_post_params_parsing(self):
        # Mock request stream
        # Valid format: global key=value lines, followed by positional rows
        body = "quality=D\nNL HGN * *\nDE BFO * *"
        with app.test_request_context(method="POST", data=body):
            # We need to mock request.stream behavior explicitly or rely on Flask's data handling?
            # Flask's test_request_context populates input_stream.
            # root.get_post_params reads from request.stream.
            # However, test_request_context sets input_stream but request.stream in code might act differently?
            # Let's try mocking request.stream directly to be sure.
            with patch('apps.root.request') as mock_req:
                mock_req.stream = io.BytesIO(body.encode('utf-8'))
                mock_req.method = "POST"
                
                params_list = root.get_post_params()
                self.assertEqual(len(params_list), 2)
                self.assertEqual(params_list[0]["network"], "NL")
                self.assertEqual(params_list[0]["station"], "HGN")
                self.assertEqual(params_list[1]["network"], "DE")

    def test_checks_get_valid(self):
        with app.test_request_context('/?net=NL&sta=HGN'):
             # IMPORTANT: root.py imports request at module level 'from flask import request'.
             # If we use `with app.test_request_context()` it sets the thread local.
             # So `root.request` (which is flask.request) should work.
             
             params, result = root.checks_get()
             self.assertEqual(result["code"], 200)
             self.assertEqual(params["network"], "NL")
             self.assertEqual(params["limit"], MAX_DATA_ROWS)

    def test_checks_get_invalid(self):
        with app.test_request_context('/?net=Valid&quality=BadQuality'):
             # Validation should fail in check_parameters -> Pydantic
             params, result = root.checks_get()
             # models.py validate_quality splits by comma and regex [DMQR...]. 
             # "BadQuality" fails regex.
             self.assertNotEqual(result["code"], 200)

if __name__ == "__main__":
    unittest.main()
