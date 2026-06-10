"""Tests for resilience (retry, circuit breaker) and cost accounting."""
from __future__ import annotations

import pytest

from app.orchestration.cost import CostLedger, estimate_tokens
from app.orchestration.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    RetryExhausted,
    RetryPolicy,
)


# ---- Retry ----

def test_retry_succeeds_first_try():
    rp = RetryPolicy(sleep=lambda s: None)
    assert rp.run(lambda: 42) == 42


def test_retry_succeeds_after_failures():
    state = {"n": 0}

    def flaky():
        state["n"] += 1
        if state["n"] < 3:
            raise ValueError("transient")
        return "ok"

    rp = RetryPolicy(max_attempts=3, base_delay_s=0.0, sleep=lambda s: None)
    assert rp.run(flaky) == "ok"
    assert state["n"] == 3


def test_retry_exhausted():
    rp = RetryPolicy(max_attempts=2, sleep=lambda s: None)
    with pytest.raises(RetryExhausted) as ei:
        rp.run(lambda: (_ for _ in ()).throw(RuntimeError("always")))
    assert ei.value.attempts == 2
    assert isinstance(ei.value.last_error, RuntimeError)


def test_retry_only_retryable():
    rp = RetryPolicy(max_attempts=3, retryable=(ValueError,), sleep=lambda s: None)
    with pytest.raises(KeyError):
        rp.run(lambda: (_ for _ in ()).throw(KeyError("not retryable")))


def test_retry_backoff_capped():
    delays = []
    rp = RetryPolicy(
        max_attempts=4,
        base_delay_s=1.0,
        max_delay_s=2.0,
        multiplier=10.0,
        sleep=delays.append,
    )
    with pytest.raises(RetryExhausted):
        rp.run(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert all(d <= 2.0 for d in delays)


# ---- Circuit breaker ----

def test_breaker_trips_and_recovers():
    clock = {"t": 0.0}
    cb = CircuitBreaker(failure_threshold=3, cooldown_s=10.0, now=lambda: clock["t"])
    for _ in range(3):
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cb.state == CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        cb.call(lambda: "x")
    clock["t"] = 11.0
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.call(lambda: "recovered") == "recovered"
    assert cb.state == CircuitState.CLOSED


def test_breaker_stays_closed_on_success():
    cb = CircuitBreaker(failure_threshold=2)
    assert cb.call(lambda: 1) == 1
    assert cb.state == CircuitState.CLOSED


def test_breaker_resets_failures_on_success():
    cb = CircuitBreaker(failure_threshold=3)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("a")))
    cb.call(lambda: "ok")  # resets counter
    # Two more failures should NOT trip (counter was reset).
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("b")))
    assert cb.state == CircuitState.CLOSED


# ---- Cost ----

def test_estimate_tokens():
    assert estimate_tokens("") == 1
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 40) == 10


def test_cost_ledger_known_model():
    ledger = CostLedger()
    ledger.add("gemini-2.0-flash", 1000, 1000)
    assert ledger.total_input_tokens == 1000
    assert ledger.total_output_tokens == 1000
    assert ledger.total_cost_usd > 0
    s = ledger.summary()
    assert s["calls"] == 1


def test_cost_ledger_unknown_model_free():
    ledger = CostLedger()
    ledger.add("unknown-model", 1000, 1000)
    assert ledger.total_cost_usd == 0.0


def test_cost_ledger_add_text():
    ledger = CostLedger()
    rec = ledger.add_text("mock-concierge", "hello world", "a response here")
    assert rec.input_tokens > 0
    assert rec.output_tokens > 0
    assert ledger.total_cost_usd == 0.0
