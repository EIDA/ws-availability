import requests
import xml.etree.ElementTree as ET
import gzip
import logging

import xml.etree.ElementTree as ET

from datetime import datetime

FDSN_STATION_URL = "http://eida-federator.ethz.ch/fdsnws/station/1/query"
NO_FDSNWS_DATA = "n/a"
ENCODING = "utf-8"
NSMAP = {"mw": "http://www.fdsn.org/xml/station/1"}


class FdsnClient:
    def _post(self, url, body):
        try:
            req = requests.post(url, data=body, allow_redirects=True)
            req.encoding = ENCODING
            return req.content
        except Exception as e:
            logging.exception(e)
            return None

    def _get(self, url):
        try:
            req = requests.get(url, allow_redirects=True)
            req.encoding = ENCODING
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

        # body = "level=station\n"

        net_stat = set()
        for s in streams:
            net_stat.add(f"?{s[0]} {s[1]} * * {s[6]} {s[7]}")

        for ns in net_stat:
            url = FDSN_STATION_URL + ns
            resp = self._get(url)
            event_root = ET.fromstring(resp)
        return response
