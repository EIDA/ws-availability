import logging
from datetime import timedelta
from typing import Union

from obspy import read_inventory
from obspy.core.inventory import Channel, Network
from obspy.core.inventory.inventory import Inventory
from pymemcache import serde
from pymemcache.client import base
from requests import HTTPError

from apps.restriction import Epoch, Restriction
from config import Config

logging.basicConfig(
    handlers=[logging.StreamHandler()],
    level=logging.INFO,
    format=f"[%(asctime)s] [0] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S +0000",
)
logger = logging.getLogger(__name__)


class Cache:
    def __init__(self):
        self._config = Config()
        self._client = base.Client(
            (self._config.CACHE_HOST, self._config.CACHE_PORT), serde=serde.pickle_serde
        )
        self._inv = {}

    @staticmethod
    def _is_obspy_restricted(cha_or_net: Union[Network, Channel]) -> Restriction:
        if cha_or_net.restricted_status == "open":
            return Restriction.OPEN
        elif cha_or_net.restricted_status == "closed":
            return Restriction.RESTRICTED
        else:
            return None

    def build_cache(self):
        logger.info(f"Getting inventory from FDSNWS-Station...")
        inventory = Inventory()

        try:
            url = f"{self._config.FDSNWS_STATION_URL}?level=network"
            cat = read_inventory(url)
            logger.info(
                "Harvesting {} from {}: {}".format(
                    len(cat.networks), url, ",".join([n.code for n in cat.networks])
                )
            )
        except HTTPError as err:
            logger.exception(err)
            return

        try:
            for n in cat:
                # Get inventory from FDSN:
                url = (
                    f"{self._config.FDSNWS_STATION_URL}?network={n.code}&level=channel"
                )
                i = read_inventory(url)
                inventory.networks += i.networks
                logger.info(
                    "Added network {} with {} stations: {}".format(
                        i.networks[0].code,
                        len(i.networks[0].stations),
                        ",".join([s.code for s in i.networks[0].stations]),
                    )
                )
        except HTTPError as err:
            logger.exception(err)
            return

        # Read ObsPy inventory
        for net in inventory:
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
                        logger.debug(
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
                            logger.debug("%s defaulting to OPEN", seed_id)
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
        self._client.set(
            self._config.CACHE_INVENTORY_KEY,
            self._inv,
            self._config.CACHE_INVENTORY_PERIOD,
        )
        logger.info(f"Completed caching inventory from FDSNWS-Station")


if __name__ == "__main__":
    cache = Cache()
    cache.build_cache()
