import hashlib
from typing import List
import logging

logger = logging.getLogger(__name__)

class RedisBloomFilter:
    def __init__(self, redis_client, key: str, size: int = 1000000):
        self.redis = redis_client
        self.key = key
        self.size = size
        # 3 distinct salts to simulate 3 independent hash functions
        self.salts = [b"salt_engine_alpha", b"salt_engine_beta", b"salt_engine_gamma"]

    def _get_offsets(self, value: str) -> List[int]:
        """Calculates 3 bit offsets using SHA-256 hashes with different salts."""
        offsets = []
        value_bytes = value.encode("utf-8")
        for salt in self.salts:
            h = hashlib.sha256(salt + value_bytes).hexdigest()
            offset = int(h, 16) % self.size
            offsets.append(offset)
        return offsets

    async def add(self, value: str) -> None:
        """Adds a value to the Bloom Filter by setting corresponding bits to 1."""
        try:
            offsets = self._get_offsets(value)
            async with self.redis.pipeline(transaction=True) as pipe:
                for offset in offsets:
                    pipe.setbit(self.key, offset, 1)
                await pipe.execute()
        except Exception as e:
            logger.error(f"Error adding to Bloom Filter: {e}")
            # Do not raise exception, fail soft to keep system operating

    async def add_multi(self, values: List[str]) -> None:
        """Adds multiple values to the Bloom Filter in a single pipeline."""
        if not values:
            return
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                for value in values:
                    offsets = self._get_offsets(value)
                    for offset in offsets:
                        pipe.setbit(self.key, offset, 1)
                await pipe.execute()
        except Exception as e:
            logger.error(f"Error bulk-adding to Bloom Filter: {e}")

    async def exists(self, value: str) -> bool:
        """Checks if the value exists in the Bloom Filter. Returns True if it might exist, False if it definitely does not."""
        try:
            offsets = self._get_offsets(value)
            async with self.redis.pipeline(transaction=False) as pipe:
                for offset in offsets:
                    pipe.getbit(self.key, offset)
                results = await pipe.execute()
            return all(results)
        except Exception as e:
            logger.error(f"Error checking Bloom Filter: {e}")
            # If Redis/Bloom filter fails, return True to fall back and query PostgreSQL
            return True
