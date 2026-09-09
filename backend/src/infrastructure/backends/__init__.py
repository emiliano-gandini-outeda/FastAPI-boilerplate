"""Shared building blocks for connection-oriented infrastructure backends.

This package holds the pieces that are identical between the cache and rate
limiter subsystems: connection settings models, optional-dependency detection,
and the generic backend provider registry.
"""

from importlib.util import find_spec

from .provider import BackendProvider
from .settings import MemcachedSettings, RedisSettings

MEMCACHED_INSTALLED = find_spec("aiomcache") is not None
REDIS_INSTALLED = find_spec("redis") is not None

__all__ = [
    "BackendProvider",
    "MemcachedSettings",
    "RedisSettings",
    "MEMCACHED_INSTALLED",
    "REDIS_INSTALLED",
]
