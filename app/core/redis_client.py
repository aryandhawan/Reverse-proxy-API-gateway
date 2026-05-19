import redis.asyncio as redis
import os 

# create a redis client instance

redis_client=os.getenv("REDIS_URL","redis://localhost:6379")
# Note: decode_responses=True ensures we get strings back instead of bytes
redis_pool=redis.from_url(redis_client,decode_responses=True)

async def check_redis_health():
    """Pings redis on startup to see if it's healthy"""
    try:
        await redis_pool.ping()
        print("Redis is healthy")
    except Exception as e:
        print(f"Redis health check failed: {e}")