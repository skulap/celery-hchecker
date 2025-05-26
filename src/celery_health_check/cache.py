from cachetools import TTLCache
from threading import Lock


class MemoryCache:
    def __init__(self, maxsize=1000, ttl=60):
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl)
        self.lock = Lock()

    def get(self, key):
        with self.lock:
            return self.cache.get(key)

    def set(self, key, value):
        with self.lock:
            self.cache[key] = value
