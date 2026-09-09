from datetime import UTC, datetime

try:
    from redis.asyncio import Redis
    from redis.exceptions import RedisError
except ImportError:
    raise ImportError(
        "The redis package is not installed. Please install it with 'pip install redis' or 'pip install -e \".[redis]\"'"
    )

from ....modules.common.utils.logger import get_logger
from ...backends import RedisSettings
from ...backends.redis_pool import get_redis_pool
from ..base import RateLimiterBackend
from ..exceptions import RateLimiterBackendException

logger = get_logger(__name__)


class RedisBackend(RateLimiterBackend):
    """Redis implementation of the rate limiter backend."""

    def __init__(self, settings: RedisSettings | None = None, fail_open: bool = True):
        """Initialize the Redis backend.

        Args:
            settings: Redis connection settings. If None, default settings are used.
            fail_open: Whether to fail open (allow requests) when rate limiting errors occur.
                       Default is True for safety.
        """
        super().__init__(fail_open=fail_open)
        self.settings = settings or RedisSettings()
        try:
            # Shared pools are created with decode_responses=False; this backend
            # decodes the only string value it reads (get_count) itself.
            self.client = Redis(connection_pool=get_redis_pool(self.settings))
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            raise RateLimiterBackendException(f"Failed to initialize Redis client: {e}")

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
            current_timestamp = int(datetime.now(UTC).timestamp())
            window_start = current_timestamp - (current_timestamp % period)
            rate_limit_key = f"{key}:{window_start}"

            pipe = self.client.pipeline()
            pipe.incr(rate_limit_key)
            pipe.expire(rate_limit_key, int(period))
            result = await pipe.execute()

            current_count = result[0]

            is_rate_limited = current_count > limit
            return current_count, is_rate_limited

        except RedisError as e:
            logger.error(f"Redis error checking rate limit for key {key}: {e}")
            return 0, not self.fail_open
        except Exception as e:
            logger.error(f"Error checking rate limit for key {key}: {e}")
            return 0, not self.fail_open

    async def get_count(self, key: str) -> int | None:
        """Get the current count for a key.

        Args:
            key: The rate limit key to check.

        Returns:
            The current count or None if the key doesn't exist.
        """
        try:
            value = await self.client.get(key)
            if value:
                return int(value.decode() if isinstance(value, bytes) else value)
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
            await self.client.delete(key)
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
            expiry_int = int(expiry)

            pipe = self.client.pipeline()
            pipe.incrby(key, amount)
            pipe.expire(key, expiry_int)
            result: list[int] = await pipe.execute()
            return result[0]
        except RedisError as e:
            logger.error(f"Redis error incrementing count for key {key}: {type(e).__name__}: {str(e)}")
            if not self.fail_open:
                raise RateLimiterBackendException(f"Redis pipeline failed for key {key}")
            return 0
        except Exception as e:
            logger.error(f"Error incrementing count for key {key}: {type(e).__name__}: {str(e)}")
            if not self.fail_open:
                raise RateLimiterBackendException(f"Unexpected error for key {key}")
            return 0

    async def delete(self, key: str) -> bool:
        """Delete a key.

        Args:
            key: The key to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            result = await self.client.delete(key)
            return bool(result)
        except Exception as e:
            logger.error(f"Error deleting key {key}: {e}")
            return False

    async def ping(self) -> bool:
        """Check if the rate limiter backend is available.

        Returns:
            True if the backend is available, False otherwise.
        """
        try:
            result = await self.client.ping()  # type: ignore[misc]
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to ping Redis server: {e}")
            return False
