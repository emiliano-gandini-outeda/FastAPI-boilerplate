"""Shared connection settings models for storage backends.

These models are used by both the cache and rate limiter subsystems so that
their backends can share a single configuration definition.
"""

from pydantic import BaseModel


class RedisSettings(BaseModel):
    """Settings for Redis connection.

    This class defines the configuration for connecting to a Redis server.

    Attributes:
        host: Redis server hostname. Default is "localhost".
        port: Redis server port. Default is 6379.
        db: Redis database number. Default is 0.
        password: Redis server password. Default is None.
        connect_timeout: Connection timeout in seconds. Default is 5.
        pool_size: Maximum number of connections in the pool. Default is 10.
    """

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    connect_timeout: int = 5
    pool_size: int = 10


class MemcachedSettings(BaseModel):
    """Settings for Memcached connection.

    This class defines the configuration for connecting to a Memcached server.

    Attributes:
        host: Memcached server hostname. Default is "localhost".
        port: Memcached server port. Default is 11211.
        pool_size: Maximum number of connections in the pool. Default is 10.
        connect_timeout: Connection timeout in seconds. Default is 5.
            Note: This parameter is not currently used by aiomcache.Client but is
            kept for API consistency across backends.
    """

    host: str = "localhost"
    port: int = 11211
    pool_size: int = 10
    connect_timeout: int = 5
