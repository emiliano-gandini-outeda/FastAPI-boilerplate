from typing import NoReturn

from ..backends import BackendProvider
from .base import RateLimiterBackend
from .exceptions import BackendNotFoundError


class RateLimiterProvider(BackendProvider[RateLimiterBackend]):
    """Provider for rate limiter backends with comprehensive backend management.

    This class manages multiple rate limiter backends and provides a centralized
    access point for all rate limiting operations. It supports dynamic backend
    registration, switching between backends, and health monitoring.

    The provider enables:
    - Multi-backend support for different use cases
    - Dynamic backend switching based on configuration
    - Health monitoring and fallback strategies
    - Centralized rate limiter configuration management

    Example:
        ```python
        # Initialize provider and register backends
        provider = RateLimiterProvider()

        # Register Redis backend for production
        redis_backend = RedisRateLimiterBackend(host="redis.example.com")
        provider.register_backend("redis", redis_backend, default=True)

        # Register in-memory backend for testing
        memory_backend = MemoryRateLimiterBackend()
        provider.register_backend("memory", memory_backend)

        # Use the provider
        backend = provider.get_backend("redis")
        count, is_limited = await backend.increment_and_check("user:123", 10, 60)
        ```
    """

    def _raise_not_found(self, name: str | None, *, for_default: bool = False) -> NoReturn:
        if for_default:
            raise BackendNotFoundError(name)
        raise BackendNotFoundError(name or "default")


rate_limiter_provider = RateLimiterProvider()


def get_rate_limiter_backend(backend_name: str | None = None) -> RateLimiterBackend:
    """Get a rate limiter backend by name from the global provider.

    This is a convenience function to get a rate limiter backend from the
    global provider instance. It provides a simple interface for accessing
    rate limiter backends throughout the application.

    Args:
        backend_name: The name of the backend to get. If None, the default
                     backend is used.

    Returns:
        The requested rate limiter backend.

    Raises:
        BackendNotFoundError: If the requested backend is not found.

    Example:
        ```python
        # Get default backend
        backend = get_rate_limiter_backend()

        # Get specific backend
        redis_backend = get_rate_limiter_backend("redis")

        # Use in dependency injection
        async def rate_limited_endpoint(
            backend: RateLimiterBackend = Depends(get_rate_limiter_backend)
        ):
            count, is_limited = await backend.increment_and_check("api_calls", 100, 3600)
        ```
    """
    return rate_limiter_provider.get_backend(backend_name)


async def increment_and_check(
    key: str, limit: int, period: int, backend_name: str | None = None, fail_open: bool | None = None
) -> tuple[int, bool]:
    """Increment the counter for a key and check if rate limit is exceeded.

    Convenience function that combines backend retrieval and rate limit checking
    in a single operation. Supports temporary fail-open policy overrides.

    Args:
        key: The rate limit key to increment.
        limit: Maximum number of requests allowed in the period.
        period: Time period in seconds.
        backend_name: The name of the backend to use. If None, the default
                     backend is used.
        fail_open: Whether to fail open if an error occurs. If None, uses
                  the backend's configured setting.

    Returns:
        Tuple of (current_count, is_rate_limited) where:
        - current_count: The current count of requests
        - is_rate_limited: True if the rate limit is exceeded, False otherwise

    Example:
        ```python
        # Basic rate limit check
        count, is_limited = await increment_and_check(
            key="user:123:api_calls",
            limit=100,
            period=3600
        )

        # With specific backend and fail-open override
        count, is_limited = await increment_and_check(
            key="user:123:critical_api",
            limit=10,
            period=60,
            backend_name="redis-primary",
            fail_open=False  # Strict enforcement
        )
        ```
    """
    backend = rate_limiter_provider.get_backend(backend_name)

    original_fail_open = None
    if fail_open is not None and fail_open != backend.fail_open:
        original_fail_open = backend.fail_open
        backend.fail_open = fail_open

    try:
        return await backend.increment_and_check(key, limit, period)
    finally:
        if original_fail_open is not None:
            backend.fail_open = original_fail_open


async def get_count(key: str, backend_name: str | None = None) -> int | None:
    """Get the current count for a key from the specified backend.

    Convenience function to get the current count for a rate limit key
    without incrementing it.

    Args:
        key: The rate limit key to check.
        backend_name: The name of the backend to use. If None, the default
                     backend is used.

    Returns:
        The current count or None if the key doesn't exist.

    Example:
        ```python
        # Check current usage
        current_count = await get_count("user:123:api_calls")
        if current_count is not None:
            remaining = max(0, limit - current_count)
            print(f"Remaining requests: {remaining}")
        ```
    """
    backend = rate_limiter_provider.get_backend(backend_name)
    return await backend.get_count(key)


async def reset(key: str, backend_name: str | None = None) -> None:
    """Reset the counter for a key using the specified backend.

    Convenience function to reset a rate limit counter, effectively
    clearing the rate limit for that key.

    Args:
        key: The rate limit key to reset.
        backend_name: The name of the backend to use. If None, the default
                     backend is used.

    Example:
        ```python
        # Reset rate limit for premium user
        await reset("user:123:api_calls")

        # Reset after resolving issue
        await reset("user:123:failed_logins", backend_name="redis-primary")
        ```
    """
    backend = rate_limiter_provider.get_backend(backend_name)
    await backend.reset(key)
