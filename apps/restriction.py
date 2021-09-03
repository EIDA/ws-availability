import logging

from pymemcache.client import base
from pymemcache import serde

from datetime import date, timedelta
from enum import Flag, auto
from functools import reduce
from obspy import read_inventory
from obspy.core.inventory import Network, Channel
from typing import Union

from requests import HTTPError
from apps.globals import CACHE_HOST, CACHE_PREFIX, CACHE_LONG_INV_PERIOD


class Restriction(Flag):
    OPEN = auto()
    RESTRICTED = auto()
    PARTIAL = OPEN | RESTRICTED

    def __str__(self):
        return self.name


class Epoch:
    def __init__(
        self,
        net_code: str,
        sta_code: str,
        cha_code: str,
        start_date: date,
        end_date: date,
    ):
        self.network = net_code
        self.station = sta_code
        self.channel = cha_code
        self.start = start_date
        self.end = end_date
        self.restriction = None

    @property
    def seed_id(self) -> str:
        return f"{self.network}.{self.station}..{self.channel}"

    def __str__(self):
        return f"{self.seed_id} {self.start} --- {self.end} {self.restriction}"


class RestrictionInventory:
    def __init__(self, url: str):
        self._inv = {}

        client = base.Client((CACHE_HOST, 11211), serde=serde.pickle_serde)
        cached_inventory_key = f"{CACHE_PREFIX}inventory"

        # Try to get cached inventory from shared memcache instance
        cached_inventory = client.get(cached_inventory_key)
        if cached_inventory:
            self._inv = cached_inventory
            logging.info(f"Loaded inventory from cache...")
            return

        logging.info(f"Getting inventory from FDSNWS-Station...")

        inv = None

        try:
            # Get inventory from FDSN:
            inv = read_inventory(url)
        except HTTPError as err:
            logging.exception(err)
            return

        # Read ObsPy inventory
        for net in inv:
            for sta in net:
                for cha in sta:
                    epoch = Epoch(
                        net.code,
                        sta.code,
                        cha.code,
                        (cha.start_date.date if cha.start_date else None),
                        (cha.end_date.date if cha.end_date else None),
                    )
                    seed_id = epoch.seed_id

                    if seed_id not in self._inv:
                        self._inv[seed_id] = []

                    if seed_id in self._inv:
                        logging.debug(
                            "Repeated channel: %s %s %s",
                            seed_id,
                            epoch.start,
                            epoch.end,
                        )

                    cha_status = self._is_obspy_restricted(cha)
                    if cha_status is not None:
                        epoch.restriction = cha_status
                    else:
                        # Go up to network level
                        net_status = self._is_obspy_restricted(net)
                        if net_status is not None:
                            epoch.restriction = net_status
                        else:
                            logging.debug("%s defaulting to OPEN", seed_id)
                            epoch.restriction = Restriction.OPEN

                    self._inv[seed_id].append(epoch)

        # Sort epochs by start date
        for seed_id in self._inv:
            self._inv[seed_id].sort(key=lambda epoch: epoch.start)

            # Fill missing end dates
            for i in range(len(self._inv[seed_id]) - 1):
                if self._inv[seed_id][i].end is None:
                    self._inv[seed_id][i].end = self._inv[seed_id][
                        i + 1
                    ].start - timedelta(days=1)

        # Store inventory in shared memcache instance
        client.set(cached_inventory_key, self._inv, CACHE_LONG_INV_PERIOD)
        logging.warning(f"Completed caching inventory from FDSNWS-Station")

    @property
    def is_populated(self):
        return len(self._inv) > 0

    @staticmethod
    def _is_obspy_restricted(cha_or_net: Union[Network, Channel]) -> Restriction:
        if cha_or_net.restricted_status == "open":
            return Restriction.OPEN
        elif cha_or_net.restricted_status == "closed":
            return Restriction.RESTRICTED
        else:
            return None

    def __str__(self):
        output_str = ""
        for seed_id in self._inv:
            output_str += seed_id + "\n"
            for epoch in self._inv[seed_id]:
                output_str += f"    {epoch}\n"
        return output_str.strip()

    def is_restricted(
        self, seed_id: str, start_date: date, end_date: date
    ) -> Restriction:
        # If station doesn't/didn't exist, return None
        if seed_id not in self._inv:
            return None
        if end_date < self._inv[seed_id][0].start:
            return None
        if self._inv[seed_id][-1].end and start_date > self._inv[seed_id][-1].end:
            return None

        # Collect all restriction statuses in the interval
        # Assumes epochs are sorted and no intermediate end date in None
        restrictions = []
        for epoch in self._inv[seed_id]:
            logging.debug(
                "%s %s %s %s %s",
                start_date,
                end_date,
                epoch.start,
                epoch.end,
                epoch.restriction,
            )
            if end_date < epoch.start:
                logging.debug("  Break1")
                break
            if epoch.end and start_date > epoch.end:
                logging.debug("  Continue")
                continue

            logging.debug("  Append")
            restrictions.append(epoch.restriction)
            if epoch.end and end_date <= epoch.end:
                logging.debug("  Break2")
                break

        # Shouldn't happen, but just to be safe
        if len(restrictions) == 0:
            return None

        if len(restrictions) == 1:
            return restrictions[0]

        # Just OR all statuses
        return reduce(lambda x, y: x | y, restrictions)

    def restriction_history(self, seed_id: str) -> list:
        # If station doesn't exist, return None
        if seed_id not in self._inv:
            return None
        return [
            (epoch.start, epoch.end, epoch.restriction) for epoch in self._inv[seed_id]
        ]


if __name__ == "__main__":
    url = "http://www.orfeus-eu.org/fdsnws/station/1/query?level=channel&network=GB"
    restricted = RestrictionInventory(url)
    print(restricted)
    print(restricted.is_restricted("GB.WLF1..HHZ", date(2000, 1, 1), date(2002, 1, 1)))
    print(restricted.is_restricted("GB.WLF1..HHZ", date(2008, 1, 1), date(2009, 1, 1)))
    print(restricted.is_restricted("GB.WLF1..HHZ", date(2020, 1, 1), date(2001, 1, 1)))
    print(restricted.is_restricted("GB.XXXX..HHZ", date(2000, 1, 1), date(2002, 1, 1)))
    print(restricted.restriction_history("GB.WLF1..HHZ"))
    print(restricted.restriction_history("GB.XXXX..HHZ"))
