import hashlib
from datetime import UTC, datetime

try:
    import aiomcache
    from aiomcache.exceptions import ClientException
except ImportError:
    raise ImportError(
        "The aiomcache package is not installed. "
        "Please install it with 'pip install aiomcache' or 'pip install -e \".[memcached]\"'"
    )

from pydantic import BaseModel

from ....modules.common.utils.logger import get_logger
from ..base import RateLimiterBackend
from ..exceptions import RateLimiterBackendException

logger = get_logger(__name__)


class MemcachedSettings(BaseModel):
    """Settings for Memcached connection.

    This class defines the configuration for connecting to a Memcached server.

    Attributes:
        host: Memcached server hostname. Default is "localhost".
        port: Memcached server port. Default is 11211.
        pool_size: Maximum number of connections in the pool. Default is 10.
        connect_timeout: Connection timeout in seconds. Default is 5.
            Note: This parameter is not currently used by aiomcache.Client but is
            kept for API consistency with other rate limiter backends.
    """

    host: str = "localhost"
    port: int = 11211
    pool_size: int = 10
    connect_timeout: int = 5


class MemcachedBackend(RateLimiterBackend):
    """Memcached implementation of the rate limiter backend."""

    def __init__(self, settings: MemcachedSettings | None = None, fail_open: bool = True):
        """Initialize the Memcached backend.

        Args:
            settings: Memcached connection settings. If None, default settings are used.
            fail_open: Whether to fail open (allow requests) when rate limiting errors occur.
                       Default is True for safety.
        """
        super().__init__(fail_open=fail_open)
        self.settings = settings or MemcachedSettings()
        try:
            self.client = aiomcache.Client(
                host=self.settings.host,
                port=self.settings.port,
                pool_size=self.settings.pool_size,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Memcached client: {e}")
            raise RateLimiterBackendException(f"Failed to initialize Memcached client: {e}")

    async def increment_and_check(self, key: str, limit: int, period: int) -> tuple[int, bool]:
        """Increment the counter for a key and check if rate limit is exceeded.

        Args:
            key: The rate limit key to increment.
            limit: Maximum number of requests allowed in the period.
            period: Time period in seconds.

        Returns:
            Tuple of (current_count, is_rate_limited) where:
            - current_count: The current count of requests
            - is_rate_limited: True if the rate limit is exceeded, False otherwise
        """
        try:
            key_hash = hashlib.md5(key.encode()).hexdigest()
            current_timestamp = int(datetime.now(UTC).timestamp())
            window_start = current_timestamp - (current_timestamp % period)
            rate_limit_key = f"{key_hash}:{window_start}".encode()

            current_count = await self._increment_counter(rate_limit_key, amount=1, expiry=period)

            is_rate_limited = current_count > limit
            return current_count, is_rate_limited

        except Exception as e:
            logger.error(f"Error checking rate limit for key {key}: {e}")
            return 0, not self.fail_open

    async def _increment_counter(self, key: bytes, amount: int, expiry: int) -> int:
        """Atomically increment a counter, creating it with an expiry if missing."""
        try:
            return await self.client.incr(key, amount)
        except ClientException:
            # Key does not exist yet; add it with the window expiry and retry
            # the incr if a concurrent request created it in the meantime.
            added = await self.client.add(key, str(amount).encode(), exptime=expiry)
            if added:
                return amount
            return await self.client.incr(key, amount)

    async def get_count(self, key: str) -> int | None:
        """Get the current count for a key.

        Args:
            key: The rate limit key to check.

        Returns:
            The current count or None if the key doesn't exist.
        """
        try:
            value = await self.client.get(key.encode())
            if value:
                return int(value.decode())
            return None
        except Exception as e:
            logger.error(f"Error getting rate limit count for key {key}: {e}")
            return None

    async def reset(self, key: str) -> None:
        """Reset the counter for a key.

        Args:
            key: The rate limit key to reset.
        """
        try:
            await self.client.delete(key.encode())
        except Exception as e:
            logger.error(f"Error resetting rate limit for key {key}: {e}")

    async def increment(self, key: str, amount: int = 1, expiry: int = 300) -> int:
        """Increment a counter by the given amount and set expiry.

        Args:
            key: The key to increment
            amount: Amount to increment by
            expiry: Time in seconds for the key to expire

        Returns:
            The new value after incrementing
        """
        try:
            return await self._increment_counter(key.encode(), amount=amount, expiry=expiry)
        except Exception as e:
            logger.error(f"Error incrementing count for key {key}: {e}")
            return 0

    async def delete(self, key: str) -> bool:
        """Delete a key.

        Args:
            key: The key to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            return await self.client.delete(key.encode())
        except Exception as e:
            logger.error(f"Error deleting key {key}: {e}")
            return False

    async def ping(self) -> bool:
        """Check if the rate limiter backend is available.

        Returns:
            True if the backend is available, False otherwise.
        """
        try:
            test_key = b"rate_limiter_ping_test"
            test_value = b"1"
            await self.client.set(test_key, test_value, exptime=1)
            result = await self.client.get(test_key)
            return bool(result == test_value)
        except Exception as e:
            logger.error(f"Failed to ping Memcached server: {e}")
            return False
