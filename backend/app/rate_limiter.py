import time
import logging
from app.config import settings
from app.cache import redis_client

logger = logging.getLogger(__name__)

# Atomic Redis Lua script to enforce sliding window rate limiting
LUA_SLIDING_WINDOW_LIMITER = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local clear_before = now - window

-- 1. Evict logs older than window start
redis.call('zremrangebyscore', key, '-inf', clear_before)

-- 2. Count requests in current window
local current_requests = redis.call('zcard', key)

-- 3. Check threshold
if current_requests < limit then
    -- Add current request timestamp (using score and value as time)
    redis.call('zadd', key, now, now)
    -- Extend lifetime of tracking set
    redis.call('expire', key, window * 2)
    return 1 -- Allowed
else
    return 0 -- Throttled
end
"""

class RedisRateLimiter:
    @classmethod
    async def is_allowed(cls, client_identifier: str) -> bool:
        """
        Validates if a client request should be throttled.
        Returns:
            - True if request is under limit or Redis is down (fail-open).
            - False if rate limit is exceeded.
        """
        key = f"rate_limit:{client_identifier}"
        now = time.time()
        
        try:
            # Execute Lua Script on Redis
            allowed = await redis_client.eval(
                LUA_SLIDING_WINDOW_LIMITER,
                1,                       # Number of keys
                key,                     # KEYS[1]
                str(now),                # ARGV[1]
                str(settings.RATE_LIMIT_WINDOW), # ARGV[2]
                str(settings.RATE_LIMIT_MAX)    # ARGV[3]
            )
            return bool(allowed)
        except Exception as e:
            logger.error(f"Redis Rate Limiter evaluation failure for key {key}: {e}. Fallback to fail-open.")
            return True
