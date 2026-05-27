"""
Caching utility - for caching embeddings and search results.
"""

import logging
from typing import Any, Dict, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class Cache:
    """
    Simple cache implementation.
    Can be extended to use Redis or Memcached.
    """

    def __init__(self, backend: str = "memory", ttl: int = 3600):
        """
        Initialize Cache.

        Args:
            backend: Cache backend (memory, redis, etc)
            ttl: Time-to-live in seconds
        """
        self.backend = backend
        self.ttl = ttl
        self.memory_cache: Dict[str, Any] = {}
        logger.info(f"Initialized Cache with backend: {backend}")

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key in self.memory_cache:
            return self.memory_cache[key]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        self.memory_cache[key] = value
        logger.debug(f"Set cache: {key}")

    def delete(self, key: str) -> None:
        """Delete value from cache."""
        if key in self.memory_cache:
            del self.memory_cache[key]
            logger.debug(f"Deleted cache: {key}")

    def clear(self) -> None:
        """Clear all cache."""
        self.memory_cache.clear()
        logger.warning("Cleared all cache")


def cached(ttl: int = 3600):
    """
    Decorator for caching function results.

    Args:
        ttl: Time-to-live in seconds
    """
    cache = Cache(ttl=ttl)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            result = cache.get(cache_key)
            if result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
