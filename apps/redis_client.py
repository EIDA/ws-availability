import redis
import pickle
from apps.restriction import REDIS_POOL as GLOBAL_POOL

class RedisClient:
    def __init__(self, host: str, port: int):
        global GLOBAL_POOL
        
        # Initialize global pool if not exists (lazy init fallback)
        if GLOBAL_POOL is None:
             from apps.restriction import RestrictionInventory
             # Trigger init
             _ = RestrictionInventory(host, port)
             from apps.restriction import REDIS_POOL as UPDATED_POOL
             GLOBAL_POOL = UPDATED_POOL

        self._pool = GLOBAL_POOL
        self._redis = redis.Redis(connection_pool=self._pool)

    def get(self, key: str):
        object = self._redis.get(key)
        if object:
            return pickle.loads(object)
        else:
            return None

    def set(self, key: str, obj, expiration: int = 0):
        if expiration == 0:
            self._redis.set(key, pickle.dumps(obj))
        else:
            self._redis.setex(key, expiration, pickle.dumps(obj))
