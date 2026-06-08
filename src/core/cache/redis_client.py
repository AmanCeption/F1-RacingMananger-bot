"""
Redis client - disabled (using memory instead)
This file kept for compatibility only
"""

class Cache:
    """Dummy cache - uses memory"""
    def __init__(self):
        self._store = {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ttl=300):
        self._store[key] = value

    async def delete(self, key):
        self._store.pop(key, None)


_cache = Cache()

async def get_cache():
    return _cache

async def get_redis():
    return None
