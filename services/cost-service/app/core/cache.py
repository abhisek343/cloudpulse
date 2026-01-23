"""
CloudPulse AI - Cost Service
Redis cache client for caching AWS cost data.
"""
import json
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings

settings = get_settings()


class RedisCache:
    """Redis cache client with async support."""
    
    def __init__(self) -> None:
        self._client: redis.Redis | None = None
    
    async def connect(self) -> None:
        """Connect to Redis."""
        self._client = redis.from_url(
            str(settings.redis_url),
            encoding="utf-8",
            decode_responses=True,
        )
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None
    
    @property
    def client(self) -> redis.Redis:
        """Get Redis client."""
        if not self._client:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client
    
    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        value = await self.client.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Set value in cache with optional TTL."""
        ttl = ttl or settings.redis_cache_ttl
        await self.client.setex(key, ttl, json.dumps(value))
    
    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        await self.client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return bool(await self.client.exists(key))
    
    async def flush_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        keys = await self.client.keys(pattern)
        if keys:
            return await self.client.delete(*keys)
        return 0
    
    def generate_key(self, *parts: str) -> str:
        """Generate cache key from parts."""
        return ":".join(["cloudpulse"] + list(parts))


# Global cache instance
cache = RedisCache()


async def get_cache() -> RedisCache:
    """Dependency for getting cache instance."""
    return cache
