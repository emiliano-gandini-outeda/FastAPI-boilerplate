from ..backends import MEMCACHED_INSTALLED, REDIS_INSTALLED
from .base import CacheBackend
from .decorator import cache
from .provider import cache_provider, clear, delete, delete_pattern, exists, get, set

if MEMCACHED_INSTALLED:
    from .backends.memcached import MemcachedBackend, MemcachedSettings
else:
    MemcachedBackend = None  # type: ignore
    MemcachedSettings = None  # type: ignore

if REDIS_INSTALLED:
    from .backends.redis import RedisBackend, RedisSettings
else:
    RedisBackend = None  # type: ignore
    RedisSettings = None  # type: ignore

__all__ = [
    "CacheBackend",
    "MemcachedBackend",
    "RedisBackend",
    "MemcachedSettings",
    "RedisSettings",
    "cache",
    "cache_provider",
    "get",
    "set",
    "delete",
    "delete_pattern",
    "exists",
    "clear",
    "REDIS_INSTALLED",
    "MEMCACHED_INSTALLED",
]
