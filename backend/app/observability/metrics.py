"""Prometheus metrics for the platform.

Uses a dedicated CollectorRegistry so metrics are isolatable in tests. Exposes
counters/histograms for HTTP requests, agent calls, evaluations, and gate
decisions, plus a render helper for the /metrics endpoint.
"""
from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


class Metrics:
    """Container for all application metrics, bound to one registry."""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()

        self.http_requests = Counter(
            "ppv_http_requests_total",
            "HTTP requests processed.",
            ["method", "path", "status"],
            registry=self.registry,
        )
        self.http_latency = Histogram(
            "ppv_http_request_duration_seconds",
            "HTTP request latency.",
            ["method", "path"],
            registry=self.registry,
        )
        self.agent_calls = Counter(
            "ppv_agent_calls_total",
            "Concierge agent invocations.",
            ["intent", "mode"],
            registry=self.registry,
        )
        self.agent_latency = Histogram(
            "ppv_agent_latency_ms",
            "Agent response latency in ms.",
            buckets=(1, 5, 10, 50, 100, 500, 1000, 5000),
            registry=self.registry,
        )
        self.evaluations = Counter(
            "ppv_evaluations_total",
            "Evaluations run.",
            ["evaluator", "verdict"],
            registry=self.registry,
        )
        self.gate_decisions = Counter(
            "ppv_gate_decisions_total",
            "Gate decisions.",
            ["passed"],
            registry=self.registry,
        )
        self.active_tenants = Gauge(
            "ppv_active_tenants",
            "Number of active tenants observed this process.",
            registry=self.registry,
        )
        self.rate_limited = Counter(
            "ppv_rate_limited_total",
            "Requests rejected by the rate limiter.",
            ["path"],
            registry=self.registry,
        )

    def observe_http(self, method: str, path: str, status: int, duration_s: float) -> None:
        self.http_requests.labels(method=method, path=path, status=str(status)).inc()
        self.http_latency.labels(method=method, path=path).observe(duration_s)

    def observe_agent(self, intent: str, mode: str, latency_ms: float) -> None:
        self.agent_calls.labels(intent=intent, mode=mode).inc()
        self.agent_latency.observe(latency_ms)

    def observe_evaluation(self, evaluator: str, verdict: str) -> None:
        self.evaluations.labels(evaluator=evaluator, verdict=verdict).inc()

    def observe_gate(self, passed: bool) -> None:
        self.gate_decisions.labels(passed=str(passed).lower()).inc()

    def observe_rate_limited(self, path: str) -> None:
        self.rate_limited.labels(path=path).inc()

    def render(self) -> tuple[bytes, str]:
        return generate_latest(self.registry), CONTENT_TYPE_LATEST


_metrics: Metrics | None = None


def get_metrics() -> Metrics:
    global _metrics
    if _metrics is None:
        _metrics = Metrics()
    return _metrics


def reset_metrics() -> None:
    global _metrics
    _metrics = None
