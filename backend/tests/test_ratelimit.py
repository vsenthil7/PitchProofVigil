"""Tests for the token-bucket rate limiter."""
from __future__ import annotations

from app.ratelimit.bucket import RateLimiter, TokenBucket


def test_bucket_allows_up_to_capacity():
    clock = {"t": 0.0}
    b = TokenBucket(capacity=3, refill_per_second=0, now=lambda: clock["t"])
    assert b.consume() and b.consume() and b.consume()
    assert not b.consume()  # exhausted, no refill


def test_bucket_refills_over_time():
    clock = {"t": 0.0}
    b = TokenBucket(capacity=2, refill_per_second=1, now=lambda: clock["t"])
    assert b.consume() and b.consume()
    assert not b.consume()
    clock["t"] = 1.0  # 1 token refilled
    assert b.consume()
    assert not b.consume()


def test_bucket_refill_caps_at_capacity():
    clock = {"t": 0.0}
    b = TokenBucket(capacity=5, refill_per_second=10, now=lambda: clock["t"])
    clock["t"] = 100.0  # would refill 1000 but caps at 5
    assert b.available == 5


def test_bucket_available_property():
    clock = {"t": 0.0}
    b = TokenBucket(capacity=10, refill_per_second=0, now=lambda: clock["t"])
    b.consume(4)
    assert b.available == 6


def test_limiter_per_key_isolation():
    clock = {"t": 0.0}
    rl = RateLimiter(capacity=1, refill_per_second=0, now=lambda: clock["t"])
    assert rl.check("tenant-a")
    assert not rl.check("tenant-a")  # a exhausted
    assert rl.check("tenant-b")  # b independent


def test_limiter_remaining():
    clock = {"t": 0.0}
    rl = RateLimiter(capacity=5, refill_per_second=0, now=lambda: clock["t"])
    rl.check("k")
    assert rl.remaining("k") == 4


# ---- P4: RedisRateLimiter (distributed) ----

async def test_redis_rate_limiter_allows_under_capacity():
    import fakeredis.aioredis as fakeredis

    from app.ratelimit.redis_bucket import RedisRateLimiter

    r = fakeredis.FakeRedis()
    limiter = RedisRateLimiter(redis_client=r, capacity=5.0, refill_per_second=1.0)
    for _ in range(5):
        assert await limiter.check("test-key") is True


async def test_redis_rate_limiter_denies_over_capacity():
    import fakeredis.aioredis as fakeredis

    from app.ratelimit.redis_bucket import RedisRateLimiter

    r = fakeredis.FakeRedis()
    limiter = RedisRateLimiter(redis_client=r, capacity=3.0, refill_per_second=0.0)
    results = [await limiter.check("test-key-deny") for _ in range(4)]
    assert results[:3] == [True, True, True]
    assert results[3] is False


async def test_redis_rate_limiter_remaining():
    import fakeredis.aioredis as fakeredis

    from app.ratelimit.redis_bucket import RedisRateLimiter

    r = fakeredis.FakeRedis()
    limiter = RedisRateLimiter(redis_client=r, capacity=10.0, refill_per_second=0.0)
    await limiter.check("key-remaining")
    assert await limiter.remaining("key-remaining") == 9


async def test_redis_rate_limiter_remaining_unknown_key():
    import fakeredis.aioredis as fakeredis

    from app.ratelimit.redis_bucket import RedisRateLimiter

    r = fakeredis.FakeRedis()
    limiter = RedisRateLimiter(redis_client=r, capacity=10.0, refill_per_second=0.0)
    # No prior check -> full capacity reported.
    assert await limiter.remaining("never-seen") == 10


async def test_redis_rate_limiter_fail_open_on_error():
    """If Redis is unreachable, check fails open (True) and remaining is capacity."""
    from unittest.mock import AsyncMock, MagicMock

    from app.ratelimit.redis_bucket import RedisRateLimiter

    mock_redis = MagicMock()
    mock_redis.script_load = AsyncMock(side_effect=ConnectionError("Redis down"))
    mock_redis.hget = AsyncMock(side_effect=ConnectionError("Redis down"))
    limiter = RedisRateLimiter(redis_client=mock_redis, capacity=5.0, refill_per_second=1.0)
    assert await limiter.check("some-key") is True
    assert await limiter.remaining("some-key") == 5


async def test_redis_rate_limiter_atomic_lua_path():
    """Exercise the EVALSHA atomic path with a mock that supports scripting."""
    from unittest.mock import AsyncMock, MagicMock

    from app.ratelimit.redis_bucket import RedisRateLimiter

    redis = MagicMock()
    redis.script_load = AsyncMock(return_value="sha123")
    # First call allowed (1), second denied (0).
    redis.evalsha = AsyncMock(side_effect=[1, 0])
    limiter = RedisRateLimiter(redis_client=redis, capacity=1.0, refill_per_second=0.0)
    assert await limiter.check("k") is True
    assert await limiter.check("k") is False
    # SHA cached after first load.
    redis.script_load.assert_awaited_once()


async def test_redis_rate_limiter_non_scripting_error_fails_open():
    """A genuine Redis error (not 'unknown command') fails open."""
    from unittest.mock import AsyncMock, MagicMock

    from app.ratelimit.redis_bucket import RedisRateLimiter

    redis = MagicMock()
    redis.script_load = AsyncMock(return_value="sha")
    redis.evalsha = AsyncMock(side_effect=TimeoutError("redis timeout"))
    limiter = RedisRateLimiter(redis_client=redis, capacity=5.0, refill_per_second=1.0)
    assert await limiter.check("k") is True
