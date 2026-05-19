import asyncio
import os
import time
import redis.asyncio as redis

# create a redis client instance

redis_client=os.getenv("REDIS_URL","redis://localhost:6379")
redis_required=os.getenv("REDIS_REQUIRED","false").lower() in ("1","true","yes")
redis_fallback=os.getenv("REDIS_FALLBACK","true").lower() in ("1","true","yes")
# Note: decode_responses=True ensures we get strings back instead of bytes
redis_pool=redis.from_url(redis_client,decode_responses=True)

class InMemoryRedis:
    def __init__(self):
        self._store = {}
        self._expires_at = {}
        self._lock = asyncio.Lock()

    def _purge_if_expired(self, key, now):
        expires_at = self._expires_at.get(key)
        if expires_at is not None and now >= expires_at:
            self._store.pop(key, None)
            self._expires_at.pop(key, None)

    async def ping(self):
        return True

    async def get(self, key):
        async with self._lock:
            now = time.monotonic()
            self._purge_if_expired(key, now)
            return self._store.get(key)

    async def set(self, key, value):
        async with self._lock:
            self._store[key] = value
            self._expires_at.pop(key, None)
            return True

    async def setex(self, key, seconds, value):
        async with self._lock:
            self._store[key] = value
            self._expires_at[key] = time.monotonic() + float(seconds)
            return True

    async def expire(self, key, seconds):
        async with self._lock:
            if key not in self._store:
                return False
            self._expires_at[key] = time.monotonic() + float(seconds)
            return True

    async def incr(self, key):
        async with self._lock:
            now = time.monotonic()
            self._purge_if_expired(key, now)
            value = int(self._store.get(key, 0)) + 1
            self._store[key] = value
            return value

async def check_redis_health():
    """Pings redis on startup to see if it's healthy"""
    global redis_pool
    try:
        await redis_pool.ping()
        print("Redis is healthy")
    except Exception as e:
        if redis_required:
            raise RuntimeError(
                "Redis is required but is not reachable. Set REDIS_URL or start Redis."
            ) from e
        if redis_fallback:
            print(f"Redis health check failed: {e}. Falling back to in-memory store.")
            redis_pool = InMemoryRedis()
        else:
            print(f"Redis health check failed: {e}")