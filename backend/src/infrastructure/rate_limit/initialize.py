"""Module for initializing the rate limiter backends."""

from ...modules.common.utils.logger import get_logger
from ..backends import MEMCACHED_INSTALLED, REDIS_INSTALLED
from ..config import CacheBackendType, get_settings
from .exceptions import BackendNotFoundError
from .provider import rate_limiter_provider

logger = get_logger(__name__)

if MEMCACHED_INSTALLED:
    from .backends import MemcachedBackend, MemcachedSettings

if REDIS_INSTALLED:
    from .backends import RedisBackend, RedisSettings


async def initialize_rate_limiter() -> None:
    """Initialize the rate limiter backends.

    This function initializes the rate limiter backends based on the application settings.
    It is called during application startup.
    """
    settings = get_settings()

    if not settings.RATE_LIMITER_ENABLED:
        return

    if settings.RATE_LIMITER_BACKEND == CacheBackendType.MEMCACHED.value:
        if not MEMCACHED_INSTALLED:
            raise ImportError("The aiomcache package is not installed. Please install it with 'pip install aiomcache'.")

        memcached_settings = MemcachedSettings(
            host=settings.RATE_LIMITER_MEMCACHED_HOST,
            port=settings.RATE_LIMITER_MEMCACHED_PORT,
            pool_size=settings.RATE_LIMITER_MEMCACHED_POOL_SIZE,
        )
        memcached_backend = MemcachedBackend(settings=memcached_settings, fail_open=settings.RATE_LIMITER_FAIL_OPEN)
        rate_limiter_provider.register_backend(CacheBackendType.MEMCACHED.value, memcached_backend, default=True)

    elif settings.RATE_LIMITER_BACKEND == CacheBackendType.REDIS.value:
        if not REDIS_INSTALLED:
            raise ImportError("The redis package is not installed. Please install it with 'pip install redis'.")

        redis_settings = RedisSettings(
            host=settings.RATE_LIMITER_REDIS_HOST,
            port=settings.RATE_LIMITER_REDIS_PORT,
            db=settings.RATE_LIMITER_REDIS_DB,
            password=settings.RATE_LIMITER_REDIS_PASSWORD,
            connect_timeout=settings.RATE_LIMITER_REDIS_CONNECT_TIMEOUT,
            pool_size=settings.RATE_LIMITER_REDIS_POOL_SIZE,
        )
        redis_backend = RedisBackend(settings=redis_settings, fail_open=settings.RATE_LIMITER_FAIL_OPEN)
        rate_limiter_provider.register_backend(CacheBackendType.REDIS.value, redis_backend, default=True)


async def close_rate_limiter() -> None:
    """Close all rate limiter connections.

    This function should be called during application shutdown to clean up resources.
    """
    settings = get_settings()

    if not settings.RATE_LIMITER_ENABLED:
        return

    if settings.RATE_LIMITER_BACKEND == CacheBackendType.MEMCACHED.value and MEMCACHED_INSTALLED:
        try:
            backend = rate_limiter_provider.get_backend(CacheBackendType.MEMCACHED.value)
        except BackendNotFoundError:
            logger.debug("Rate limiter backend 'memcached' was never initialized; nothing to close.")
            return
        if hasattr(backend, "client") and hasattr(backend.client, "close"):
            await backend.client.close()

    elif settings.RATE_LIMITER_BACKEND == CacheBackendType.REDIS.value and REDIS_INSTALLED:
        try:
            backend = rate_limiter_provider.get_backend(CacheBackendType.REDIS.value)
        except BackendNotFoundError:
            logger.debug("Rate limiter backend 'redis' was never initialized; nothing to close.")
            return
        if hasattr(backend, "client") and hasattr(backend.client, "close"):
            await backend.client.close()
