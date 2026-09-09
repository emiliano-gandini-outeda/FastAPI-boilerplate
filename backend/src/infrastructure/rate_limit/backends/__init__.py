"""Rate limiter backend implementations.

This package contains implementations of rate limiter backends for different storage engines.
"""

from ...backends import MEMCACHED_INSTALLED, REDIS_INSTALLED

if MEMCACHED_INSTALLED:
    from .memcached import MemcachedBackend, MemcachedSettings  # noqa: F401

    __all__ = ["MemcachedBackend", "MemcachedSettings"]
else:
    MemcachedBackendType: type | None = None
    MemcachedSettingsType: type | None = None
    __all__ = []

if REDIS_INSTALLED:
    from .redis import RedisBackend, RedisSettings  # noqa: F401

    __all__.extend(["RedisBackend", "RedisSettings"])
else:
    RedisBackendType: type | None = None
    RedisSettingsType: type | None = None
