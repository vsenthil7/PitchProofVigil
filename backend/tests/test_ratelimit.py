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
