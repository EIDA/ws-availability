import requests
import xml.etree.ElementTree as ET
import gzip
import logging

from xml.etree.ElementTree import ParseError

FDSN_STATION_URL = "http://eida-federator.ethz.ch/fdsnws/station/1/query"
NO_FDSNWS_DATA = "n/a"
NSMAP = {"mw": "http://www.fdsn.org/xml/station/1"}


class FdsnClient:
    def _post(self, url, body):
        try:
            req = requests.post(url, data=body, allow_redirects=True)
            return req.content
        except Exception as e:
            logging.exception(e)
            return None

    def assign_restricted_statuses(self, params, streams):
        """Gets list of streams and returns the same list of streams, but with
        restricted status values assigned using response from EIDAWS-Federator

        Args
            params ([]): URL query parameters
            streams ([]): List of streams.

        Returns:
            []: Same list of streams, but with updated restricted status.
        """

        body = "level=station\n"

        for s in streams:
            body += f"{s[0]} {s[1]} * * {s[6].isoformat()} {s[7].isoformat()} \n"

        response = self._post(FDSN_STATION_URL, body)
        return response
