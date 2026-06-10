"""OpenTelemetry / OpenInference tracing configuration.

Wires OTLP span export to Arize Phoenix (and optionally Arize AX) on startup.
In mock mode this is a no-op so the laptop dev loop never needs an external
collector, and the OTel packages stay optional (lazy-imported in real mode).

Usage (in lifespan):
    from app.observability.tracing import configure_tracing
    configure_tracing(settings)
"""
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from app.core.config import Settings


def configure_tracing(settings: "Settings") -> None:
    """Install an OpenTelemetry -> Phoenix OTLP exporter.

    Safe to call multiple times (idempotent via the global TracerProvider
    check). No-op in mock mode; degrades silently if the OTel packages are
    missing or the collector is unreachable.
    """
    if settings.use_mocks:
        return

    try:  # pragma: no cover - requires optional OTel packages + live collector
        from opentelemetry import trace as otel_trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        existing = otel_trace.get_tracer_provider()
        if not isinstance(existing, TracerProvider):
            headers: dict = {}
            if settings.phoenix_api_key:
                headers["Authorization"] = f"Bearer {settings.phoenix_api_key}"
            exporter = OTLPSpanExporter(
                endpoint=f"{settings.phoenix_collector_endpoint}/v1/traces",
                headers=headers,
            )
            provider = TracerProvider()
            provider.add_span_processor(BatchSpanProcessor(exporter))
            otel_trace.set_tracer_provider(provider)
    except Exception:  # pragma: no cover - defensive degrade
        pass


def get_tracer(name: str = "pitchproof-vigil"):
    """Return a tracer; falls back to a no-op tracer when OTel is absent."""
    try:
        from opentelemetry import trace as otel_trace

        return otel_trace.get_tracer(name)
    except Exception:  # pragma: no cover - only when OTel is not installed
        return _NoOpTracer()


class _NoOpTracer:
    """Minimal no-op tracer for mock mode / when OTel is not installed."""

    def start_as_current_span(self, name: str, **kwargs):
        return contextlib.nullcontext()

    def start_span(self, name: str, **kwargs):
        return _NoOpSpan()


class _NoOpSpan:
    def set_attribute(self, key, value):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
