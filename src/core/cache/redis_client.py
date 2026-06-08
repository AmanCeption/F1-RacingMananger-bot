"""
Redis Cache Client
"""
import json
import logging
from typing import Optional, Any
from redis.asyncio import Redis, from_url

from src.core.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[Redis] = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


class Cache:
    """Helper class for common cache operations"""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def get(self, key: str) -> Optional[Any]:
        val = await self.redis.get(key)
        if val:
            return json.loads(val)
        return None

    async def set(self, key: str, value: Any, ttl: int = 300):
        await self.redis.setex(key, ttl, json.dumps(value, default=str))

    async def delete(self, key: str):
        await self.redis.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self.redis.exists(key))

    async def incr(self, key: str, ttl: int = 60) -> int:
        val = await self.redis.incr(key)
        if val == 1:
            await self.redis.expire(key, ttl)
        return val

    async def get_cooldown(self, user_id: int, action: str) -> Optional[int]:
        key = f"cooldown:{user_id}:{action}"
        ttl = await self.redis.ttl(key)
        return ttl if ttl > 0 else None

    async def set_cooldown(self, user_id: int, action: str, seconds: int):
        key = f"cooldown:{user_id}:{action}"
        await self.redis.setex(key, seconds, "1")

    async def rate_limit(self, user_id: int) -> int:
        key = f"ratelimit:{user_id}"
        return await self.incr(key, ttl=60)


async def get_cache() -> Cache:
    redis = await get_redis()
    return Cache(redis)
