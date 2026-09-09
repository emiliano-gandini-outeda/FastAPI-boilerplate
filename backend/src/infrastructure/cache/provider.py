from typing import Any, NoReturn

from ..backends import BackendProvider
from .base import CacheBackend
from .exceptions import BackendNotFoundError


class CacheProvider(BackendProvider[CacheBackend]):
    """Provider for cache backends.

    This class manages the different cache backends and provides a single point of access
    for all cache operations. It supports registering multiple backends and switching
    between them at runtime.
    """

    def _raise_not_found(self, name: str | None, *, for_default: bool = False) -> NoReturn:
        if for_default:
            raise BackendNotFoundError(f"Backend '{name}' not found. Cannot set as default.")
        raise BackendNotFoundError(f"Backend '{name}' is not available.")


cache_provider = CacheProvider()


async def get(key: str, backend_name: str | None = None) -> Any:
    """Get a value from the cache.

    Args:
        key: The cache key to get.
        backend_name: The name of the backend to use. If None, the default backend is used.

    Returns:
        The cached value, or None if it doesn't exist.
    """
    backend = cache_provider.get_backend(backend_name)
    return await backend.get(key)


async def set(key: str, value: Any, expiration: int = 3600, backend_name: str | None = None) -> None:
    """Set a value in the cache.

    Args:
        key: The cache key to set.
        value: The value to cache.
        expiration: Time in seconds before the key expires (default: 3600).
        backend_name: The name of the backend to use. If None, the default backend is used.
    """
    backend = cache_provider.get_backend(backend_name)
    await backend.set(key, value, expiration)


async def delete(key: str, backend_name: str | None = None) -> None:
    """Delete a key from the cache.

    Args:
        key: The cache key to delete.
        backend_name: The name of the backend to use. If None, the default backend is used.
    """
    backend = cache_provider.get_backend(backend_name)
    await backend.delete(key)


async def delete_pattern(pattern: str, backend_name: str | None = None) -> None:
    """Delete all keys matching a pattern.

    Args:
        pattern: The pattern to match against keys.
        backend_name: The name of the backend to use. If None, the default backend is used.
    """
    backend = cache_provider.get_backend(backend_name)
    await backend.delete_pattern(pattern)


async def exists(key: str, backend_name: str | None = None) -> bool:
    """Check if a key exists in the cache.

    Args:
        key: The cache key to check.
        backend_name: The name of the backend to use. If None, the default backend is used.

    Returns:
        True if the key exists, False otherwise.
    """
    backend = cache_provider.get_backend(backend_name)
    return await backend.exists(key)


async def clear(backend_name: str | None = None) -> None:
    """Clear the entire cache.

    Args:
        backend_name: The name of the backend to use. If None, the default backend is used.
    """
    backend = cache_provider.get_backend(backend_name)
    await backend.clear()
