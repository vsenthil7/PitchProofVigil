"""Token-bucket rate limiter.

A classic token bucket: ``capacity`` tokens refilling at ``refill_per_second``.
Each request tries to ``consume`` one token; if none are available the request
is rejected. Time is injectable for deterministic tests. The limiter is
in-process (per worker); a Redis-backed variant would swap the store but keep
this interface.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class TokenBucket:
    capacity: float
    refill_per_second: float
    now: "callable" = time.monotonic

    def __post_init__(self) -> None:
        self._tokens = float(self.capacity)
        self._last = self.now()
        self._lock = Lock()

    def _refill(self) -> None:
        current = self.now()
        elapsed = current - self._last
        if elapsed > 0:
            self._tokens = min(
                self.capacity, self._tokens + elapsed * self.refill_per_second
            )
            self._last = current

    def consume(self, tokens: float = 1.0) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def available(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens


@dataclass
class RateLimiter:
    """Keyed collection of token buckets (one per tenant/identity)."""

    capacity: float = 60.0
    refill_per_second: float = 1.0
    now: "callable" = time.monotonic
    _buckets: dict[str, TokenBucket] = field(default_factory=dict)

    def _bucket_for(self, key: str) -> TokenBucket:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(self.capacity, self.refill_per_second, self.now)
            self._buckets[key] = bucket
        return bucket

    def check(self, key: str, tokens: float = 1.0) -> bool:
        return self._bucket_for(key).consume(tokens)

    def remaining(self, key: str) -> int:
        return int(self._bucket_for(key).available)
