import logging
import redis
import pickle
from datetime import date
from enum import Flag, auto
from functools import reduce


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
    def __init__(self, host: str, port: int, key: str):
        self._inv = {}
        self._pool = redis.ConnectionPool(
            host=host,
            port=port,
            db=0,
        )
        self._redis = redis.Redis(connection_pool=self._pool)

        cached_inventory = self._redis.get(key)
        # Try to get cached inventory from shared memcache instance
        if cached_inventory:
            self._inv = pickle.loads(cached_inventory)
            logging.info(f"Loaded inventory from cache...")
            return
        else:
            logging.exception(
                "Inventory information is not cached and needs to be rebuilt."
            )

    @property
    def is_populated(self):
        return len(self._inv) > 0

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
    restricted = RestrictionInventory()
    print(restricted)
    print(restricted.is_restricted("GB.WLF1..HHZ", date(2000, 1, 1), date(2002, 1, 1)))
    print(restricted.is_restricted("GB.WLF1..HHZ", date(2008, 1, 1), date(2009, 1, 1)))
    print(restricted.is_restricted("GB.WLF1..HHZ", date(2020, 1, 1), date(2001, 1, 1)))
    print(restricted.is_restricted("GB.XXXX..HHZ", date(2000, 1, 1), date(2002, 1, 1)))
    print(restricted.restriction_history("GB.WLF1..HHZ"))
    print(restricted.restriction_history("GB.XXXX..HHZ"))
