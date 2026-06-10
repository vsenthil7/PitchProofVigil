"""Resilience primitives: retry policy and circuit breaker.

``RetryPolicy`` wraps a callable with bounded exponential backoff over a set of
retryable exceptions. ``CircuitBreaker`` trips open after a threshold of
consecutive failures and rejects calls until a cooldown elapses, then allows a
trial call (half-open). Both are dependency-free and deterministic (the sleep
function is injectable for tests).
"""
from __future__ import annotations

import enum
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


class RetryExhausted(Exception):
    def __init__(self, attempts: int, last_error: Exception) -> None:
        super().__init__(f"Retry exhausted after {attempts} attempt(s): {last_error}")
        self.attempts = attempts
        self.last_error = last_error


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay_s: float = 0.05
    max_delay_s: float = 1.0
    multiplier: float = 2.0
    retryable: tuple[type[Exception], ...] = (Exception,)
    sleep: Callable[[float], None] = time.sleep

    def run(self, fn: Callable[[], T]) -> T:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return fn()
            except self.retryable as exc:
                last_error = exc
                if attempt >= self.max_attempts:
                    break
                delay = min(
                    self.base_delay_s * (self.multiplier ** (attempt - 1)),
                    self.max_delay_s,
                )
                self.sleep(delay)
        assert last_error is not None
        raise RetryExhausted(self.max_attempts, last_error)


class CircuitState(str, enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    pass


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    cooldown_s: float = 30.0
    now: Callable[[], float] = time.monotonic

    def __post_init__(self) -> None:
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0

    @property
    def state(self) -> CircuitState:
        # Transition OPEN → HALF_OPEN after cooldown.
        if (
            self._state == CircuitState.OPEN
            and self.now() - self._opened_at >= self.cooldown_s
        ):
            self._state = CircuitState.HALF_OPEN
        return self._state

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._state = CircuitState.CLOSED

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = self.now()

    def call(self, fn: Callable[[], T]) -> T:
        state = self.state
        if state == CircuitState.OPEN:
            raise CircuitOpenError("Circuit is open; rejecting call.")
        try:
            result = fn()
        except Exception:
            self._record_failure()
            raise
        self._record_success()
        return result
