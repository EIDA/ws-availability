import redis
import pickle


class RedisClient:
    def __init__(self, host: str, port: int):
        self._pool = redis.ConnectionPool(host=host, port=port, db=0)
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
