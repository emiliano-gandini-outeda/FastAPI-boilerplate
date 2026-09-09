"""Tests for the shared Redis connection pool registry."""

import pytest

from src.infrastructure.backends.redis_pool import close_redis_pools, get_redis_pool
from src.infrastructure.backends.settings import RedisSettings
from src.infrastructure.cache.backends.redis import RedisBackend as CacheRedisBackend
from src.infrastructure.rate_limit.backends.redis import RedisBackend as RateLimiterRedisBackend


@pytest.fixture(autouse=True)
async def clean_pools():
    yield
    await close_redis_pools()


def test_same_settings_share_one_pool():
    """Cache and rate limiter on the same server share a single pool."""
    settings = RedisSettings(host="localhost", port=6379, db=0)
    cache_backend = CacheRedisBackend(settings=settings)
    rate_limit_backend = RateLimiterRedisBackend(settings=RedisSettings(host="localhost", port=6379, db=0))

    assert cache_backend.client.connection_pool is rate_limit_backend.client.connection_pool
    assert cache_backend.client.connection_pool is get_redis_pool(settings)


def test_different_settings_get_different_pools():
    """Differing connection parameters must not share a pool."""
    pool_a = get_redis_pool(RedisSettings(host="localhost", port=6379, db=0))
    pool_b = get_redis_pool(RedisSettings(host="localhost", port=6379, db=1))
    pool_c = get_redis_pool(RedisSettings(host="otherhost", port=6379, db=0))

    assert pool_a is not pool_b
    assert pool_a is not pool_c


@pytest.mark.asyncio
async def test_closing_one_client_does_not_tear_down_shared_pool():
    """Clients do not own the shared pool: aclose() leaves it usable."""
    settings = RedisSettings(host="localhost", port=6379, db=0)
    cache_backend = CacheRedisBackend(settings=settings)
    rate_limit_backend = RateLimiterRedisBackend(settings=settings)
    pool = get_redis_pool(settings)

    assert cache_backend.client.auto_close_connection_pool is False
    assert rate_limit_backend.client.auto_close_connection_pool is False

    await cache_backend.client.aclose()

    assert rate_limit_backend.client.connection_pool is pool
    assert get_redis_pool(settings) is pool


@pytest.mark.asyncio
async def test_close_redis_pools_disconnects_and_clears():
    """Central shutdown disconnects pools and empties the registry."""
    settings = RedisSettings(host="localhost", port=6379, db=0)
    pool = get_redis_pool(settings)

    await close_redis_pools()

    assert get_redis_pool(settings) is not pool


@pytest.mark.asyncio
async def test_close_redis_pools_without_pools_is_noop():
    await close_redis_pools()
