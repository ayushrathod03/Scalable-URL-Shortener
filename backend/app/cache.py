import logging
from typing import Optional
import redis.asyncio as redis
from app.config import settings
from app.bloom_filter import RedisBloomFilter
from app.metrics import CACHE_REQUESTS_TOTAL

logger = logging.getLogger(__name__)

# Initialize asynchronous Redis client
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD,
    db=0
)

# Instantiate the Bloom Filter
bloom_filter = RedisBloomFilter(
    redis_client=redis_client, 
    key=settings.BLOOM_FILTER_KEY, 
    size=settings.BLOOM_FILTER_SIZE
)

async def get_cached_url(token: str) -> Optional[str]:
    """
    Attempts to retrieve a URL from cache.
    Returns:
        - The long URL string on a cache hit.
        - "__NOT_FOUND__" sentinel if the Bloom Filter indicates it definitely does not exist.
        - None if it's a cache miss but exists in the Bloom Filter (requiring PG lookup).
    """
    # 1. Query Redis Cache
    try:
        cached_url = await redis_client.get(f"url:{token}")
        if cached_url:
            CACHE_REQUESTS_TOTAL.labels(result="hit").inc()
            return cached_url.decode("utf-8")
    except Exception as e:
        logger.error(f"Redis cache read failure: {e}")
        # If Redis connection drops, proceed directly to DB fallback without Bloom Filter
        return None

    # 2. Query Bloom Filter (Cache Miss Path)
    try:
        exists_in_bloom = await bloom_filter.exists(token)
        if not exists_in_bloom:
            CACHE_REQUESTS_TOTAL.labels(result="miss").inc()
            # Bloom Filter guarantees non-existence; bypass database entirely
            logger.info(f"Bloom Filter blocked lookups for non-existent token: {token}")
            return "__NOT_FOUND__"
    except Exception as e:
        logger.error(f"Bloom Filter query failure: {e}")
        # In case of Redis failure, assume it might exist and query DB
        return None

    CACHE_REQUESTS_TOTAL.labels(result="miss").inc()
    return None

async def set_cached_url(token: str, long_url: str, ttl: int = 86400) -> None:
    """Sets URL in cache and populates the Bloom Filter."""
    try:
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.set(f"url:{token}", long_url, ex=ttl)
            await pipe.execute()
        
        # Add to Bloom Filter
        await bloom_filter.add(token)
    except Exception as e:
        logger.error(f"Failed to populate Redis cache/Bloom filter: {e}")
