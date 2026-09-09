"""
Caching backend implementations.

This module contains implementations of various cache backends that follow the
CacheBackend interface.
"""

from ...backends import MEMCACHED_INSTALLED, REDIS_INSTALLED

if MEMCACHED_INSTALLED:
    from .memcached import (
        MemcachedBackend,
        MemcachedSettings,
        PatternMatchingNotSupportedError,
    )
else:
    MemcachedBackend = None  # type: ignore
    MemcachedSettings = None  # type: ignore
    PatternMatchingNotSupportedError = None  # type: ignore

if REDIS_INSTALLED:
    from .redis import RedisBackend, RedisSettings
else:
    RedisBackend = None  # type: ignore
    RedisSettings = None  # type: ignore

__all__ = ["MemcachedBackend", "MemcachedSettings", "RedisBackend", "RedisSettings"]
if MEMCACHED_INSTALLED:
    __all__.append("PatternMatchingNotSupportedError")
