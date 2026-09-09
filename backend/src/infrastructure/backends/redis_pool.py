"""Shared Redis connection pools.

Pools are keyed by their connection parameters so that subsystems (cache,
rate limiter) pointing at the same server reuse a single pool instead of each
opening their own. Clients built on a shared pool do not own it: redis-py sets
``auto_close_connection_pool = False`` when a pool is passed in, so closing a
client never tears down the pool. Pools are closed centrally via
``close_redis_pools()`` during application shutdown.
"""

from redis.asyncio import ConnectionPool

from .settings import RedisSettings

_pools: dict[tuple, ConnectionPool] = {}


def _pool_key(settings: RedisSettings) -> tuple:
    return (
        settings.host,
        settings.port,
        settings.db,
        settings.password,
        settings.pool_size,
        settings.connect_timeout,
    )


def get_redis_pool(settings: RedisSettings) -> ConnectionPool:
    """Get the shared connection pool for the given settings.

    Identical settings return the same pool; differing settings get their own.

    Args:
        settings: Redis connection settings.

    Returns:
        The shared connection pool for those settings.
    """
    key = _pool_key(settings)
    pool = _pools.get(key)
    if pool is None:
        pool = ConnectionPool(
            host=settings.host,
            port=settings.port,
            db=settings.db,
            password=settings.password,
            socket_timeout=settings.connect_timeout,
            socket_connect_timeout=settings.connect_timeout,
            socket_keepalive=True,
            max_connections=settings.pool_size,
        )
        _pools[key] = pool
    return pool


async def close_redis_pools() -> None:
    """Disconnect and forget all shared pools. Safe to call when none exist."""
    for pool in _pools.values():
        await pool.disconnect()
    _pools.clear()
