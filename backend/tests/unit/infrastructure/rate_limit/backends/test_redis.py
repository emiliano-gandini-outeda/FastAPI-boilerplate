"""Tests for the Redis rate limiter backend."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.exceptions import RedisError

from src.infrastructure.rate_limit.backends.redis import RedisBackend, RedisSettings


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    pipeline_mock = MagicMock()
    pipeline_mock.incr = MagicMock()
    pipeline_mock.expire = MagicMock()
    pipeline_mock.execute = AsyncMock(return_value=[1])

    client_mock = AsyncMock()
    client_mock.pipeline = MagicMock(return_value=pipeline_mock)
    client_mock.get = AsyncMock(return_value="1")
    client_mock.mget = AsyncMock(return_value=["1"])
    client_mock.delete = AsyncMock(return_value=1)
    client_mock.ping = AsyncMock(return_value=True)

    def scan_iter(match=None):
        async def _gen():
            for key in client_mock._scan_keys:
                yield key

        return _gen()

    client_mock._scan_keys = []
    client_mock.scan_iter = MagicMock(side_effect=scan_iter)

    return client_mock, pipeline_mock


@pytest.fixture
def redis_backend(mock_redis_client):
    """Create a RedisBackend with a mock client."""
    client_mock, pipeline_mock = mock_redis_client

    settings = RedisSettings(host="localhost", port=6379)
    backend = RedisBackend(settings=settings, fail_open=True)
    backend.client = client_mock

    yield backend, client_mock, pipeline_mock


@pytest.mark.asyncio
async def test_increment_and_check_new_key(redis_backend):
    """Test incrementing a counter for a new key."""
    backend, client_mock, pipeline_mock = redis_backend

    pipeline_mock.execute.return_value = [1]

    count, is_limited = await backend.increment_and_check(key="test:123", limit=5, period=60)

    assert count == 1
    assert is_limited is False

    client_mock.pipeline.assert_called_once()
    pipeline_mock.incr.assert_called_once()
    pipeline_mock.expire.assert_called_once()
    pipeline_mock.execute.assert_called_once()


@pytest.mark.asyncio
async def test_increment_and_check_existing_key(redis_backend):
    """Test incrementing a counter for an existing key."""
    backend, client_mock, pipeline_mock = redis_backend

    pipeline_mock.execute.return_value = [5]

    count, is_limited = await backend.increment_and_check(key="test:123", limit=5, period=60)

    assert count == 5
    assert is_limited is False


@pytest.mark.asyncio
async def test_rate_limited(redis_backend):
    """Test that requests are rate limited once limit is exceeded."""
    backend, client_mock, pipeline_mock = redis_backend

    pipeline_mock.execute.return_value = [6]

    count, is_limited = await backend.increment_and_check(key="test:123", limit=5, period=60)

    assert count == 6
    assert is_limited is True


@pytest.mark.asyncio
async def test_get_count(redis_backend):
    """Test getting the current count sums the windowed keys."""
    backend, client_mock, _ = redis_backend

    client_mock._scan_keys = ["test:123:1000", "test:123:1060"]
    client_mock.mget.return_value = ["2", "1"]
    count = await backend.get_count("test:123")
    assert count == 3
    client_mock.scan_iter.assert_called_once_with(match="test:123:*")

    client_mock._scan_keys = []
    count = await backend.get_count("test:456")
    assert count is None


@pytest.mark.asyncio
async def test_reset(redis_backend):
    """Test resetting the counter deletes all windowed keys."""
    backend, client_mock, _ = redis_backend

    client_mock._scan_keys = ["test:123:1000", "test:123:1060"]
    await backend.reset("test:123")
    client_mock.delete.assert_called_once_with("test:123:1000", "test:123:1060")


@pytest.mark.asyncio
async def test_delete_covers_windowed_keys(redis_backend):
    """Test that delete removes the raw key and any windowed keys."""
    backend, client_mock, _ = redis_backend

    client_mock._scan_keys = ["test:123:1000"]
    result = await backend.delete("test:123")
    assert result is True
    client_mock.delete.assert_called_once_with("test:123", "test:123:1000")


@pytest.mark.asyncio
async def test_ping_success(redis_backend):
    """Test ping with successful connection."""
    backend, client_mock, _ = redis_backend
    client_mock.ping.return_value = True

    result = await backend.ping()
    assert result is True


@pytest.mark.asyncio
async def test_ping_failure(redis_backend):
    """Test ping with failed connection."""
    backend, client_mock, _ = redis_backend
    client_mock.ping.side_effect = Exception("Connection failed")

    result = await backend.ping()
    assert result is False


@pytest.mark.asyncio
async def test_redis_error_handling(redis_backend):
    """Test Redis-specific error handling."""
    backend, client_mock, pipeline_mock = redis_backend

    pipeline_mock.execute.side_effect = RedisError("Redis error")

    count, is_limited = await backend.increment_and_check(key="test:123", limit=5, period=60)

    assert count == 0
    assert is_limited is False
